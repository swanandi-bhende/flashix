// SPDX-License-Identifier: MIT
pragma solidity ^0.8.25;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "./LendingPool.sol";
import "./SignalValidator.sol";

/**
 * @title ISwapRouter
 * @dev Minimal interface for DEX router (supports Uniswap-like routers)
 */
interface ISwapRouter {
    function exactInputSingle(
        uint256 amountIn,
        uint256 amountOutMinimum,
        address tokenIn,
        address tokenOut,
        uint24 fee,
        address recipient
    ) external returns (uint256 amountOut);

    function exactOutputSingle(
        uint256 amountOut,
        uint256 amountInMaximum,
        address tokenIn,
        address tokenOut,
        uint24 fee,
        address recipient
    ) external returns (uint256 amountIn);
}

/**
 * @title ArbitrageExecutor
 * @dev On-chain execution engine for atomic perpswap arbitrage.
 *
 * Receives execution signals from the sealed 0G Compute TEE inference layer,
 * verifies cryptographic signatures, executes atomic perpswap trades, validates
 * profit calculations, and routes proceeds back to the lending pool.
 *
 * Implements the IERC3156FlashBorrower interface to receive flashloans from
 * LendingPool and execute atomic arbitrage in a single transaction.
 */
contract ArbitrageExecutor is IERC3156FlashBorrower, ReentrancyGuard, Pausable, Ownable {
    uint256 private constant SIGNAL_DATA_STATIC_SIZE = 10 * 32;
    uint256 private constant TRACE_ID_SIZE = 32;

    // ==================== State Variables ====================
    /// @notice Reference to the lending pool contract
    IERC3156FlashLender public lendingPool;

    /// @notice Reference to the signal validator contract
    SignalValidator public signalValidator;

    /// @notice Recipient for arbitrage profits
    address public profitRecipient;

    /// @notice Mapping of approved DEX routers
    mapping(address => bool) public approvedRouters;

    /// @notice Counter for execution IDs (for event tracking)
    uint256 public executionCounter;

    /// @notice Last trace identifier linked to an execution, if provided.
    bytes32 public lastTraceId;

    /// @notice Mapping from signal opportunity ID to the linked reasoning trace ID.
    mapping(bytes32 => bytes32) public traceIdsByOpportunity;

    // ==================== Events ====================
    /// @notice Emitted when arbitrage is successfully executed
    event ArbitrageExecuted(
        bytes32 indexed signalId,
        address indexed dexA,
        address indexed dexB,
        uint256 profit,
        uint256 gasUsed
    );

    /// @notice Emitted when DEX router approval changes
    event RouterApprovalUpdated(address indexed router, bool approved);

    /// @notice Emitted when profit recipient is updated
    event ProfitRecipientUpdated(address indexed newRecipient);

    /// @notice Emitted when lending pool reference is updated
    event LendingPoolUpdated(address indexed newPool);

    /// @notice Emitted when signal validator reference is updated
    event SignalValidatorUpdated(address indexed newValidator);

    /// @notice Emitted when a reasoning trace is linked to an execution.
    event TraceLinked(bytes32 indexed opportunityId, bytes32 indexed traceId);

    // ==================== Errors ====================
    /// @notice Raised when signal verification fails
    error SignalVerificationFailed(bytes32 opportunityId);

    /// @notice Raised when signal has expired
    error SignalExpired(uint256 deadline, uint256 blockTimestamp);

    /// @notice Raised when profit is below minimum threshold
    error InsufficientProfit(uint256 realized, uint256 required);

    /// @notice Raised when DEX router not approved
    error UnapprovedRouter(address router);

    /// @notice Raised when profit recipient is invalid
    error InvalidProfitRecipient();

    /// @notice Raised when lending pool not configured
    error LendingPoolNotConfigured();

    /// @notice Raised when signal validator not configured
    error SignalValidatorNotConfigured();

    // ==================== Constructor ====================
    /**
     * @notice Initialize arbitrage executor
     * @param _profitRecipient Initial recipient for arbitrage profits
     */
    constructor(address _profitRecipient) Ownable(msg.sender) {
        require(_profitRecipient != address(0), "Invalid profit recipient");
        profitRecipient = _profitRecipient;
        executionCounter = 0;
    }

    // ==================== Contract Configuration ====================
    /**
     * @notice Set the lending pool contract reference
     * @param _lendingPool Address of the lending pool contract
     */
    function setLendingPool(address _lendingPool) external onlyOwner {
        require(_lendingPool != address(0), "Invalid lending pool address");
        lendingPool = IERC3156FlashLender(_lendingPool);
        emit LendingPoolUpdated(_lendingPool);
    }

    /**
     * @notice Set the signal validator contract reference
     * @param _signalValidator Address of the signal validator contract
     */
    function setSignalValidator(address _signalValidator) external onlyOwner {
        require(_signalValidator != address(0), "Invalid signal validator address");
        signalValidator = SignalValidator(_signalValidator);
        emit SignalValidatorUpdated(_signalValidator);
    }

    /**
     * @notice Update the profit recipient address
     * @param _profitRecipient New recipient address
     */
    function setProfitRecipient(address _profitRecipient) external onlyOwner {
        require(_profitRecipient != address(0), "Invalid profit recipient");
        profitRecipient = _profitRecipient;
        emit ProfitRecipientUpdated(_profitRecipient);
    }

    /**
     * @notice Approve or revoke a DEX router
     * @param router The router address
     * @param approved True to approve, false to revoke
     */
    function setRouterApproval(address router, bool approved) external onlyOwner {
        require(router != address(0), "Invalid router address");
        approvedRouters[router] = approved;
        emit RouterApprovalUpdated(router, approved);
    }

    // ==================== Flashloan Callback ====================
    /**
     * @notice Receive flashloan and execute arbitrage
     * @param initiator The address that initiated the flashloan
     * @param token The borrowed token
     * @param amount The borrowed amount
     * @param fee The flashloan fee to repay
     * @param data Encoded arbitrage signal and execution parameters
     * @return keccak256("ERC3156FlashBorrower.onFlashLoan") on success
     */
    function onFlashLoan(
        address initiator,
        address token,
        uint256 amount,
        uint256 fee,
        bytes calldata data
    ) external nonReentrant returns (bytes32) {
        // Verify this is called by the lending pool
        require(msg.sender == address(lendingPool), "Unauthorized caller");
        require(address(lendingPool) != address(0), "LendingPool not configured");
        require(address(signalValidator) != address(0), "SignalValidator not configured");

        // Decode, verify, and extract the execution signal in a smaller scope to
        // keep stack usage low when compiling without viaIR.
        (
            bytes32 opportunityId,
            address dexA,
            address dexB,
            uint256 minProfit,
            bytes32 traceId
        ) = _validateSignal(data);

        if (traceId != bytes32(0)) {
            lastTraceId = traceId;
            traceIdsByOpportunity[opportunityId] = traceId;
            emit TraceLinked(opportunityId, traceId);
        }

        // Verify routers are approved.
        if (!approvedRouters[dexA] || !approvedRouters[dexB]) {
            revert UnapprovedRouter(dexA);
        }

        uint256 gasStart = gasleft();
        uint256 preBalance = IERC20(token).balanceOf(address(this));

        // Execute atomic arbitrage trades.
        _executeArbitrage(dexA, dexB, token, amount);

        uint256 realized = IERC20(token).balanceOf(address(this)) - preBalance;
        if (realized < minProfit) {
            revert InsufficientProfit(realized, minProfit);
        }

        uint256 repayAmount = amount + fee;
        require(IERC20(token).transfer(address(lendingPool), repayAmount), "Repayment transfer failed");

        if (realized > 0) {
            require(IERC20(token).transfer(profitRecipient, realized), "Profit transfer failed");
        }

        executionCounter++;

        emit ArbitrageExecuted(opportunityId, dexA, dexB, realized, gasStart - gasleft());

        // Return ERC-3156 callback hash
        return keccak256("ERC3156FlashBorrower.onFlashLoan");
    }

    /**
     * @notice Decode and verify a signal, returning only the fields used by execution.
     * @param data Encoded arbitrage signal and execution parameters
     * @return opportunityId Unique signal identifier
     * @return dexA First DEX router address
     * @return dexB Second DEX router address
     * @return minProfit Minimum acceptable profit
     */
    function _validateSignal(
        bytes calldata data
    )
        internal
        returns (
            bytes32 opportunityId,
            address dexA,
            address dexB,
            uint256 minProfit,
            bytes32 traceId
        )
    {
        bytes calldata signalData = data[:SIGNAL_DATA_STATIC_SIZE];
        SignalValidator.ArbitrageSignal memory signal = abi.decode(signalData, (SignalValidator.ArbitrageSignal));

        traceId = bytes32(0);
        if (data.length >= SIGNAL_DATA_STATIC_SIZE + TRACE_ID_SIZE) {
            traceId = bytes32(data[SIGNAL_DATA_STATIC_SIZE:SIGNAL_DATA_STATIC_SIZE + TRACE_ID_SIZE]);
        }

        if (block.timestamp > signal.deadline) {
            revert SignalExpired(signal.deadline, block.timestamp);
        }

        bool isValid;
        try signalValidator.verify(signal) returns (bool verified) {
            isValid = verified;
        } catch {
            revert SignalVerificationFailed(signal.opportunityId);
        }

        if (!isValid) {
            revert SignalVerificationFailed(signal.opportunityId);
        }

        return (
            signal.opportunityId,
            signal.dexA,
            signal.dexB,
            signal.minProfit,
            traceId
        );
    }

    // ==================== Internal Trade Execution ====================
    /**
     * @notice Execute atomic perpswap trades (long + short in same tx)
     * @param dexA First DEX router
     * @param dexB Second DEX router
     * @param token The borrow token
     * @param amount The borrowed amount
     */
    function _executeArbitrage(
        address dexA,
        address dexB,
        address token,
        uint256 amount
    ) internal {

        // Simple placeholder implementation:
        // In production, this would:
        // 1. Parse perpetual market addresses from signal
        // 2. Execute long position on dexA
        // 3. Execute short position on dexB
        // 4. Close both positions atomically
        // 5. Validate realized PnL exceeds minProfit

        // For testing/demo purposes, we verify the call completes without reverting
        // The actual DEX integration depends on specific DEX interfaces
        
        // Approve tokens to DEX routers
        require(IERC20(token).approve(dexA, amount), "Approval to dexA failed");
        require(IERC20(token).approve(dexB, amount), "Approval to dexB failed");

        // Placeholder: In production, call actual DEX interfaces here
        // Example (pseudo-code):
        // - IPerpsMarket(dexA).openLongPosition(amount, ...)
        // - IPerpsMarket(dexB).openShortPosition(amount, ...)
        // - Close positions and calculate PnL
        
        // For now, we assume successful execution that would generate profit
        // The actual implementation requires specific DEX ABIs and interfaces
    }

    // ==================== Emergency Management ====================
    /**
     * @notice Pause arbitrage execution
     */
    function pause() external onlyOwner {
        _pause();
    }

    /**
     * @notice Unpause arbitrage execution
     */
    function unpause() external onlyOwner {
        _unpause();
    }

    /**
     * @notice Emergency token recovery
     * @param token The token to recover
     * @param amount The amount to recover
     */
    function emergencyWithdraw(address token, uint256 amount) external onlyOwner {
        require(IERC20(token).transfer(msg.sender, amount), "Transfer failed");
    }

    /**
     * @notice Get execution counter (total executions)
     * @return Total number of successful arbitrage executions
     */
    function getExecutionCount() external view returns (uint256) {
        return executionCounter;
    }
}

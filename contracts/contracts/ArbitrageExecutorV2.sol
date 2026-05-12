// SPDX-License-Identifier: MIT
pragma solidity ^0.8.25;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

import "./LendingPool.sol";
import "./SignalValidator.sol";
import "./interfaces/IGasConstants.sol";

/**
 * @title ISwapRouterV2
 * @dev Minimal router interface used by the V2 executor.
 */
interface ISwapRouterV2 {
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
 * @title ArbitrageExecutorV2
 * @dev Batch-capable arbitrage executor with shared validation and MEV controls.
 */
contract ArbitrageExecutorV2 is IERC3156FlashBorrower, ReentrancyGuard, Pausable, Ownable, IGasConstants {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    uint256 private constant NONCE_PRUNE_WINDOW = 7 days;

    /// @custom:storage-size 4 slots
    struct ArbitrageSignal {
        bytes32 opportunityId;
        address dexA;
        address dexB;
        address borrowToken;
        uint256 borrowAmount;
        uint256 minProfit;
        uint256 deadline;
        uint8 signatureV;
        bytes32 signatureR;
        bytes32 signatureS;
    }

    IERC3156FlashLender public lendingPool;
    SignalValidator public signalValidator;
    address public profitRecipient;
    address public trustedSigner;
    address public defaultBorrowToken;
    uint32 public maxBatchSize;
    bool public commitmentRequired;
    bool public mevBurnEnabled;

    uint256 public ethPriceUsdc;
    uint256 public mevBurnPct;
    uint256 public mevBurnTotalSpent;
    uint256 public executionCounter;
    bytes32 public lastTraceId;

    mapping(address => bool) public approvedRouters;
    mapping(bytes32 => uint256) public nonceTimestamps;
    mapping(bytes32 => uint256) public commitmentBlocks;

    event ArbitrageExecuted(bytes32 indexed signalId, address indexed dexA, address indexed dexB, uint256 profit, uint256 gasUsed);
    event BatchArbitrageExecuted(bytes32 indexed batchId, uint256 signalCount, uint256 totalProfit, uint256 gasUsed);
    event RouterApprovalUpdated(address indexed router, bool approved);
    event ProfitRecipientUpdated(address indexed newRecipient);
    event LendingPoolUpdated(address indexed newPool);
    event SignalValidatorUpdated(address indexed newValidator);
    event TraceLinked(bytes32 indexed opportunityId, bytes32 indexed traceId);
    event MevBurnExecuted(uint256 amount, address coinbase);
    event MevFundDeposited(uint256 amount);
    event CommitmentRecorded(bytes32 indexed commitment, uint256 blockNumber);
    event NoncePruned(bytes32 indexed nonce);
    event MevBurnSettingsUpdated(bool enabled, uint256 pct, uint256 ethPriceUsdc);
    event CommitmentRequirementUpdated(bool required);
    event TrustedSignerUpdated(address indexed oldSigner, address indexed newSigner);

    error SignalVerificationFailed(bytes32 opportunityId);
    error SignalExpired(uint256 deadline, uint256 blockTimestamp);
    error InsufficientProfit(uint256 realized, uint256 required);
    error UnapprovedRouter(address router);
    error InvalidProfitRecipient();
    error LendingPoolNotConfigured();
    error SignalValidatorNotConfigured();
    error InvalidBatchSize(uint256 provided, uint256 maxSize);
    error InvalidBatchDeadline(uint256 deadline, uint256 blockTimestamp);
    error InvalidBorrowAmount(uint256 expected, uint256 actual);
    error InvalidNonce(bytes32 nonce);
    error CommitmentMissing(bytes32 commitment);

    constructor(address _profitRecipient) Ownable(msg.sender) {
        require(_profitRecipient != address(0), "Invalid profit recipient");
        profitRecipient = _profitRecipient;
        maxBatchSize = 5;
        ethPriceUsdc = 2_500_000_000;
        mevBurnPct = 2;
        executionCounter = 1;
        mevBurnTotalSpent = 1;
    }

    receive() external payable {}

    function setLendingPool(address _lendingPool) external onlyOwner {
        require(_lendingPool != address(0), "Invalid lending pool address");
        lendingPool = IERC3156FlashLender(_lendingPool);
        emit LendingPoolUpdated(_lendingPool);
    }

    function setSignalValidator(address _signalValidator) external onlyOwner {
        require(_signalValidator != address(0), "Invalid signal validator address");
        signalValidator = SignalValidator(_signalValidator);
        address oldSigner = trustedSigner;
        trustedSigner = signalValidator.getTrustedSigner();
        emit SignalValidatorUpdated(_signalValidator);
        emit TrustedSignerUpdated(oldSigner, trustedSigner);
    }

    function setTrustedSigner(address newSigner) external onlyOwner {
        require(newSigner != address(0), "Invalid signer address");
        address oldSigner = trustedSigner;
        trustedSigner = newSigner;
        emit TrustedSignerUpdated(oldSigner, newSigner);
    }

    function setProfitRecipient(address _profitRecipient) external onlyOwner {
        require(_profitRecipient != address(0), "Invalid profit recipient");
        profitRecipient = _profitRecipient;
        emit ProfitRecipientUpdated(_profitRecipient);
    }

    function setRouterApproval(address router, bool approved) external onlyOwner {
        require(router != address(0), "Invalid router address");
        approvedRouters[router] = approved;
        if (approved && defaultBorrowToken != address(0)) {
            require(IERC20(defaultBorrowToken).approve(router, type(uint256).max), "Approval setup failed");
        }
        emit RouterApprovalUpdated(router, approved);
    }

    function setDefaultBorrowToken(address token) external onlyOwner {
        require(token != address(0), "Invalid token address");
        defaultBorrowToken = token;
    }

    function setCommitmentRequired(bool required) external onlyOwner {
        commitmentRequired = required;
        emit CommitmentRequirementUpdated(required);
    }

    function setMevBurnEnabled(bool enabled) external onlyOwner {
        mevBurnEnabled = enabled;
        emit MevBurnSettingsUpdated(enabled, mevBurnPct, ethPriceUsdc);
    }

    function setMevBurnPct(uint256 pct) external onlyOwner {
        require(pct <= 100, "Invalid burn pct");
        mevBurnPct = pct;
        emit MevBurnSettingsUpdated(mevBurnEnabled, pct, ethPriceUsdc);
    }

    function setEthPriceUsdc(uint256 price) external onlyOwner {
        require(price > 0, "Invalid ETH price");
        ethPriceUsdc = price;
        emit MevBurnSettingsUpdated(mevBurnEnabled, mevBurnPct, price);
    }

    function setMaxBatchSize(uint32 newMaxBatchSize) external onlyOwner {
        require(newMaxBatchSize >= 1 && newMaxBatchSize <= 5, "Invalid batch size");
        maxBatchSize = newMaxBatchSize;
    }

    function commitSignal(bytes32 commitment) external {
        commitmentBlocks[commitment] = block.number;
        emit CommitmentRecorded(commitment, block.number);
    }

    function pruneExpiredNonces(bytes32[] calldata nonces) external onlyOwner {
        for (uint256 i = 0; i < nonces.length; i++) {
            bytes32 nonce = nonces[i];
            uint256 usedAt = nonceTimestamps[nonce];
            if (usedAt == 0 || block.timestamp < usedAt + NONCE_PRUNE_WINDOW) {
                revert InvalidNonce(nonce);
            }
            delete nonceTimestamps[nonce];
            emit NoncePruned(nonce);
        }
    }

    function depositMevFund() external payable onlyOwner {
        emit MevFundDeposited(msg.value);
    }

    function executeArbitrage(ArbitrageSignal calldata signal) external nonReentrant whenNotPaused {
        BatchSignal[] memory signals = new BatchSignal[](1);
        signals[0] = BatchSignal({
            opportunityId: signal.opportunityId,
            primaryDex: signal.dexA,
            counterDex: signal.dexB,
            borrowAmount: signal.borrowAmount,
            collateralRequired: 0,
            minProfit: signal.minProfit,
            deadline: uint32(signal.deadline),
            v: signal.signatureV,
            r: signal.signatureR,
            s: signal.signatureS
        });

        BatchExecutionParams memory params = BatchExecutionParams({
            signals: signals,
            borrowToken: signal.borrowToken,
            totalBorrowAmount: signal.borrowAmount,
            batchDeadline: signal.deadline,
            activateMevBurn: false,
            mevBurnAmount: 0
        });

        _executeArbitrageBatch(params);
    }

    function executeArbitrageBatch(BatchExecutionParams calldata params) external nonReentrant whenNotPaused {
        BatchExecutionParams memory copied = BatchExecutionParams({
            signals: params.signals,
            borrowToken: params.borrowToken,
            totalBorrowAmount: params.totalBorrowAmount,
            batchDeadline: params.batchDeadline,
            activateMevBurn: params.activateMevBurn,
            mevBurnAmount: params.mevBurnAmount
        });

        _executeArbitrageBatch(copied);
    }

    function onFlashLoan(
        address /*initiator*/,
        address token,
        uint256 amount,
        uint256 fee,
        bytes calldata data
    ) external returns (bytes32) {
        BatchExecutionParams memory params = abi.decode(data, (BatchExecutionParams));
        if (amount != params.totalBorrowAmount) {
            revert InvalidBorrowAmount(params.totalBorrowAmount, amount);
        }

        uint256 preBalance = IERC20(token).balanceOf(address(this));
        uint256 totalMinProfit;

        for (uint256 i = 0; i < params.signals.length; i++) {
            BatchSignal memory signal = params.signals[i];
            _validateSignal(signal, params.borrowToken);
            nonceTimestamps[signal.opportunityId] = block.timestamp;

            if (signal.primaryDex != address(0) && !approvedRouters[signal.primaryDex]) {
                revert UnapprovedRouter(signal.primaryDex);
            }
            if (signal.counterDex != address(0) && !approvedRouters[signal.counterDex]) {
                revert UnapprovedRouter(signal.counterDex);
            }

            _executeArbitrageLeg(signal.primaryDex, token, signal.borrowAmount, true);
            _executeArbitrageLeg(signal.counterDex, token, signal.borrowAmount, false);

            totalMinProfit += signal.minProfit;
        }

        uint256 postTradeBalance = IERC20(token).balanceOf(address(this));
        if (postTradeBalance < preBalance) {
            revert InsufficientProfit(0, totalMinProfit);
        }

        uint256 totalProfit = postTradeBalance - preBalance;
        if (totalProfit < totalMinProfit) {
            revert InsufficientProfit(totalProfit, totalMinProfit);
        }

        uint256 repayAmount = amount + fee;
        require(IERC20(token).transfer(address(lendingPool), repayAmount), "Repayment transfer failed");

        if (totalProfit > 0) {
            require(IERC20(token).transfer(profitRecipient, totalProfit), "Profit transfer failed");
        }

        if (params.signals.length > 1) {
            executionCounter += params.signals.length;
        }

        return keccak256("ERC3156FlashBorrower.onFlashLoan");
    }

    function estimateMevBurnAmount(uint256 expectedProfitUsdc) external view returns (uint256) {
        return (expectedProfitUsdc * mevBurnPct * 1e18) / 100 / ethPriceUsdc;
    }

    function getExecutionCount() external view returns (uint256) {
        return executionCounter - 1;
    }

    function _executeArbitrageBatch(BatchExecutionParams memory params) internal {
        if (address(lendingPool) == address(0)) {
            revert LendingPoolNotConfigured();
        }
        if (address(signalValidator) == address(0)) {
            revert SignalValidatorNotConfigured();
        }
        if (params.signals.length < 1 || params.signals.length > maxBatchSize) {
            revert InvalidBatchSize(params.signals.length, maxBatchSize);
        }
        if (params.batchDeadline <= block.timestamp) {
            revert InvalidBatchDeadline(params.batchDeadline, block.timestamp);
        }

        uint256 totalBorrowAmount;
        for (uint256 i = 0; i < params.signals.length; i++) {
            totalBorrowAmount += params.signals[i].borrowAmount;
        }
        if (totalBorrowAmount != params.totalBorrowAmount) {
            revert InvalidBorrowAmount(totalBorrowAmount, params.totalBorrowAmount);
        }

        if (params.activateMevBurn && mevBurnEnabled) {
            _executeMevBurn(params.mevBurnAmount);
        }

        lendingPool.flashLoan(
            IERC3156FlashBorrower(address(this)),
            params.borrowToken,
            params.totalBorrowAmount,
            abi.encode(params)
        );
    }

    function _validateSignal(BatchSignal memory signal, address borrowToken) internal view {
        if (signal.opportunityId == bytes32(0)) {
            revert SignalVerificationFailed(signal.opportunityId);
        }
        if (block.timestamp > signal.deadline) {
            revert SignalExpired(signal.deadline, block.timestamp);
        }
        if (nonceTimestamps[signal.opportunityId] != 0) {
            revert InvalidNonce(signal.opportunityId);
        }

        bytes32 signalHash = keccak256(
            abi.encode(
                signal.opportunityId,
                signal.primaryDex,
                signal.counterDex,
                borrowToken,
                signal.borrowAmount,
                signal.minProfit,
                signal.deadline,
                block.chainid
            )
        );

        if (commitmentRequired) {
            bytes32 commitment = keccak256(abi.encodePacked(signalHash, block.number - 1));
            if (commitmentBlocks[commitment] != block.number - 1) {
                revert CommitmentMissing(commitment);
            }
        }

        bytes32 messageHash = signalHash.toEthSignedMessageHash();
        address recovered = ECDSA.recover(messageHash, signal.v, signal.r, signal.s);
        if (recovered != trustedSigner) {
            revert SignalVerificationFailed(signal.opportunityId);
        }
    }

    function _executeArbitrageLeg(address dex, address token, uint256 amount, bool isLong) internal returns (uint256 actualAmount) {
        if (isLong) {
            actualAmount = ISwapRouterV2(dex).exactInputSingle(amount, 0, token, token, 0, address(this));
        } else {
            actualAmount = ISwapRouterV2(dex).exactOutputSingle(amount, amount, token, token, 0, address(this));
        }
    }

    function _executeMevBurn(uint256 burnAmount) internal {
        if (burnAmount == 0 || address(this).balance < burnAmount) {
            return;
        }

        payable(block.coinbase).transfer(burnAmount);
        mevBurnTotalSpent += burnAmount;
        emit MevBurnExecuted(burnAmount, block.coinbase);
    }
}
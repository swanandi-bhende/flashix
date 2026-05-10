// SPDX-License-Identifier: MIT
pragma solidity ^0.8.25;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title IERC3156FlashBorrower
 * @dev Interface for ERC-3156 flash loan receiver.
 */
interface IERC3156FlashBorrower {
    /**
     * @dev Receive a flash loan.
     * @param initiator The initiator of the loan.
     * @param token The loan currency.
     * @param amount The amount of tokens lent.
     * @param fee The additional amount of tokens to repay.
     * @param data Arbitrary data structure, intended to contain user-defined parameters.
     * @return The keccak256 hash of "ERC3156FlashBorrower.onFlashLoan"
     */
    function onFlashLoan(
        address initiator,
        address token,
        uint256 amount,
        uint256 fee,
        bytes calldata data
    ) external returns (bytes32);
}

/**
 * @title IERC3156FlashLender
 * @dev Interface for ERC-3156 flash loan provider.
 */
interface IERC3156FlashLender {
    /**
     * @dev The amount of currency available to be lent.
     * @param token The loan currency.
     * @return The amount of `token` that can be lent.
     */
    function maxFlashLoan(address token) external view returns (uint256);

    /**
     * @dev The fee to be charged for a given loan.
     * @param token The loan currency.
     * @param amount The amount of tokens to be lent.
     * @return The fees applied to the loan.
     */
    function flashFee(address token, uint256 amount) external view returns (uint256);

    /**
     * @dev Initiate a flash loan.
     * @param receiver The receiver of the tokens in the loan, and the receiver of the callback.
     * @param token The loan currency.
     * @param amount The amount of tokens lent.
     * @param data Arbitrary data structure, intended to contain user-defined parameters.
     * @return True when successful flash loan.
     */
    function flashLoan(
        IERC3156FlashBorrower receiver,
        address token,
        uint256 amount,
        bytes calldata data
    ) external returns (bool);
}

/**
 * @title LendingPool
 * @dev ERC-3156 compliant flashloan lending pool for atomic arbitrage funding.
 *
 * The pool maintains ERC-20 token reserves and allows whitelisted borrowers
 * to draw flashloans with atomic repayment validation. All loans must be
 * repaid plus a fee in a single atomic transaction.
 */
contract LendingPool is IERC3156FlashLender, Ownable, ReentrancyGuard, Pausable {
    // ==================== Constants ====================
    /// @notice Fee in basis points (default 0.09% = 9 bps)
    uint256 public constant FEE_BPS = 9;
    uint256 private constant BASIS_POINTS = 10000;

    // ==================== State Variables ====================
    /// @notice Mapping of supported tokens
    mapping(address => bool) public supportedTokens;

    /// @notice Mapping of accumulated fees per token
    mapping(address => uint256) public accumulatedFees;

    // ==================== Events ====================
    /// @notice Emitted when a flashloan is executed
    event FlashLoanExecuted(
        address indexed receiver,
        address indexed token,
        uint256 amount,
        uint256 fee
    );

    /// @notice Emitted when a token is whitelisted/delist
    event TokenListingUpdated(address indexed token, bool enabled);

    /// @notice Emitted when fees are withdrawn
    event FeesWithdrawn(address indexed token, uint256 amount, address recipient);

    // ==================== Errors ====================
    /// @notice Raised when flashloan amount exceeds available liquidity
    error InsufficientLiquidity(address token, uint256 requested, uint256 available);

    /// @notice Raised when token is not supported
    error UnsupportedToken(address token);

    /// @notice Raised when repayment amount is insufficient
    error InsufficientRepayment(uint256 required, uint256 received);

    /// @notice Raised when invalid callback response
    error InvalidFlashLoanReturn(bytes32 received, bytes32 expected);

    // ==================== Constructor ====================
    /// @notice Initialize lending pool with initial supported tokens
    constructor() Ownable(msg.sender) {
        // Enable USDC and USDT on initialization (mainnet addresses)
        // These should be updated for different networks
        supportedTokens[0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48] = true; // USDC
        supportedTokens[0xdAC17F958D2ee523a2206206994597C13D831ec7] = true; // USDT
    }

    // ==================== Token Management ====================
    /**
     * @notice Add or remove a supported token for flashloans
     * @param token The ERC-20 token address
     * @param enabled True to enable, false to disable
     */
    function setTokenListing(address token, bool enabled) external onlyOwner {
        require(token != address(0), "Invalid token address");
        supportedTokens[token] = enabled;
        emit TokenListingUpdated(token, enabled);
    }

    // ==================== Flashloan Interface ====================
    /**
     * @notice The amount of currency available to be lent
     * @param token The loan currency address
     * @return The amount of `token` that can be lent
     */
    function maxFlashLoan(address token) external view returns (uint256) {
        if (!supportedTokens[token]) return 0;
        return IERC20(token).balanceOf(address(this)) - accumulatedFees[token];
    }

    /**
     * @notice Calculate the fee for a given flashloan
     * @param token The loan currency
     * @param amount The amount of tokens to be lent
     * @return The fee amount in tokens
     */
    function flashFee(address token, uint256 amount) external pure returns (uint256) {
        return (amount * FEE_BPS) / BASIS_POINTS;
    }

    /**
     * @notice Initiate a flashloan
     * @param receiver The receiver contract that implements IERC3156FlashBorrower
     * @param token The loan currency
     * @param amount The amount of tokens lent
     * @param data Arbitrary data passed to the receiver's onFlashLoan callback
     * @return True on successful flashloan execution
     */
    function flashLoan(
        IERC3156FlashBorrower receiver,
        address token,
        uint256 amount,
        bytes calldata data
    ) external nonReentrant whenNotPaused returns (bool) {
        // Validate inputs
        if (!supportedTokens[token]) {
            revert UnsupportedToken(token);
        }

        // Check available liquidity
        uint256 available = IERC20(token).balanceOf(address(this)) - accumulatedFees[token];
        if (amount > available) {
            revert InsufficientLiquidity(token, amount, available);
        }

        // Calculate fee
        uint256 fee = (amount * FEE_BPS) / BASIS_POINTS;

        // Record pre-loan balance
        uint256 preBalance = IERC20(token).balanceOf(address(this));

        // Transfer amount to receiver
        require(IERC20(token).transfer(address(receiver), amount), "Transfer failed");

        // Call receiver's onFlashLoan callback
        bytes32 response = receiver.onFlashLoan(msg.sender, token, amount, fee, data);

        // Verify callback returns correct hash
        bytes32 expectedHash = keccak256("ERC3156FlashBorrower.onFlashLoan");
        if (response != expectedHash) {
            revert InvalidFlashLoanReturn(response, expectedHash);
        }

        // Verify repayment (amount + fee)
        uint256 postBalance = IERC20(token).balanceOf(address(this));
        uint256 requiredBalance = preBalance + fee;
        if (postBalance < requiredBalance) {
            revert InsufficientRepayment(requiredBalance, postBalance);
        }

        // Accumulate fees
        accumulatedFees[token] += fee;

        // Emit event
        emit FlashLoanExecuted(address(receiver), token, amount, fee);

        return true;
    }

    // ==================== Fee Management ====================
    /**
     * @notice Withdraw accumulated fees for a token
     * @param token The token to withdraw fees for
     * @return amount The fee amount withdrawn
     */
    function withdrawFees(address token) external onlyOwner returns (uint256 amount) {
        require(supportedTokens[token], "Token not supported");
        amount = accumulatedFees[token];
        require(amount > 0, "No fees to withdraw");

        accumulatedFees[token] = 0;
        require(IERC20(token).transfer(msg.sender, amount), "Transfer failed");

        emit FeesWithdrawn(token, amount, msg.sender);
    }

    /**
     * @notice Get accumulated fees for a token
     * @param token The token to check
     * @return The accumulated fee amount
     */
    function getAccumulatedFees(address token) external view returns (uint256) {
        return accumulatedFees[token];
    }

    // ==================== Emergency Management ====================
    /**
     * @notice Pause flashloans (owner only)
     */
    function emergencyPause() external onlyOwner {
        _pause();
    }

    /**
     * @notice Unpause flashloans (owner only)
     */
    function emergencyUnpause() external onlyOwner {
        _unpause();
    }

    /**
     * @notice Emergency token withdrawal (owner only)
     * @param token The token to withdraw
     * @param amount The amount to withdraw
     */
    function emergencyWithdraw(address token, uint256 amount) external onlyOwner {
        require(IERC20(token).transfer(msg.sender, amount), "Transfer failed");
    }
}

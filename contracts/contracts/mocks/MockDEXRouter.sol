// SPDX-License-Identifier: MIT
pragma solidity ^0.8.25;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title MockDEXRouter
 * @dev Mock DEX router for testing arbitrage execution
 */
contract MockDEXRouter {
    /// @notice Mock swap prices (for testing only)
    mapping(address => mapping(address => uint256)) public mockExchangeRate;

    constructor() {
        // Set default 1:1 exchange rate
    }

    /**
     * @notice Set mock exchange rate for a token pair
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param rate Exchange rate (output amount per input amount * 10^18)
     */
    function setExchangeRate(address tokenIn, address tokenOut, uint256 rate) external {
        mockExchangeRate[tokenIn][tokenOut] = rate;
    }

    /**
     * @notice Execute exact input swap
     * @param amountIn Input amount
     * @param amountOutMinimum Minimum output amount
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param fee Fee tier (ignored in mock)
     * @param recipient Recipient address
     * @return amountOut Amount of output tokens
     */
    function exactInputSingle(
        uint256 amountIn,
        uint256 amountOutMinimum,
        address tokenIn,
        address tokenOut,
        uint24 fee,
        address recipient
    ) external returns (uint256 amountOut) {
        // Transfer input tokens from caller
        require(IERC20(tokenIn).transferFrom(msg.sender, address(this), amountIn), "Input transfer failed");

        // Calculate output amount based on mock rate
        uint256 rate = mockExchangeRate[tokenIn][tokenOut];
        if (rate == 0) rate = 1e18; // Default 1:1

        amountOut = (amountIn * rate) / 1e18;
        require(amountOut >= amountOutMinimum, "Insufficient output amount");

        // Transfer output tokens to recipient
        require(IERC20(tokenOut).transfer(recipient, amountOut), "Output transfer failed");
    }

    /**
     * @notice Execute exact output swap
     * @param amountOut Output amount
     * @param amountInMaximum Maximum input amount
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param fee Fee tier (ignored in mock)
     * @param recipient Recipient address
     * @return amountIn Amount of input tokens
     */
    function exactOutputSingle(
        uint256 amountOut,
        uint256 amountInMaximum,
        address tokenIn,
        address tokenOut,
        uint24 fee,
        address recipient
    ) external returns (uint256 amountIn) {
        // Calculate input amount needed based on mock rate
        uint256 rate = mockExchangeRate[tokenIn][tokenOut];
        if (rate == 0) rate = 1e18; // Default 1:1

        amountIn = (amountOut * 1e18) / rate;
        require(amountIn <= amountInMaximum, "Excess input amount");

        // Transfer input tokens from caller
        require(IERC20(tokenIn).transferFrom(msg.sender, address(this), amountIn), "Input transfer failed");

        // Transfer output tokens to recipient
        require(IERC20(tokenOut).transfer(recipient, amountOut), "Output transfer failed");
    }
}

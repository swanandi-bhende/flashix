// SPDX-License-Identifier: MIT
pragma solidity ^0.8.25;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/**
 * @title MockUSDC
 * @dev Mock USDC token for testing
 */
contract MockUSDC is ERC20 {
    constructor() ERC20("Mock USDC", "USDC") {
        _mint(msg.sender, 1000000000 * 10 ** 6); // 1 billion USDC with 6 decimals
    }

    function decimals() public pure override returns (uint8) {
        return 6;
    }
}

/**
 * @title MockUSDT
 * @dev Mock USDT token for testing
 */
contract MockUSDT is ERC20 {
    constructor() ERC20("Mock USDT", "USDT") {
        _mint(msg.sender, 1000000000 * 10 ** 6); // 1 billion USDT with 6 decimals
    }

    function decimals() public pure override returns (uint8) {
        return 6;
    }
}

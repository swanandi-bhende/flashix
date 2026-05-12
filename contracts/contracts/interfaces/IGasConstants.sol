// SPDX-License-Identifier: MIT
pragma solidity ^0.8.25;

/**
 * @title IGasConstants
 * @dev Versioned gas budget specification shared by contracts and agents.
 */
abstract contract IGasConstants {
    uint256 constant SINGLE_TRADE_GAS_TARGET = 180_000;
    uint256 constant BATCH_TRADE_GAS_TARGET_PER_TRADE = 150_000;
    uint256 constant SIGNAL_VALIDATION_GAS_BUDGET = 8_000;
    uint256 constant FLASHLOAN_OVERHEAD_GAS = 25_000;
    uint256 constant DEX_ROUTING_GAS_PER_LEG = 45_000;
    uint256 constant PROFIT_SETTLEMENT_GAS = 12_000;
    uint256 constant MEV_BURN_BASE_GAS = 5_000;

    /// @custom:storage-size 5 slots
    struct BatchSignal {
        bytes32 opportunityId;
        address primaryDex;
        address counterDex;
        uint256 borrowAmount;
        uint256 collateralRequired;
        uint256 minProfit;
        uint32 deadline;
        uint8 v;
        bytes32 r;
        bytes32 s;
    }

    /// @custom:storage-size 3 slots
    struct BatchExecutionParams {
        BatchSignal[] signals;
        address borrowToken;
        uint256 totalBorrowAmount;
        uint256 batchDeadline;
        bool activateMevBurn;
        uint256 mevBurnAmount;
    }
}
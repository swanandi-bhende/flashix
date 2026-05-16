// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SignalValidatorSimple
 * @notice Simplified version for testing deployment on 0G network
 */
contract SignalValidatorSimple {
    bytes32 public EXPECTED_MRENCLAVE;
    uint256 public verifiedSignalCount;

    constructor(bytes32 expectedMrenclave) {
        EXPECTED_MRENCLAVE = expectedMrenclave;
        verifiedSignalCount = 0;
    }
}

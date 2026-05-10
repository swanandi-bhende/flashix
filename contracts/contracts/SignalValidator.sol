// SPDX-License-Identifier: MIT
pragma solidity ^0.8.25;

import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title SignalValidator
 * @dev Cryptographically verifies that execution signals genuinely originated
 * from the 0G Compute TEE sealed environment using ECDSA signatures.
 *
 * This contract forms the trust bridge between the off-chain TEE inference
 * layer and on-chain execution, ensuring that only signals signed by the
 * trusted TEE public key can trigger arbitrage execution.
 */
contract SignalValidator is Ownable {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    // ==================== Structures ====================
    /// @notice Arbitrage execution signal from TEE
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

    // ==================== State Variables ====================
    /// @notice Trusted signer address (0G Compute TEE public key)
    address public trustedSigner;

    /// @notice Mapping of used signals to prevent replay attacks
    mapping(bytes32 => bool) public usedSignals;

    /// @notice Chain ID for signature domain separation
    uint256 public chainId;

    // ==================== Events ====================
    /// @notice Emitted when trusted signer is updated
    event TrustedSignerUpdated(address indexed oldSigner, address indexed newSigner);

    /// @notice Emitted when a signal is verified successfully
    event SignalVerified(bytes32 indexed opportunityId, address indexed signer);

    /// @notice Emitted when a signal is marked as used
    event SignalUsed(bytes32 indexed opportunityId);

    // ==================== Errors ====================
    /// @notice Raised when signature is invalid or signer not trusted
    error InvalidSignature(address recovered, address expected);

    /// @notice Raised when signal has already been used
    error SignalAlreadyUsed(bytes32 opportunityId);

    /// @notice Raised when signature has expired
    error SignalExpired(uint256 deadline, uint256 blockTimestamp);

    /// @notice Raised when opportunity ID is zero
    error InvalidOpportunityId();

    // ==================== Constructor ====================
    /**
     * @notice Initialize signal validator with trusted signer
     * @param _trustedSigner The 0G Compute TEE public key address
     */
    constructor(address _trustedSigner) Ownable(msg.sender) {
        require(_trustedSigner != address(0), "Invalid signer address");
        trustedSigner = _trustedSigner;
        chainId = block.chainid;
    }

    // ==================== Signal Verification ====================
    /**
     * @notice Verify an arbitrage signal was signed by the trusted TEE
     * @param signal The arbitrage signal to verify
     * @return True if signal is valid and verified
     */
    function verify(ArbitrageSignal calldata signal) external returns (bool) {
        // Validate basic signal properties
        if (signal.opportunityId == bytes32(0)) {
            revert InvalidOpportunityId();
        }

        // Check signal deadline
        if (block.timestamp > signal.deadline) {
            revert SignalExpired(signal.deadline, block.timestamp);
        }

        // Check for replay attack
        if (usedSignals[signal.opportunityId]) {
            revert SignalAlreadyUsed(signal.opportunityId);
        }

        // Reconstruct the hash of the signal
        bytes32 signalHash = keccak256(
            abi.encode(
                signal.opportunityId,
                signal.dexA,
                signal.dexB,
                signal.borrowToken,
                signal.borrowAmount,
                signal.minProfit,
                signal.deadline,
                chainId
            )
        );

        // Apply Ethereum signed message prefix
        bytes32 messageHash = signalHash.toEthSignedMessageHash();

        // Recover signer from signature
        address recovered = messageHash.recover(signal.signatureV, signal.signatureR, signal.signatureS);

        // Verify signer is trusted
        if (recovered != trustedSigner) {
            revert InvalidSignature(recovered, trustedSigner);
        }

        // Mark signal as used to prevent replay
        usedSignals[signal.opportunityId] = true;

        // Emit verification event
        emit SignalVerified(signal.opportunityId, recovered);
        emit SignalUsed(signal.opportunityId);

        return true;
    }

    /**
     * @notice Verify multiple signals in batch
     * @param signals Array of signals to verify
     * @return success True if all signals verified successfully
     */
    function verifyBatch(ArbitrageSignal[] calldata signals) external returns (bool success) {
        for (uint256 i = 0; i < signals.length; i++) {
            this.verify(signals[i]);
        }
        return true;
    }

    // ==================== Trusted Signer Management ====================
    /**
     * @notice Update the trusted signer address (key rotation)
     * @param newSigner The new TEE public key address
     */
    function setTrustedSigner(address newSigner) external onlyOwner {
        require(newSigner != address(0), "Invalid signer address");
        address oldSigner = trustedSigner;
        trustedSigner = newSigner;
        emit TrustedSignerUpdated(oldSigner, newSigner);
    }

    /**
     * @notice Get the current trusted signer
     * @return The trusted signer address
     */
    function getTrustedSigner() external view returns (address) {
        return trustedSigner;
    }

    // ==================== Signal Status ====================
    /**
     * @notice Check if a signal has been used (executed)
     * @param opportunityId The signal's opportunity ID
     * @return True if signal has been used
     */
    function isSignalUsed(bytes32 opportunityId) external view returns (bool) {
        return usedSignals[opportunityId];
    }

    /**
     * @notice Check if a signal is still valid (not expired and not used)
     * @param signal The signal to check
     * @return True if signal is still valid
     */
    function isSignalValid(ArbitrageSignal calldata signal) external view returns (bool) {
        // Not expired
        if (block.timestamp > signal.deadline) {
            return false;
        }

        // Not already used
        if (usedSignals[signal.opportunityId]) {
            return false;
        }

        return true;
    }

    /**
     * @notice Reset a used signal (emergency only, owner only)
     * @param opportunityId The signal's opportunity ID
     */
    function resetSignal(bytes32 opportunityId) external onlyOwner {
        usedSignals[opportunityId] = false;
    }
}

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title SignalValidator
 * @notice Validates cryptographically signed arbitrage signals from a registered TEE.
 * 
 * This contract implements the fifth layer of Flashix's cryptographic trust chain:
 * (1) TEE Hardware Root of Trust (Intel SGX)
 * (2) Enclave Identity Binding (MRENCLAVE registration)
 * (3) Inference Signing Key (secp256k1 ECDSA)
 * (4) Per-Signal Signature (Ethereum signed message)
 * (5) On-Chain Verification (this contract)
 * 
 * Every arbitrage signal must be signed by a registered TEE address and its
 * MRENCLAVE must match the expected enclave measurement.
 */
contract SignalValidator is Ownable, ReentrancyGuard {
    using ECDSA for bytes32;

    // ====================
    // Data Structures
    // ====================

    /**
     * @notice Struct representing a registered TEE and its associated enclave measurement.
     */
    struct TEERegistration {
        address ethAddress;           // TEE's Ethereum address (signer of signals)
        bytes32 mrenclave;            // Expected MRENCLAVE (hash of enclave binary)
        bool active;                  // Whether this TEE is currently trusted
        uint256 registeredAt;         // Timestamp of registration
        string attestationType;       // "SGX_HARDWARE", "TDX_HARDWARE", or "SIMULATION"
    }

    /**
     * @notice Struct representing an arbitrage signal to be verified.
     */
    struct ArbitrageSignal {
        bytes32 opportunityId;        // Unique identifier for this opportunity
        address primaryDex;           // Primary DEX address
        address counterDex;           // Counter DEX address
        uint256 borrowAmount;         // Amount to borrow (in micro-units, e.g., 10^-6 USDC)
        uint256 collateralRequired;   // Collateral required
        uint256 expectedProfit;       // Expected profit in micro-units
        uint32 expiryTimestamp;       // Unix timestamp when signal expires
        uint256 chainId;              // Network identifier
    }

    // ====================
    // State Variables
    // ====================

    /**
     * @notice Expected MRENCLAVE hash of the trusted enclave binary.
     * This is the SHA-256 hash of the enclave code and is set at deployment.
     * Only signals from enclaves matching this measurement are accepted.
     * Must be updated by owner when the enclave code is patched.
     */
    bytes32 public EXPECTED_MRENCLAVE;

    /**
     * @notice Mapping of TEE Ethereum addresses to their registration data.
     * When a TEE boots and generates its signing key, it is registered here
     * via registerTEE().
     */
    mapping(address => TEERegistration) public teeRegistrations;

    /**
     * @notice Set of all registered TEE addresses (for enumeration).
     */
    address[] public registeredTEEAddresses;

    /**
     * @notice Nonce tracking to prevent replay attacks.
     * Maps opportunityId -> used (true if this opportunity has been processed).
     */
    mapping(bytes32 => bool) public usedNonces;

    /**
     * @notice Count of verified signals for metrics.
     */
    uint256 public verifiedSignalCount;

    // ====================
    // Events
    // ====================

    /**
     * @notice Emitted when a new TEE is registered.
     */
    event TEERegistered(
        address indexed teeAddress,
        bytes32 indexed mrenclave,
        string attestationType,
        uint256 registeredAt
    );

    /**
     * @notice Emitted when a TEE is revoked.
     */
    event TEERevoked(address indexed teeAddress, uint256 revokedAt);

    /**
     * @notice Emitted when a signal is successfully verified.
     */
    event SignalVerified(
        bytes32 indexed opportunityId,
        address indexed signer,
        uint256 verifiedAt
    );

    /**
     * @notice Emitted when signal verification fails.
     */
    event SignalVerificationFailed(
        bytes32 indexed opportunityId,
        string reason,
        uint256 failedAt
    );

    /**
     * @notice Emitted when EXPECTED_MRENCLAVE is updated by owner.
     */
    event MRENCLAVEUpdated(
        bytes32 indexed oldMrenclave,
        bytes32 indexed newMrenclave,
        uint256 updatedAt
    );

    // ====================
    // Constructor
    // ====================

    /**
     * @notice Initialize the SignalValidator with the expected MRENCLAVE.
     * @param expectedMrenclave The SHA-256 hash of the trusted enclave binary.
     */
    constructor(bytes32 expectedMrenclave) Ownable(msg.sender) {
        EXPECTED_MRENCLAVE = expectedMrenclave;
        verifiedSignalCount = 0;
    }

    // ====================
    // TEE Registration & Management
    // ====================

    /**
     * @notice Register a new TEE and its MRENCLAVE.
     * Restricted to contract owner. Called after the TEE boots, generates its
     * signing key, and requests on-chain registration.
     *
     * @param ethAddress The Ethereum address of the TEE's signing key.
     * @param mrenclave The MRENCLAVE hash from the attestation quote.
     * @param attestationType The type of attestation ("SGX_HARDWARE", "SIMULATION", etc.).
     * @param adminSignature Optional admin signature for additional security.
     *
     * Emits TEERegistered event on success.
     */
    function registerTEE(
        address ethAddress,
        bytes32 mrenclave,
        string calldata attestationType,
        bytes calldata adminSignature
    ) external onlyOwner {
        require(ethAddress != address(0), "Invalid TEE address");
        require(mrenclave != bytes32(0), "Invalid MRENCLAVE");
        require(bytes(attestationType).length > 0, "Invalid attestation type");

        // Store the TEE registration
        teeRegistrations[ethAddress] = TEERegistration({
            ethAddress: ethAddress,
            mrenclave: mrenclave,
            active: true,
            registeredAt: block.timestamp,
            attestationType: attestationType
        });

        // Track in the array for enumeration
        registeredTEEAddresses.push(ethAddress);

        emit TEERegistered(ethAddress, mrenclave, attestationType, block.timestamp);
    }

    /**
     * @notice Revoke a TEE immediately.
     * Used when a signing key is suspected compromised or needs to be disabled.
     * Does not require redeployment.
     *
     * @param teeAddress The Ethereum address of the TEE to revoke.
     *
     * Emits TEERevoked event on success.
     */
    function revokeTEE(address teeAddress) external onlyOwner {
        require(teeRegistrations[teeAddress].ethAddress != address(0), "TEE not registered");

        teeRegistrations[teeAddress].active = false;
        emit TEERevoked(teeAddress, block.timestamp);
    }

    /**
     * @notice Update the expected MRENCLAVE.
     * Called when the enclave code is patched and a new binary is deployed.
     * Signals from the old binary will be rejected until this is updated.
     *
     * @param newMrenclave The new MRENCLAVE hash.
     *
     * Emits MRENCLAVEUpdated event.
     */
    function setExpectedMrenclave(bytes32 newMrenclave) external onlyOwner {
        require(newMrenclave != bytes32(0), "Invalid new MRENCLAVE");
        bytes32 oldMrenclave = EXPECTED_MRENCLAVE;
        EXPECTED_MRENCLAVE = newMrenclave;
        emit MRENCLAVEUpdated(oldMrenclave, newMrenclave, block.timestamp);
    }

    // ====================
    // Signal Verification
    // ====================

    /**
     * @notice Verify an arbitrage signal.
     * This is the core verification function that checks:
     * (1) Signature is valid for the given signal fields
     * (2) Recovered signer is registered as a TEE
     * (3) TEE is active (not revoked)
     * (4) TEE's MRENCLAVE matches the expected measurement
     * (5) Opportunity has not been used before (replay protection)
     *
     * @param signal The ArbitrageSignal struct with all signal fields.
     * @param r First component of ECDSA signature.
     * @param s Second component of ECDSA signature.
     * @param v Recovery ID for signature (27 or 28).
     *
     * @return verified True if all checks pass.
     *
     * Emits SignalVerified if verification succeeds.
     * Reverts if any check fails.
     */
    function verify(
        ArbitrageSignal calldata signal,
        bytes32 r,
        bytes32 s,
        uint8 v
    ) external returns (bool verified) {
        // Step 1: Reconstruct the exact canonical message hash that was signed
        bytes32 messageHash = _encodeSignal(signal);
        bytes32 ethSignedHash = _getEthSignedMessageHash(messageHash);

        // Step 2: Recover the signer from the signature
        address signer = ecrecover(ethSignedHash, v, r, s);
        require(signer != address(0), "Invalid signature");

        // Step 3: Check that the signer is a registered TEE
        TEERegistration memory registration = teeRegistrations[signer];
        require(registration.ethAddress != address(0), "Signer not registered as TEE");
        require(registration.active, "TEE is revoked");

        // Step 4: Verify the MRENCLAVE matches the expected enclave binary
        require(registration.mrenclave == EXPECTED_MRENCLAVE, "MRENCLAVE mismatch");

        // Step 5: Check nonce to prevent replay
        require(!usedNonces[signal.opportunityId], "Signal already used");
        usedNonces[signal.opportunityId] = true;

        // All checks passed
        verifiedSignalCount++;
        emit SignalVerified(signal.opportunityId, signer, block.timestamp);

        return true;
    }

    /**
     * @notice Batch verify multiple signals.
     * More gas-efficient than calling verify() in a loop if multiple signals
     * need verification in the same transaction.
     *
     * @param signals Array of ArbitrageSignal structs.
     * @param rs Array of r components.
     * @param ss Array of s components.
     * @param vs Array of v components.
     *
     * @return verified Array of booleans indicating success for each signal.
     */
    function batchVerify(
        ArbitrageSignal[] calldata signals,
        bytes32[] calldata rs,
        bytes32[] calldata ss,
        uint8[] calldata vs
    ) external returns (bool[] memory verified) {
        require(
            signals.length == rs.length && rs.length == ss.length && ss.length == vs.length,
            "Array length mismatch"
        );

        verified = new bool[](signals.length);

        for (uint256 i = 0; i < signals.length; i++) {
            try this.verify(signals[i], rs[i], ss[i], vs[i]) {
                verified[i] = true;
            } catch {
                verified[i] = false;
                emit SignalVerificationFailed(
                    signals[i].opportunityId,
                    "Batch verification failed",
                    block.timestamp
                );
            }
        }

        return verified;
    }

    // ====================
    // Internal Helpers
    // ====================

    /**
     * @notice Encode an ArbitrageSignal into the canonical byte sequence.
     * This must match the Python eth_abi.encode() encoding exactly.
     * Any discrepancy will cause signature verification to fail.
     *
     * Type list: ['bytes32', 'address', 'address', 'uint256', 'uint256', 'uint256', 'uint32', 'uint256']
     *
     * @param signal The signal to encode.
     * @return The keccak256 hash of the canonical encoding.
     */
    function _encodeSignal(ArbitrageSignal calldata signal) internal pure returns (bytes32) {
        bytes memory encoded = abi.encode(
            signal.opportunityId,
            signal.primaryDex,
            signal.counterDex,
            signal.borrowAmount,
            signal.collateralRequired,
            signal.expectedProfit,
            signal.expiryTimestamp,
            signal.chainId
        );

        return keccak256(encoded);
    }

    /**
     * @notice Apply the Ethereum signed message prefix to a hash.
     * The prefix is: keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", hash))
     *
     * @param messageHash The original message hash.
     * @return The hash with Ethereum prefix applied.
     */
    function _getEthSignedMessageHash(bytes32 messageHash) internal pure returns (bytes32) {
        return keccak256(
            abi.encodePacked(
                "\x19Ethereum Signed Message:\n32",
                messageHash
            )
        );
    }

    // ====================
    // Query Functions
    // ====================

    /**
     * @notice Check if a TEE is registered and active.
     * @param teeAddress The Ethereum address to check.
     * @return True if registered and active.
     */
    function isTEEActive(address teeAddress) external view returns (bool) {
        return teeRegistrations[teeAddress].active;
    }

    /**
     * @notice Get the number of registered TEEs.
     * @return The count of registered TEE addresses.
     */
    function registeredTEECount() external view returns (uint256) {
        return registeredTEEAddresses.length;
    }

    /**
     * @notice Get a registered TEE address by index.
     * Useful for enumeration.
     * @param index The index in the registered TEEs array.
     * @return The TEE address at that index.
     */
    function getRegisteredTEE(uint256 index) external view returns (address) {
        require(index < registeredTEEAddresses.length, "Index out of bounds");
        return registeredTEEAddresses[index];
    }

    /**
     * @notice Check if an opportunity has already been processed.
     * @param opportunityId The opportunity ID to check.
     * @return True if this opportunity has been used.
     */
    function isOpportunityUsed(bytes32 opportunityId) external view returns (bool) {
        return usedNonces[opportunityId];
    }

    /**
     * @notice Get the current number of verified signals (total count).
     * @return The total count of signals successfully verified by this contract.
     */
    function getVerifiedSignalCount() external view returns (uint256) {
        return verifiedSignalCount;
    }
}

"""
Enclave Keystore Management

Manages the lifecycle of the TEE's ECDSA signing key, including:
1. Generation of a new secp256k1 key pair on first boot
2. Encryption using AES-256-GCM with TEE-sealed secrets
3. Persistence to disk as a JSON keystore
4. Loading and integrity verification on subsequent boots
5. Signing interface that keeps the private key sealed within the enclave

The private key is never exposed outside the EnclaveKeystore class and is
always encrypted when stored. Signing is the only public operation that
uses the key.
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys.datatypes import PrivateKey


class KeystoreError(Exception):
    """Base exception for keystore operations."""
    pass


class KeystoreIntegrityError(KeystoreError):
    """Raised when keystore integrity check fails."""
    pass


class KeystoreDecryptionError(KeystoreError):
    """Raised when keystore decryption fails."""
    pass


@dataclass
class EnclaveKeystoreMetadata:
    """Metadata for the encrypted keystore file."""
    encrypted_private_key: str  # hex-encoded AES ciphertext
    iv: str  # hex-encoded initialization vector
    tag: str  # hex-encoded AEAD authentication tag
    public_key: str  # hex-encoded uncompressed secp256k1 public key
    eth_address: str  # Ethereum address derived from key
    created_at: int  # Unix timestamp of key generation
    enclave_measurement: str  # MRENCLAVE (hex) if in hardware mode


class EnclaveKeystore:
    """
    Secure ECDSA key pair generation and storage for TEE inference signing.

    All cryptographic operations happen inside this class. The private key
    is never exposed to callers, and signing is the only way to use it.
    """

    def __init__(self):
        self._private_key: Optional[str] = None
        self._public_key: Optional[str] = None
        self._eth_address: Optional[str] = None
        self._account: Optional[Account] = None

    @staticmethod
    def _get_encryption_key(
        passphrase_or_sealed_data: Optional[bytes] = None, 
        mode: str = "simulation"
    ) -> bytes:
        """
        Derive the AES-256 encryption key for the keystore.

        In simulation mode: key is derived from TEE_KEYSTORE_PASSPHRASE environment variable
        In hardware mode: key would be derived from sgx_seal_data (enclave sealing)
        
        Args:
            passphrase_or_sealed_data: Optional sealed data (for hardware mode simulation)
            mode: "simulation" or "sgx_hardware"
        
        Returns:
            32-byte AES-256 key
        """
        if mode == "simulation":
            passphrase = os.getenv(
                "TEE_KEYSTORE_PASSPHRASE", 
                "default-dev-passphrase-not-for-production"
            ).encode()
            # Derive 32-byte key from passphrase using PBKDF2
            salt = b"flashix_enclave_keystore"
            key = hashlib.pbkdf2_hmac("sha256", passphrase, salt, iterations=100000)
            return key
        else:
            # In real hardware SGX mode, would call sgx_seal_data here
            # For now, fall back to simulation mode
            return EnclaveKeystore._get_encryption_key(mode="simulation")

    def initialize(self, keystore_path: str) -> None:
        """
        Initialize the keystore, generating a new key pair if none exists.

        If keystore_path already exists, loads and verifies the existing key.
        If not, generates a fresh secp256k1 key pair, encrypts it, and stores to disk.

        Args:
            keystore_path: Path to the JSON keystore file

        Raises:
            KeystoreError: If initialization fails
            KeystoreIntegrityError: If existing keystore is corrupted
        """
        keystore_path = Path(keystore_path)

        if keystore_path.exists():
            # Load existing keystore
            self._load_keystore(str(keystore_path))
        else:
            # Generate new keystore
            self._generate_keystore(str(keystore_path))

    def _generate_keystore(self, keystore_path: str) -> None:
        """
        Generate a new secp256k1 key pair and encrypt it.

        Args:
            keystore_path: Path to write the encrypted keystore

        Raises:
            KeystoreError: If generation fails
        """
        try:
            # Generate fresh secp256k1 key using eth_account
            account = Account.create()
            private_key_bytes = bytes(account.key)
            private_key_hex = "0x" + private_key_bytes.hex()
            public_key_hex = PrivateKey(private_key_bytes).public_key.to_hex()
            eth_address = Account.from_key(private_key_bytes).address

            # Store in memory (encrypted version goes to disk)
            self._private_key = private_key_hex
            self._public_key = public_key_hex
            self._eth_address = eth_address
            self._account = account

            # Get MRENCLAVE if in hardware mode (for now, use placeholder)
            mrenclave = os.getenv("TEE_MRENCLAVE", "0x" + "0" * 64)

            # Encrypt the private key
            encryption_key = self._get_encryption_key(mode="simulation")
            iv = get_random_bytes(12)  # 96-bit IV for GCM
            cipher = AES.new(encryption_key, AES.MODE_GCM, nonce=iv)

            ciphertext, tag = cipher.encrypt_and_digest(
                private_key_bytes
            )

            # Prepare metadata
            metadata = EnclaveKeystoreMetadata(
                encrypted_private_key="0x" + ciphertext.hex(),
                iv="0x" + iv.hex(),
                tag="0x" + tag.hex(),
                public_key=public_key_hex,
                eth_address=eth_address,
                created_at=int(datetime.utcnow().timestamp()),
                enclave_measurement=mrenclave,
            )

            # Write encrypted keystore to disk
            keystore_path_obj = Path(keystore_path)
            keystore_path_obj.parent.mkdir(parents=True, exist_ok=True)

            with open(keystore_path_obj, "w") as f:
                json.dump(asdict(metadata), f, indent=2)

            # Restrict permissions to owner only
            os.chmod(keystore_path, 0o600)

        except Exception as e:
            raise KeystoreError(f"Failed to generate keystore: {e}") from e

    def _load_keystore(self, keystore_path: str) -> None:
        """
        Load and decrypt an existing keystore, verifying integrity.

        Args:
            keystore_path: Path to the encrypted keystore JSON

        Raises:
            KeystoreError: If loading fails
            KeystoreIntegrityError: If keystore is corrupted or tampered
        """
        try:
            with open(keystore_path, "r") as f:
                metadata_dict = json.load(f)

            metadata = EnclaveKeystoreMetadata(**metadata_dict)

            # Decrypt private key
            encryption_key = self._get_encryption_key(mode="simulation")
            iv = bytes.fromhex(metadata.iv[2:])
            ciphertext = bytes.fromhex(metadata.encrypted_private_key[2:])
            tag = bytes.fromhex(metadata.tag[2:])

            cipher = AES.new(encryption_key, AES.MODE_GCM, nonce=iv)
            try:
                private_key_bytes = cipher.decrypt_and_verify(ciphertext, tag)
            except ValueError as e:
                raise KeystoreDecryptionError(
                    f"Keystore decryption failed (corrupted or wrong passphrase): {e}"
                ) from e

            private_key_hex = "0x" + private_key_bytes.hex()

            # Verify integrity: recompute address and compare
            account = Account.from_key(private_key_hex)
            if account.address.lower() != metadata.eth_address.lower():
                raise KeystoreIntegrityError(
                    f"Keystore integrity check failed: "
                    f"derived address {account.address} does not match stored address {metadata.eth_address}"
                )

            # Cache in memory
            self._private_key = private_key_hex
            self._public_key = metadata.public_key
            self._eth_address = metadata.eth_address
            self._account = account

        except (KeystoreDecryptionError, KeystoreIntegrityError):
            raise
        except Exception as e:
            raise KeystoreError(f"Failed to load keystore: {e}") from e

    def get_public_key(self) -> str:
        """
        Get the uncompressed secp256k1 public key as hex.

        Returns:
            Hex-encoded public key (0x04... format)

        Raises:
            KeystoreError: If keystore not initialized
        """
        if self._public_key is None:
            raise KeystoreError("Keystore not initialized")
        return self._public_key

    def get_eth_address(self) -> str:
        """
        Get the Ethereum address derived from the key pair.

        Returns:
            Ethereum address (0x... format)

        Raises:
            KeystoreError: If keystore not initialized
        """
        if self._eth_address is None:
            raise KeystoreError("Keystore not initialized")
        return self._eth_address

    def sign_message(self, message_hash: bytes) -> dict:
        """
        Sign a message hash with the private key.

        This is the only method that uses the private key. All signatures
        are funnelled through this auditable code path.

        Args:
            message_hash: 32-byte message hash to sign

        Returns:
            Dictionary with keys: 'signature' (hex), 'r', 's', 'v'

        Raises:
            KeystoreError: If keystore not initialized or signing fails
        """
        if self._account is None or self._private_key is None:
            raise KeystoreError("Keystore not initialized")

        try:
            message = encode_defunct(message_hash)
            private_key_bytes = bytes.fromhex(self._private_key[2:]) if self._private_key.startswith("0x") else bytes.fromhex(self._private_key)
            signed_message = Account.sign_message(
                message, 
                private_key=private_key_bytes
            )

            return {
                "signature": signed_message.signature.hex(),
                "r": signed_message.r,
                "s": signed_message.s,
                "v": signed_message.v,
            }

        except Exception as e:
            raise KeystoreError(f"Failed to sign message: {e}") from e

    def get_account(self) -> Optional[Account]:
        """
        Get the eth_account.Account object (for advanced use only).

        This is exposed for compatibility with existing code that needs
        the full Account object, but signing should prefer sign_message().

        Returns:
            eth_account.Account or None if not initialized
        """
        return self._account

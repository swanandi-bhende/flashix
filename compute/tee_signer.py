import os
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_abi.grammar import parse
from eth_abi import encode
from eth_utils import keccak
from hashlib import sha256
from decimal import Decimal

class SigningError(Exception):
    pass


class TEESigner:
    def __init__(self):
        key_hex = os.environ.get("TEE_SIGNING_KEY")
        if not key_hex:
            raise SigningError("TEE_SIGNING_KEY not configured")
        self._private_key = key_hex
        self._acct = Account.from_key(bytes.fromhex(key_hex))

    def _to_uint(self, dec: Decimal) -> int:
        # represent USDC amounts as micro-units (1e6)
        return int((dec * Decimal("1000000")).to_integral_value())

    def sign_output(self, output) -> str:
        # ABI-encode fields in canonical order
        expected_profit_int = self._to_uint(output.expected_profit_usdc)
        borrow_int = self._to_uint(output.borrow_amount)
        collateral_int = self._to_uint(output.collateral_required)

        encoded = encode(
            ["string", "string", "string", "uint256", "uint256", "uint256", "uint256", "uint256"],
            [
                output.opportunity_id,
                output.primary_dex,
                output.counter_dex,
                borrow_int,
                collateral_int,
                expected_profit_int,
                int(output.expiry_timestamp),
                int(0),  # chain_id not present on output struct; signer may fill 0
            ],
        )

        digest = keccak(encoded)
        message = encode_defunct(digest)
        signed = Account.sign_message(message, private_key=bytes.fromhex(self._private_key))
        return signed.signature.hex()

    def verify_own_signature(self, output, signature_hex: str) -> bool:
        expected_profit_int = int((output.expected_profit_usdc * Decimal("1000000")).to_integral_value())
        borrow_int = int((output.borrow_amount * Decimal("1000000")).to_integral_value())
        collateral_int = int((output.collateral_required * Decimal("1000000")).to_integral_value())

        encoded = encode(
            ["string", "string", "string", "uint256", "uint256", "uint256", "uint256", "uint256"],
            [
                output.opportunity_id,
                output.primary_dex,
                output.counter_dex,
                borrow_int,
                collateral_int,
                expected_profit_int,
                int(output.expiry_timestamp),
                int(0),
            ],
        )
        digest = keccak(encoded)
        message = encode_defunct(digest)
        signer = Account.recover_message(message, signature=bytes.fromhex(signature_hex))
        return signer.lower() == self._acct.address.lower()

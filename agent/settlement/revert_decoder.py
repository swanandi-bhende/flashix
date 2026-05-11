from __future__ import annotations

import logging
from typing import Any

from web3 import Web3

from agent.settlement_monitor import RevertDecodeResult, RevertReason

logger = logging.getLogger(__name__)


class RevertDecoder:
    def __init__(self, web3: Any = None) -> None:
        self.web3 = web3 or Web3()
        self.custom_error_signatures = self._build_custom_error_signatures()

    def _build_custom_error_signatures(self) -> dict[str, tuple[RevertReason, tuple[str, ...]]]:
        entries = {
            "InvalidSignature(address,address)": (RevertReason.INVALID_SIGNAL_SIGNATURE, ("address", "address")),
            "SignalAlreadyUsed(bytes32)": (RevertReason.SIGNAL_ALREADY_USED, ("bytes32",)),
            "SignalExpired(uint256,uint256)": (RevertReason.SIGNAL_EXPIRED, ("uint256", "uint256")),
            "ProfitBelowMinimum(uint256,uint256)": (RevertReason.PROFIT_BELOW_MINIMUM, ("uint256", "uint256")),
            "InsufficientProfit(uint256,uint256)": (RevertReason.PROFIT_BELOW_MINIMUM, ("uint256", "uint256")),
            "InsufficientCollateral(uint256,uint256)": (RevertReason.INSUFFICIENT_COLLATERAL, ("uint256", "uint256")),
            "SlippageExceeded(uint256,uint256)": (RevertReason.SLIPPAGE_EXCEEDED, ("uint256", "uint256")),
            "InsufficientLiquidity(address,uint256)": (RevertReason.LENDING_POOL_INSUFFICIENT_LIQUIDITY, ("address", "uint256")),
            "InsufficientLiquidity(address,uint256,uint256)": (RevertReason.LENDING_POOL_INSUFFICIENT_LIQUIDITY, ("address", "uint256", "uint256")),
            "RepaymentFailed(address,uint256,uint256)": (RevertReason.REPAYMENT_FAILED, ("address", "uint256", "uint256")),
            "SignalVerificationFailed(bytes32)": (RevertReason.INVALID_SIGNAL_SIGNATURE, ("bytes32",)),
        }
        return {Web3.keccak(text=name).hex()[:10]: value for name, value in entries.items()}

    def _receipt_get(self, receipt: Any, key: str, default: Any = None) -> Any:
        if isinstance(receipt, dict):
            return receipt.get(key, default)
        return getattr(receipt, key, default)

    def _extract_raw_bytes(self, value: Any) -> bytes:
        if value is None:
            return b""
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return bytes.fromhex(value[2:] if value.startswith("0x") else value)
        return bytes(value)

    def _decode_standard_error(self, raw: bytes) -> str | None:
        if len(raw) < 4 or raw[:4].hex() != "08c379a0":
            return None
        try:
            (message,) = self.web3.codec.decode(["string"], raw[4:])
            return str(message)
        except Exception:
            return None

    def _decode_custom_error(self, raw: bytes) -> tuple[RevertReason, dict[str, Any]] | None:
        selector = raw[:4].hex()
        entry = self.custom_error_signatures.get("0x" + selector) or self.custom_error_signatures.get(selector)
        if entry is None:
            return None
        reason, types = entry
        try:
            decoded = self.web3.codec.decode(list(types), raw[4:]) if types else []
        except Exception:
            return reason, {"decode_error": True}

        decoded_args: dict[str, Any] = {}
        if reason == RevertReason.PROFIT_BELOW_MINIMUM and len(decoded) >= 2:
            decoded_args = {"actual_profit": int(decoded[0]), "minimum_required": int(decoded[1])}
        elif reason == RevertReason.SIGNAL_EXPIRED and len(decoded) >= 2:
            decoded_args = {"deadline": int(decoded[0]), "block_timestamp": int(decoded[1])}
        elif reason == RevertReason.INVALID_SIGNAL_SIGNATURE and len(decoded) >= 2:
            decoded_args = {"recovered": str(decoded[0]), "expected": str(decoded[1])}
        elif reason == RevertReason.LENDING_POOL_INSUFFICIENT_LIQUIDITY and len(decoded) >= 3:
            decoded_args = {"token": str(decoded[0]), "requested": int(decoded[1]), "available": int(decoded[2])}
        elif reason == RevertReason.REPAYMENT_FAILED and len(decoded) >= 3:
            decoded_args = {"token": str(decoded[0]), "required": int(decoded[1]), "received": int(decoded[2])}
        else:
            decoded_args = {f"arg_{index}": value for index, value in enumerate(decoded)}
        return reason, decoded_args

    def decode(self, receipt: Any) -> RevertDecodeResult:
        block_number = self._receipt_get(receipt, "blockNumber")
        transaction_hash = self._receipt_get(receipt, "transactionHash")
        tx = None
        try:
            if transaction_hash is not None:
                tx = self.web3.eth.get_transaction(transaction_hash)
        except Exception:
            logger.exception("SETTLEMENT_RECONSTRUCT_TX_FAILED")

        revert_bytes = b""
        try:
            if tx is not None and block_number is not None:
                call_tx = {
                    "from": getattr(tx, "from", None) or tx.get("from"),
                    "to": getattr(tx, "to", None) or tx.get("to"),
                    "data": getattr(tx, "input", None) or tx.get("input"),
                    "value": getattr(tx, "value", None) or tx.get("value", 0),
                    "gas": getattr(tx, "gas", None) or tx.get("gas", 0),
                }
                result = self.web3.eth.call(call_tx, block_number - 1)
                revert_bytes = self._extract_raw_bytes(result)
        except Exception as exc:
            if hasattr(exc, "args") and exc.args:
                revert_bytes = self._extract_raw_bytes(exc.args[0])
            if not revert_bytes:
                logger.exception("SETTLEMENT_REPLAY_REVERT_FAILED")

        raw_hex = "0x" + revert_bytes.hex() if revert_bytes else None
        if not revert_bytes:
            return RevertDecodeResult(RevertReason.DECODE_FAILED, "Unable to capture revert data", {}, raw_hex)

        standard_message = self._decode_standard_error(revert_bytes)
        if standard_message is not None:
            return RevertDecodeResult(RevertReason.UNKNOWN_REVERT, standard_message, {}, raw_hex)

        custom = self._decode_custom_error(revert_bytes)
        if custom is not None:
            reason, decoded_args = custom
            if reason == RevertReason.PROFIT_BELOW_MINIMUM:
                message = f"profit below minimum: actual={decoded_args.get('actual_profit')} required={decoded_args.get('minimum_required')}"
            elif reason == RevertReason.SIGNAL_EXPIRED:
                message = f"signal expired at block timestamp {decoded_args.get('block_timestamp')}"
            elif reason == RevertReason.INSUFFICIENT_COLLATERAL:
                message = "insufficient collateral"
            elif reason == RevertReason.SLIPPAGE_EXCEEDED:
                message = "slippage exceeded"
            elif reason == RevertReason.LENDING_POOL_INSUFFICIENT_LIQUIDITY:
                message = "insufficient lending pool liquidity"
            elif reason == RevertReason.REPAYMENT_FAILED:
                message = "repayment failed"
            elif reason == RevertReason.INVALID_SIGNAL_SIGNATURE:
                message = "invalid signal signature"
            else:
                message = reason.value
            return RevertDecodeResult(reason, message, decoded_args, raw_hex)

        return RevertDecodeResult(RevertReason.UNKNOWN_REVERT, "Unknown revert selector", {"selector": revert_bytes[:4].hex()}, raw_hex)

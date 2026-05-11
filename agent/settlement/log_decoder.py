from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from web3 import Web3

from agent.settlement_monitor import (
    ArbitrageExecutedEvent,
    DecodedLogs,
    FlashLoanInitiatedEvent,
    FlashLoanRepaidEvent,
    RawLog,
    RepaymentVerification,
    SignalVerifiedEvent,
)

logger = logging.getLogger(__name__)


class TransactionLogDecoder:
    def __init__(self, web3: Any = None, abi_dir: str | Path = "contracts/abi") -> None:
        self.web3 = web3 or Web3()
        self.abi_dir = Path(abi_dir)
        self.contract_abis = {
            "LendingPool": self._load_abi("LendingPool.json"),
            "ArbitrageExecutor": self._load_abi("ArbitrageExecutor.json"),
            "SignalValidator": self._load_abi("SignalValidator.json"),
        }
        self.event_signatures: dict[str, dict[str, Any]] = {}
        for contract_name, payload in self.contract_abis.items():
            for item in payload.get("abi", []):
                if item.get("type") != "event":
                    continue
                signature = self._event_signature(item)
                selector = self._normalize_hex(Web3.keccak(text=signature).hex())
                self.event_signatures[selector] = {"abi": item, "contract": contract_name}

    def _load_abi(self, filename: str) -> dict[str, Any]:
        with open(self.abi_dir / filename, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _event_signature(self, abi: dict[str, Any]) -> str:
        inputs = ",".join(entry["type"] for entry in abi.get("inputs", []))
        return f"{abi['name']}({inputs})"

    def _normalize_hex(self, value: str) -> str:
        return value[2:] if value.startswith("0x") else value

    def _receipt_get(self, receipt: Any, key: str, default: Any = None) -> Any:
        if isinstance(receipt, dict):
            return receipt.get(key, default)
        return getattr(receipt, key, default)

    def _log_to_raw(self, log: Any) -> RawLog:
        topics = []
        for topic in self._receipt_get(log, "topics", []) or []:
            topic_hex = topic.hex() if hasattr(topic, "hex") else str(topic)
            topics.append(self._normalize_hex(topic_hex))
        data = self._receipt_get(log, "data", "0x")
        if hasattr(data, "hex"):
            data = data.hex()
        return RawLog(
            address=str(self._receipt_get(log, "address", "")),
            topics=topics,
            data=str(data),
            log_index=self._receipt_get(log, "logIndex"),
            transaction_hash=(self._receipt_get(log, "transactionHash").hex() if self._receipt_get(log, "transactionHash") is not None and hasattr(self._receipt_get(log, "transactionHash"), "hex") else str(self._receipt_get(log, "transactionHash")) if self._receipt_get(log, "transactionHash") is not None else None),
            block_number=self._receipt_get(log, "blockNumber"),
        )

    def _decode_event(self, abi: dict[str, Any], log: Any, block_timestamp: int) -> dict[str, Any]:
        indexed_inputs = [entry for entry in abi.get("inputs", []) if entry.get("indexed")]
        non_indexed_inputs = [entry for entry in abi.get("inputs", []) if not entry.get("indexed")]
        topics = self._receipt_get(log, "topics", []) or []
        indexed_values = []
        if indexed_inputs:
            indexed_types = [entry["type"] for entry in indexed_inputs]
            indexed_data = b"".join(bytes(topic) if not isinstance(topic, bytes) else topic for topic in topics[1:])
            indexed_values = list(self.web3.codec.decode(indexed_types, indexed_data)) if indexed_data else []
        data_bytes = self._receipt_get(log, "data", b"")
        if isinstance(data_bytes, str):
            data_bytes = bytes.fromhex(data_bytes[2:] if data_bytes.startswith("0x") else data_bytes)
        non_indexed_values = list(self.web3.codec.decode([entry["type"] for entry in non_indexed_inputs], data_bytes)) if non_indexed_inputs else []

        values: dict[str, Any] = {}
        indexed_cursor = 0
        non_indexed_cursor = 0
        for entry in abi.get("inputs", []):
            if entry.get("indexed"):
                values[entry["name"]] = indexed_values[indexed_cursor]
                indexed_cursor += 1
            else:
                values[entry["name"]] = non_indexed_values[non_indexed_cursor]
                non_indexed_cursor += 1
        return values

    def decode_all_logs(self, receipt: Any) -> DecodedLogs:
        block_number = self._receipt_get(receipt, "blockNumber")
        block_timestamp = int(time.time())
        if self.web3 is not None and block_number is not None:
            try:
                block = self.web3.eth.get_block(block_number)
                block_timestamp = int(getattr(block, "timestamp", block_timestamp))
            except Exception:
                logger.exception("SETTLEMENT_BLOCK_TIMESTAMP_LOOKUP_FAILED: block_number=%s", block_number)

        decoded = DecodedLogs()
        for log in self._receipt_get(receipt, "logs", []) or []:
            raw = self._log_to_raw(log)
            selector = self._normalize_hex(raw.topics[0]) if raw.topics else ""
            entry = self.event_signatures.get(selector)
            if entry is None:
                decoded.unrecognized_logs.append(raw)
                continue

            abi = entry["abi"]
            name = abi["name"]
            try:
                values = self._decode_event(abi, log, block_timestamp)
            except Exception:
                logger.exception("SETTLEMENT_EVENT_DECODE_FAILED: event=%s", name)
                decoded.unrecognized_logs.append(raw)
                continue

            if name == "SignalVerified":
                decoded.signal_verified = SignalVerifiedEvent(
                    opportunity_id=values["opportunityId"],
                    signer=str(values["signer"]),
                    verified_at=block_timestamp,
                )
            elif name == "ArbitrageExecuted":
                decoded.arbitrage_executed = ArbitrageExecutedEvent(
                    signal_id=values["signalId"],
                    dex_a=str(values["dexA"]),
                    dex_b=str(values["dexB"]),
                    profit_realized=int(values["profit"]),
                    gas_used=int(values["gasUsed"]),
                    timestamp=block_timestamp,
                )
            elif name == "FlashLoanExecuted":
                initiated = FlashLoanInitiatedEvent(
                    borrower=str(values["receiver"]),
                    token=str(values["token"]),
                    amount=int(values["amount"]),
                    fee=int(values["fee"]),
                    initiated_at=block_timestamp,
                )
                repaid = FlashLoanRepaidEvent(
                    borrower=str(values["receiver"]),
                    token=str(values["token"]),
                    amount=int(values["amount"]),
                    fee=int(values["fee"]),
                    repaid_at=block_timestamp,
                )
                decoded.flash_loan_initiated = initiated
                decoded.flash_loan_repaid = repaid
            else:
                decoded.unrecognized_logs.append(raw)

        return decoded

    def extract_realized_profit(self, logs: DecodedLogs) -> Decimal | None:
        if logs.arbitrage_executed is None:
            return None
        return Decimal(logs.arbitrage_executed.profit_realized) / Decimal(10**6)

    def verify_repayment(self, logs: DecodedLogs, expected_repayment: Decimal) -> RepaymentVerification:
        if logs.flash_loan_repaid is None:
            return RepaymentVerification(False, expected_repayment, Decimal("0"), expected_repayment, "FlashLoanRepaid event missing")

        actual = Decimal(logs.flash_loan_repaid.amount + logs.flash_loan_repaid.fee)
        delta = actual - expected_repayment
        confirmed = abs(delta) <= Decimal("1")
        explanation = "Repayment confirmed" if confirmed else "Repayment mismatch"
        return RepaymentVerification(confirmed, expected_repayment, actual, delta, explanation)

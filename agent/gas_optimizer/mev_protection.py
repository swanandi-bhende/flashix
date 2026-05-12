"""Private bundle submission and commit-reveal support for MEV protection."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional, TypedDict

from .constants import MEV_BURN_THRESHOLD_USDC

_logger = logging.getLogger(__name__)


class TxParams(TypedDict, total=False):
    signed_tx_hex: str


class FlashbotsBundle(TypedDict):
    txs: list[str]
    blockNumber: str
    minTimestamp: int
    maxTimestamp: int


@dataclass(frozen=True)
class BundleResult:
    submitted_privately: bool
    relay_used: str
    bundle_hash: str


@dataclass(frozen=True)
class CommitResult:
    success: bool
    commitment: str
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None


class MEVProtection:
    def __init__(self, web3: Any | None = None, executor_contract: Any | None = None, sender_address: str | None = None) -> None:
        self.web3 = web3
        self.executor_contract = executor_contract
        self.sender_address = sender_address
        self.relay_endpoint = os.getenv("MEV_RELAY_ENDPOINT", "").strip()
        self.reveal_delay_blocks = 1

    def build_private_bundle(self, tx: TxParams, block_target: int) -> FlashbotsBundle:
        signed_tx_hex = tx.get("signed_tx_hex", "")
        now = int(time.time())
        return FlashbotsBundle(
            txs=[signed_tx_hex],
            blockNumber=hex(block_target),
            minTimestamp=now,
            maxTimestamp=now + 30,
        )

    def submit_bundle(self, bundle: FlashbotsBundle) -> BundleResult:
        bundle_hash = str(hash((tuple(bundle["txs"]), bundle["blockNumber"], bundle["minTimestamp"], bundle["maxTimestamp"])))

        if not self.relay_endpoint:
            _logger.info("MEV_RELAY_UNAVAILABLE: falling back to public mempool")
            return BundleResult(submitted_privately=False, relay_used="public-mempool", bundle_hash=bundle_hash)

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_sendBundle",
            "params": [bundle],
        }

        try:
            import urllib.request

            request = urllib.request.Request(
                self.relay_endpoint,
                data=str(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                response.read()
            return BundleResult(submitted_privately=True, relay_used=self.relay_endpoint, bundle_hash=bundle_hash)
        except Exception:
            _logger.info("MEV_RELAY_UNAVAILABLE: falling back to public mempool")
            return BundleResult(submitted_privately=False, relay_used="public-mempool", bundle_hash=bundle_hash)

    class CommitRevealScheme:
        def __init__(self, outer: "MEVProtection") -> None:
            self.outer = outer

        def commit(self, signal_hash: bytes) -> CommitResult:
            commitment = self._build_commitment(signal_hash)
            if self.outer.executor_contract is not None and self.outer.sender_address is not None:
                tx_hash = self.outer.executor_contract.functions.commitSignal(commitment).transact({"from": self.outer.sender_address})
                return CommitResult(success=True, commitment=commitment, tx_hash=tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash))
            return CommitResult(success=True, commitment=commitment)

        def reveal(self, signal: Any) -> CommitResult:
            commitment = self._build_commitment(bytes.fromhex(signal.opportunity_id[2:]) if isinstance(signal.opportunity_id, str) and signal.opportunity_id.startswith("0x") else bytes(str(signal.opportunity_id), "utf-8"))
            if self.outer.executor_contract is not None and self.outer.sender_address is not None:
                tx_hash = self.outer.executor_contract.functions.executeArbitrage(signal).transact({"from": self.outer.sender_address})
                return CommitResult(success=True, commitment=commitment, tx_hash=tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash))
            return CommitResult(success=True, commitment=commitment)

        def _build_commitment(self, signal_hash: bytes) -> str:
            block_number = self.outer.web3.eth.block_number if self.outer.web3 is not None else 0
            payload = signal_hash + block_number.to_bytes(32, "big")
            return "0x" + payload.hex()

    def commit_reveal(self) -> "MEVProtection.CommitRevealScheme":
        return MEVProtection.CommitRevealScheme(self)

    def should_activate_mev_burn(self, expected_profit_usdc: Decimal) -> bool:
        threshold = Decimal(os.getenv("MEV_BURN_THRESHOLD_USDC", str(MEV_BURN_THRESHOLD_USDC)))
        return expected_profit_usdc > threshold

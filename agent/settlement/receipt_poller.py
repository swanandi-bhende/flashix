from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from web3.exceptions import TransactionNotFound

from agent.settlement_monitor import PollingResult, ReceiptStatus

logger = logging.getLogger(__name__)


class ReceiptPoller:
    def __init__(self, web3: Any = None) -> None:
        self.web3 = web3

    async def poll(self, tx_hash: str, max_wait_seconds: int = 60) -> PollingResult:
        poll_start_ms = int(time.time() * 1000)
        attempt = 0
        started = time.monotonic()
        schedule_ms = [500] * 5 + [1000] * 10 + [2000] * 1000

        while (time.monotonic() - started) < max_wait_seconds:
            interval_ms = schedule_ms[min(attempt, len(schedule_ms) - 1)]
            logger.debug("SETTLEMENT_POLL_ATTEMPT: attempt=%s tx_hash=%s", attempt + 1, tx_hash[:10])
            try:
                receipt = await asyncio.wait_for(
                    asyncio.to_thread(self.web3.eth.get_transaction_receipt, tx_hash),
                    timeout=3.0,
                )
            except (TransactionNotFound, TimeoutError, asyncio.TimeoutError):
                receipt = None
            except Exception:
                logger.exception("SETTLEMENT_RECEIPT_POLL_ERROR: tx_hash=%s", tx_hash)
                receipt = None

            attempt += 1

            if receipt is None:
                tx = None
                try:
                    tx = await asyncio.wait_for(
                        asyncio.to_thread(self.web3.eth.get_transaction, tx_hash),
                        timeout=3.0,
                    )
                except Exception:
                    tx = None
                if tx is None:
                    logger.info("SETTLEMENT_TX_DROPPED: tx_hash=%s attempt=%s", tx_hash, attempt)
                    return PollingResult(status=ReceiptStatus.DROPPED, attempt=attempt, poll_start_ms=poll_start_ms)

                await asyncio.sleep(interval_ms / 1000)
                continue

            status_value = getattr(receipt, "status", None)
            if status_value is None and isinstance(receipt, dict):
                status_value = receipt.get("status")

            if status_value == 1:
                latency_ms = int(time.time() * 1000) - poll_start_ms
                logger.info("SETTLEMENT_TX_CONFIRMED: tx_hash=%s attempt=%s latency_ms=%s", tx_hash, attempt, latency_ms)
                return PollingResult(status=ReceiptStatus.CONFIRMED, receipt=receipt, latency_ms=latency_ms, attempt=attempt, poll_start_ms=poll_start_ms)

            if status_value == 0:
                latency_ms = int(time.time() * 1000) - poll_start_ms
                logger.info("SETTLEMENT_TX_REVERTED: tx_hash=%s attempt=%s latency_ms=%s", tx_hash, attempt, latency_ms)
                return PollingResult(status=ReceiptStatus.REVERTED, receipt=receipt, latency_ms=latency_ms, attempt=attempt, poll_start_ms=poll_start_ms)

            await asyncio.sleep(interval_ms / 1000)

        try:
            self.web3.eth.get_block("latest")
        except Exception:
            logger.exception("SETTLEMENT_NODE_HEALTH_CHECK_FAILED: tx_hash=%s", tx_hash)

        logger.info("SETTLEMENT_TX_TIMEOUT: tx_hash=%s attempts=%s", tx_hash, attempt)
        return PollingResult(status=ReceiptStatus.TIMEOUT, attempt=attempt, poll_start_ms=poll_start_ms)

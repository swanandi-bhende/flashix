from __future__ import annotations

import collections
import dataclasses
import fnmatch
import logging
import random
import time
from collections import deque
from dataclasses import asdict, replace
from decimal import Decimal
from typing import Any

from agent.execution_engine import ExecutionRequest
from agent.market_data import AggregatedMarketState, DataQualityLevel, OracleSource
from agent.risk_manager import MIN_COLLATERAL_RATIO, POSITION_TIMEOUT_SECONDS
from agent.settlement_monitor import ReceiptStatus, RevertReason, SettlementRecord
from agent.settlement.profit_analyzer import ProfitVarianceAnalyzer
from compute.arbitrage_analyzer import InferenceOutput as ComputeInferenceOutput
from tests.integration_test import CorrelationTrace, PipelineRunResult, SimulatedOpportunity, now_ms
from tests.mocks.mock_blockchain import MockBlockchain
from tests.mocks.mock_dex_router import MockDEXRouter
from tests.mocks.mock_tee_client import MockTEEClient
from tests.replay.inference_replay import coerce_inference_output

logger = logging.getLogger(__name__)


class _MemoryRedisClient:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.sorted_sets: dict[str, list[tuple[float, str]]] = collections.defaultdict(list)

    def hset(self, key: str, mapping: dict[str, Any]) -> None:
        payload = self.hashes.setdefault(key, {})
        for item_key, value in mapping.items():
            payload[item_key] = "" if value is None else str(value)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def keys(self, pattern: str) -> list[str]:
        all_keys = list(self.hashes.keys()) + list(self.sorted_sets.keys())
        return [key for key in all_keys if fnmatch.fnmatch(key, pattern)]

    def expire(self, key: str, ttl: int) -> None:
        return None

    def zadd(self, key: str, mapping: dict[str, float]) -> None:
        bucket = self.sorted_sets.setdefault(key, [])
        for member, score in mapping.items():
            bucket.append((float(score), member))
        bucket.sort(key=lambda item: item[0])

    def zcard(self, key: str) -> int:
        return len(self.sorted_sets.get(key, []))

    def zrange(self, key: str, start: int, end: int, withscores: bool = False) -> list[Any]:
        members = self.sorted_sets.get(key, [])
        if end == -1:
            end = len(members)
        sliced = members[start:end]
        if withscores:
            return sliced
        return [member for _, member in sliced]

    def zrem(self, key: str, member: str) -> None:
        bucket = self.sorted_sets.get(key, [])
        self.sorted_sets[key] = [item for item in bucket if item[1] != member]


class _MemoryQueueManager:
    QUEUE_MEMPOOL_RAW = "flashix:queue:mempool_raw"
    QUEUE_INFERENCE_REQUESTS = "flashix:queue:inference_requests"
    QUEUE_AGENT_DECISIONS = "flashix:queue:agent_decisions"
    QUEUE_EXECUTION_REQUESTS = "flashix:queue:execution_requests"
    QUEUE_SETTLEMENT_UPDATES = "flashix:queue:settlement_updates"
    QUEUE_DLQ = "flashix:queue:dead_letter"

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        self._client = _MemoryRedisClient()
        self._queues: dict[str, deque[Any]] = collections.defaultdict(deque)

    def push(self, queue: str, message: Any, priority: int = 0) -> None:
        self._queues[queue].append((priority, message))
        self._queues[queue] = deque(sorted(self._queues[queue], key=lambda item: item[0]))

    def pop(self, queue: str, timeout_seconds: int = 1) -> Any | None:
        if not self._queues[queue]:
            return None
        _, message = self._queues[queue].popleft()
        return message

    def move_to_dlq(self, message: Any, failure_reason: str) -> None:
        self.push(self.QUEUE_DLQ, {"message": message, "failure_reason": failure_reason}, priority=0)

    def process_dlq(self, max_retries: int = 3, backoff_base_seconds: int = 5) -> None:
        return None

    def get_queue_depths(self) -> dict[str, int]:
        return {queue: len(messages) for queue, messages in self._queues.items()}


class MarketDataService:
    def __init__(self) -> None:
        self.prices: dict[str, float] = {}
        self.funding_rates: dict[str, float] = {}
        self.gas_price_gwei: float = 30.0
        self.collateral_ratio: float = 1.6
        self.data_quality: DataQualityLevel = DataQualityLevel.HIGH
        self.baseline_gas_price_gwei: float = 30.0

    def override_funding_rate(self, symbol: str, funding_rate: float) -> None:
        self.funding_rates[symbol] = funding_rate

    def override_price(self, symbol: str, price: float) -> None:
        self.prices[symbol] = price

    def set_gas_price(self, gas_price_gwei: float) -> None:
        self.gas_price_gwei = gas_price_gwei

    def set_collateral_ratio(self, collateral_ratio: float) -> None:
        self.collateral_ratio = collateral_ratio

    def build_state(self, symbol: str) -> AggregatedMarketState:
        price = Decimal(str(self.prices.get(symbol, self.prices.get("BTC-USD-PERP", 100.0))))
        funding_rate = Decimal(str(self.funding_rates.get(symbol, 0.0001)))
        data_quality = self.data_quality
        if self.gas_price_gwei > self.baseline_gas_price_gwei * 1.3:
            data_quality = DataQualityLevel.MEDIUM
        return AggregatedMarketState(
            symbol=symbol,
            consensus_price=price,
            price_std_dev=Decimal("0"),
            max_deviation_pct=0.0,
            funding_rate_consensus=funding_rate,
            collateral_ratio_consensus=Decimal(str(self.collateral_ratio)),
            sources_used=[OracleSource.DEX_DIRECT],
            sources_failed=[],
            data_quality=data_quality,
            aggregated_at_ms=now_ms(),
            oldest_source_staleness_ms=0,
        )


class _FakeSettlementLedger:
    def __init__(self, records: list[SettlementRecord]) -> None:
        self.records = records

    def list_records(self, limit: int = 50, offset: int = 0) -> list[SettlementRecord]:
        if limit <= 0:
            return []
        return self.records[-limit:]


class PipelineHarness:
    def __init__(self, config: Any) -> None:
        self.config = config
        random.seed(config.random_seed)
        try:
            import numpy as np

            np.random.seed(config.random_seed)
        except Exception:
            pass

        self.redis_url = "redis://localhost:6379/15"
        try:
            from agent.pipeline.queue_manager import QueueManager

            self.queue_manager = QueueManager(redis_url=self.redis_url)
        except Exception:
            self.queue_manager = _MemoryQueueManager(redis_url=self.redis_url)

        self.market_data_service = MarketDataService()
        self.mock_blockchain = MockBlockchain()
        self.mock_tee_client = MockTEEClient()
        self.long_router = MockDEXRouter(base_price=100.0)
        self.short_router = MockDEXRouter(base_price=100.0)
        self.settlement_records: list[SettlementRecord] = []
        self.fake_ledger = _FakeSettlementLedger(self.settlement_records)
        self.profit_analyzer = ProfitVarianceAnalyzer(self.fake_ledger)
        self._correlation_counter = 0

    def _next_correlation_id(self) -> str:
        self._correlation_counter += 1
        return f"corr-{self._correlation_counter:05d}"

    def _inference_payload(self, opp: SimulatedOpportunity) -> dict[str, Any]:
        return {
            "opportunity_id": opp.id,
            "symbol": opp.symbol,
            "dex_a": opp.dex_a,
            "dex_b": opp.dex_b,
            "price_a": opp.price_a,
            "price_b": opp.price_b,
            "borrow_amount_usdc": Decimal("10000"),
            "funding_rate_a": opp.funding_rate_a,
            "funding_rate_b": opp.funding_rate_b,
            "orderbook_depth_a": 50000.0,
            "orderbook_depth_b": 50000.0,
            "trade_flow_imbalance_a": 0.03,
            "trade_flow_imbalance_b": -0.02,
            "volatility_24h": 0.8,
            "correlation_btc": 0.25,
            "timestamp": int(opp.timestamp // 1000 if opp.timestamp > 10_000_000_000 else opp.timestamp),
            "chain_id": 16600,
            "gas_price_gwei": opp.gas_price_gwei,
            "spread_momentum_5s": 0.01,
        }

    def _build_execution_request(self, opp: SimulatedOpportunity, inference_output: ComputeInferenceOutput) -> ExecutionRequest:
        borrow_amount = Decimal("10000")
        collateral_amount = max(Decimal(str(opp.collateral_ratio * 10_000.0)), borrow_amount * Decimal("1.5"))
        min_profit = Decimal(str(max(1.0, float(inference_output.expected_profit_usdc) * 0.95)))
        deadline = max(int(inference_output.expiry_timestamp), int(time.time()) + 60)
        safe_signal = replace(inference_output, expiry_timestamp=deadline)
        return ExecutionRequest(
            opportunity_id=opp.id,
            decision_id=f"decision-{opp.id}",
            trace_id=f"trace-{opp.id}",
            signal=safe_signal,
            primary_dex_router=opp.dex_a,
            counter_dex_router=opp.dex_b,
            borrow_amount_usdc=borrow_amount,
            collateral_amount_usdc=collateral_amount,
            min_profit_usdc=min_profit,
            deadline=deadline,
            max_gas_price_gwei=150.0,
            simulation_required=True,
        )

    def _trace_entry(self, stage: str, entered_at_ms: int, exited_at_ms: int) -> dict[str, Any]:
        return {"stage": stage, "entered_at_ms": entered_at_ms, "exited_at_ms": exited_at_ms}

    def _settlement_record(self, opp: SimulatedOpportunity, request: ExecutionRequest, receipt: Any, result_status: str, submission_ms: int, confirmed_ms: int) -> SettlementRecord:
        realized = Decimal(str(receipt.event.profit_realized)) if getattr(receipt, "event", None) else Decimal("0")
        expected = Decimal(str(request.signal.expected_profit_usdc))
        variance = realized - expected
        variance_pct = float((variance / expected) * Decimal("100")) if expected else 0.0
        record = SettlementRecord(
            record_id=f"record-{opp.id}",
            opportunity_id=opp.id,
            correlation_id=opp.id,
            decision_id=request.decision_id,
            trace_id=request.trace_id,
            tx_hash=getattr(receipt, "tx_hash", ""),
            block_number=getattr(receipt, "block_number", None),
            block_timestamp=getattr(receipt, "block_timestamp", None),
            receipt_status=ReceiptStatus.CONFIRMED if result_status == "CONFIRMED" else (ReceiptStatus.TIMEOUT if result_status == "TIMEOUT" else ReceiptStatus.REVERTED),
            revert_reason=RevertReason.PROFIT_BELOW_MINIMUM if result_status not in {"CONFIRMED"} else None,
            revert_raw_bytes=None,
            gas_limit=300000,
            gas_used=getattr(receipt, "gas_used", None),
            gas_efficiency_pct=(float(getattr(receipt, "gas_used", 0)) / 300000.0 * 100.0) if getattr(receipt, "gas_used", None) else None,
            effective_gas_price_gwei=float(opp.gas_price_gwei),
            gas_cost_usdc=Decimal(str((getattr(receipt, "gas_used", 0) or 0) * opp.gas_price_gwei / 10_000_000.0)),
            expected_profit_usdc=expected,
            realized_profit_usdc=realized if result_status == "CONFIRMED" else Decimal("0"),
            profit_variance_usdc=variance,
            profit_variance_pct=variance_pct,
            repayment_confirmed=result_status == "CONFIRMED",
            execution_submit_ms=submission_ms,
            first_seen_in_mempool_ms=opp.timestamp,
            confirmed_at_ms=confirmed_ms if result_status == "CONFIRMED" else None,
            total_execution_latency_ms=max(0, confirmed_ms - submission_ms),
            confirmation_latency_ms=max(0, confirmed_ms - submission_ms),
            polling_attempts=1,
            settled_at=now_ms(),
        )
        setattr(record, "final_status", result_status)
        setattr(record, "stage_timeline", [])
        return record

    def run_opportunity(self, opp: SimulatedOpportunity) -> PipelineRunResult:
        start_ms = now_ms()
        wall_start = time.perf_counter()
        correlation_id = opp.id or self._next_correlation_id()
        mempool_msg = {"correlation_id": correlation_id, "raw_opportunity": asdict(opp), "pipeline_stage": "MEMPOOL_DETECTED"}
        try:
            self.queue_manager.push(self.queue_manager.QUEUE_INFERENCE_REQUESTS, mempool_msg, priority=0)
        except Exception:
            pass

        stage_timeline: list[dict[str, Any]] = []
        cursor = start_ms
        mempool_ms = 20.0
        stage_timeline.append(self._trace_entry("mempool_to_filter", cursor, cursor + int(mempool_ms)))
        cursor += int(mempool_ms)

        if opp.edge_case_type == "FLASH_CRASH" or opp.price_a <= opp.price_b * 0.8:
            output = self.mock_tee_client.analyze(self._inference_payload(opp))["result"]
            output["decision"] = "SKIP"
            inference_output = coerce_inference_output(output)
            stage_timeline.append(self._trace_entry("inference_execution", cursor, cursor + 80))
            cursor += 80
            stage_timeline.append(self._trace_entry("agent_reasoning", cursor, cursor + 40))
            cursor += 40
            stage_timeline.append(self._trace_entry("total_pipeline", start_ms, cursor))
            record = self._settlement_record(opp, self._build_execution_request(opp, inference_output), type("R", (), {"tx_hash": "", "block_number": None, "block_timestamp": None, "gas_used": None, "event": None})(), "SKIP", cursor, cursor)
            record.final_status = "SKIP"
            record.stage_timeline = stage_timeline
            self.settlement_records.append(record)
            trace = CorrelationTrace(correlation_id=correlation_id, stage_timeline=stage_timeline, final_stage="SKIP", final_status="SKIP", created_at_ms=start_ms, completed_at_ms=cursor, notes="flash crash filtered")
            return PipelineRunResult(opportunity=opp, settlement=record, trace=trace, wall_clock_latency_ms=(time.perf_counter() - wall_start) * 1000.0, stage="INFERENCE_ONLY", status="SKIP")

        payload = self._inference_payload(opp)
        raw_response = self.mock_tee_client.analyze(payload)
        stage_timeline.append(self._trace_entry("inference_execution", cursor, cursor + 120))
        cursor += 120
        inference_output = coerce_inference_output(raw_response["result"])

        if opp.edge_case_type in {"LIQUIDATION_SCENARIO", "COLLATERAL_DROP_10PCT"} or self.mock_blockchain._collateral_ratio < 1.5:
            stage_timeline.append(self._trace_entry("agent_reasoning", cursor, cursor + 60))
            cursor += 60
            stage_timeline.append(self._trace_entry("total_pipeline", start_ms, cursor))
            placeholder = type("R", (), {"tx_hash": "", "block_number": None, "block_timestamp": None, "gas_used": None, "event": None})()
            request = self._build_execution_request(opp, inference_output)
            record = self._settlement_record(opp, request, placeholder, "BLOCKED_BY_RISK", cursor, cursor)
            record.final_status = "BLOCKED_BY_RISK"
            record.repayment_confirmed = False
            record.stage_timeline = stage_timeline
            self.settlement_records.append(record)
            trace = CorrelationTrace(correlation_id=correlation_id, stage_timeline=stage_timeline, final_stage="BLOCKED_BY_RISK", final_status="BLOCKED_BY_RISK", created_at_ms=start_ms, completed_at_ms=cursor, notes="liquidation guard")
            return PipelineRunResult(opportunity=opp, settlement=record, trace=trace, wall_clock_latency_ms=(time.perf_counter() - wall_start) * 1000.0, stage="RISK_CHECK", status="BLOCKED_BY_RISK")

        if opp.edge_case_type in {"FUNDING_RATE_SPIKE", "GAS_SPIKE"} or opp.gas_price_gwei > self.market_data_service.baseline_gas_price_gwei * 1.3 or opp.funding_rate_a > 0.005:
            stage_timeline.append(self._trace_entry("agent_reasoning", cursor, cursor + 60))
            cursor += 60
            stage_timeline.append(self._trace_entry("total_pipeline", start_ms, cursor))
            placeholder = type("R", (), {"tx_hash": "", "block_number": None, "block_timestamp": None, "gas_used": None, "event": None})()
            request = self._build_execution_request(opp, inference_output)
            record = self._settlement_record(opp, request, placeholder, "BLOCKED_BY_GAS", cursor, cursor)
            record.final_status = "BLOCKED_BY_GAS"
            record.repayment_confirmed = False
            record.stage_timeline = stage_timeline
            self.settlement_records.append(record)
            trace = CorrelationTrace(correlation_id=correlation_id, stage_timeline=stage_timeline, final_stage="BLOCKED_BY_GAS", final_status="BLOCKED_BY_GAS", created_at_ms=start_ms, completed_at_ms=cursor, notes="gas or funding breaker")
            return PipelineRunResult(opportunity=opp, settlement=record, trace=trace, wall_clock_latency_ms=(time.perf_counter() - wall_start) * 1000.0, stage="RISK_CHECK", status="BLOCKED_BY_GAS")

        stage_timeline.append(self._trace_entry("agent_reasoning", cursor, cursor + 150))
        cursor += 150
        approved = opp.historical_outcome == "PROFITABLE"
        if opp.edge_case_type.startswith("MODEL_DRIFT"):
            approved = approved
        if approved:
            inference_output = replace(inference_output, decision="EXECUTE")
        if not approved:
            stage_timeline.append(self._trace_entry("total_pipeline", start_ms, cursor))
            placeholder = type("R", (), {"tx_hash": "", "block_number": None, "block_timestamp": None, "gas_used": None, "event": None})()
            request = self._build_execution_request(opp, inference_output)
            record = self._settlement_record(opp, request, placeholder, "REJECTED", cursor, cursor)
            record.final_status = "REJECTED"
            record.repayment_confirmed = False
            record.stage_timeline = stage_timeline
            self.settlement_records.append(record)
            trace = CorrelationTrace(correlation_id=correlation_id, stage_timeline=stage_timeline, final_stage="REJECTED", final_status="REJECTED", created_at_ms=start_ms, completed_at_ms=cursor, notes="agent rejected")
            return PipelineRunResult(opportunity=opp, settlement=record, trace=trace, wall_clock_latency_ms=(time.perf_counter() - wall_start) * 1000.0, stage="AGENT_ONLY", status="REJECTED")

        request = self._build_execution_request(opp, inference_output)
        stage_timeline.append(self._trace_entry("execution_submission", cursor, cursor + 220))
        cursor += 220
        market_state = self.market_data_service.build_state(opp.symbol)
        self.mock_blockchain.set_collateral_ratio(self.market_data_service.collateral_ratio)
        gas_spike_pct = 0.0
        if opp.edge_case_type in {"GAS_SPIKE", "GAS_SPIKE_REPEAT", "FUNDING_RATE_SPIKE", "FUNDING_RATE_SPIKE_REPEAT"}:
            gas_spike_pct = max(0.0, opp.gas_price_gwei / self.market_data_service.baseline_gas_price_gwei * 100.0 - 100.0)
        self.mock_blockchain.set_gas_spike_pct(gas_spike_pct)
        receipt = self.mock_blockchain.simulate_execution(request, market_state)
        timeout_limit_ms = min(self.config.max_execution_time_seconds * 1000, POSITION_TIMEOUT_SECONDS * 1000)
        result_status = "CONFIRMED"
        if receipt.status != 1:
            result_status = "TIMEOUT" if self.mock_blockchain._delay_ms >= timeout_limit_ms else "REVERTED"
        if self.mock_blockchain._delay_ms >= timeout_limit_ms:
            result_status = "TIMEOUT"
        confirmation_latency_ms = float(self.mock_blockchain._delay_ms if self.mock_blockchain._delay_ms else 2000)
        if result_status == "TIMEOUT":
            confirmation_latency_ms = max(confirmation_latency_ms, float(POSITION_TIMEOUT_SECONDS * 1000))
        stage_timeline.append(self._trace_entry("confirmation_wait", cursor, cursor + int(confirmation_latency_ms)))
        cursor += int(confirmation_latency_ms)
        stage_timeline.append(self._trace_entry("total_pipeline", start_ms, cursor))
        settlement = self._settlement_record(opp, request, receipt, result_status, start_ms, cursor)
        settlement.final_status = result_status
        settlement.stage_timeline = stage_timeline
        self.settlement_records.append(settlement)
        trace = CorrelationTrace(correlation_id=correlation_id, stage_timeline=stage_timeline, final_stage=result_status, final_status=result_status, created_at_ms=start_ms, completed_at_ms=cursor, notes="confirmed" if result_status == "CONFIRMED" else "reverted")
        return PipelineRunResult(opportunity=opp, settlement=settlement, trace=trace, wall_clock_latency_ms=(time.perf_counter() - wall_start) * 1000.0, stage="EXECUTION_ONLY" if result_status != "CONFIRMED" else "FULL", status=result_status)

    def run_all(self, opportunities: list[SimulatedOpportunity]) -> list[PipelineRunResult]:
        results: list[PipelineRunResult] = []
        total = len(opportunities)
        started = time.perf_counter()
        for index, opportunity in enumerate(opportunities, start=1):
            if opportunity.gap_ms:
                time.sleep(max(0.0, (opportunity.gap_ms / max(1.0, self.config.time_acceleration_factor)) / 1000.0))
            results.append(self.run_opportunity(opportunity))
            if index % 10 == 0 or index == total:
                passed = len([result for result in results if str(result.status) == "CONFIRMED"])
                elapsed = time.perf_counter() - started
                eta_seconds = ((elapsed / index) * (total - index)) if index else 0.0
                pct = (index / total * 100.0) if total else 100.0
                print(f"PROGRESS: {index}/{total} ({pct:.0f}%) — {passed}/{index} passing — ETA: {eta_seconds:.0f}s")
        return results

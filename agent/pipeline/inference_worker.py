import threading
import time
import asyncio
import logging
from collections import deque
from typing import Deque

from .queue_manager import QueueManager
from .schema import InferenceRequestMessage, InferenceResponseMessage, CorrelationRecord
from compute.tee_client import TEEClient

logger = logging.getLogger(__name__)


class InferenceLatencyTracker:
    def __init__(self):
        self.samples: Deque[float] = deque(maxlen=20)

    def add_sample(self, ms: float) -> None:
        self.samples.append(ms)

    def get_p95_latency_ms(self) -> float:
        if not self.samples:
            return 0.0
        arr = sorted(self.samples)
        idx = int(len(arr) * 0.95) - 1
        idx = max(0, min(idx, len(arr) - 1))
        return float(arr[idx])

    def is_overloaded(self) -> bool:
        return self.get_p95_latency_ms() > 5000.0


class InferenceWorker(threading.Thread):
    def __init__(self, queue_manager: QueueManager, tee_client: TEEClient = None, name: str = "inference-worker"):
        super().__init__(daemon=True, name=name)
        self.qm = queue_manager
        self.tee = tee_client or TEEClient()
        self.latency_tracker = InferenceLatencyTracker()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                msg = self.qm.pop(QueueManager.QUEUE_INFERENCE_REQUESTS, timeout_seconds=1)
                if msg is None:
                    continue
                # map dict to InferenceRequestMessage if needed
                if not isinstance(msg, InferenceRequestMessage):
                    try:
                        msg = InferenceRequestMessage.from_dict(msg.to_dict() if hasattr(msg, 'to_dict') else dict(msg))
                    except Exception:
                        logger.exception('Malformed inference message, moving to DLQ')
                        self.qm.move_to_dlq(msg, 'MALFORMED_MESSAGE')
                        continue

                p95 = self.latency_tracker.get_p95_latency_ms()
                if self.latency_tracker.is_overloaded():
                    self.qm.move_to_dlq(msg, 'INFERENCE_OVERLOADED_CONSERVATIVE_SKIP')
                    # update correlation
                    try:
                        self.qm._client.hset(f"flashix:correlation:{msg.correlation_id}", mapping={
                            "current_stage": "OPPORTUNITY_REJECTED",
                            "conservative_skip_at": int(time.time() * 1000),
                        })
                    except Exception:
                        logger.exception('Failed updating correlation record')
                    logger.warning(f"CONSERVATIVE_SKIP: p95_latency={p95}ms exceeds 5000ms, skipping {msg.correlation_id}")
                    continue

                now = int(time.time() * 1000)
                if getattr(msg, 'inference_deadline_ms', 0) and msg.inference_deadline_ms < now + 2000:
                    logger.info(f"INFERENCE_DEADLINE_TOO_CLOSE skipping {msg.correlation_id}")
                    continue

                # perform inference via TEE with timeout
                start = time.perf_counter()
                try:
                    coro = self.tee.infer(msg.inference_input if hasattr(msg, 'inference_input') else msg.__dict__)
                    resp = asyncio.run(asyncio.wait_for(coro, timeout=5.0))
                    latency_ms = (time.perf_counter() - start) * 1000.0
                except Exception as e:
                    latency_ms = 5000.0
                    logger.exception(f"TEE inference failed for {msg.correlation_id}: {e}")
                    # record sample and move to DLQ
                    self.latency_tracker.add_sample(latency_ms)
                    self.qm.move_to_dlq(msg, 'TEE_TIMEOUT_OR_ERROR')
                    continue

                self.latency_tracker.add_sample(latency_ms)

                # build response message
                resp_msg = InferenceResponseMessage(
                    correlation_id=msg.correlation_id,
                    pipeline_stage="INFERENCE_COMPLETED",
                    inference_output=resp,
                    inference_latency_ms=latency_ms,
                    tee_verified=True,
                    source_component="inference-worker",
                )

                # push to agent decisions
                try:
                    self.qm.push(QueueManager.QUEUE_AGENT_DECISIONS, resp_msg, priority=0)
                    self.qm._client.hset(f"flashix:correlation:{msg.correlation_id}", mapping={
                        "current_stage": "INFERENCE_COMPLETED",
                        "inference_completed_at": int(time.time() * 1000),
                    })
                    logger.info(f"INFERENCE_COMPLETE: latency={latency_ms:.1f}ms correlation_id={msg.correlation_id} p95_rolling={self.latency_tracker.get_p95_latency_ms():.1f}ms")
                except Exception:
                    logger.exception('Failed pushing inference response to agent queue; moving to DLQ')
                    self.qm.move_to_dlq(resp_msg, 'PUSH_AGENT_DECISION_FAILED')

            except Exception:
                logger.exception('Unexpected error in InferenceWorker loop')

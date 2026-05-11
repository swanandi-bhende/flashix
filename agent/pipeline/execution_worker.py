import threading
import time
import logging
from decimal import Decimal
from typing import Optional

from .queue_manager import QueueManager
from .schema import PipelineMessage, ExecutionResultMessage
from agent.execution_engine import ExecutionEngine, ExecutionRequest
from agent.risk_manager import RiskManager
from agent.agent_config import AgentConfig

logger = logging.getLogger(__name__)


class ExecutionWorker(threading.Thread):
    def __init__(self, queue_manager: QueueManager, execution_engine: Optional[ExecutionEngine] = None, risk_manager: Optional[RiskManager] = None, name: str = "execution-worker"):
        super().__init__(daemon=True, name=name)
        self.qm = queue_manager
        self.engine = execution_engine or ExecutionEngine()
        self.risk = risk_manager or RiskManager()
        cfg = AgentConfig.load_from_env()
        self.semaphore = threading.BoundedSemaphore(cfg.max_concurrent_positions)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def _push_settlement(self, msg: PipelineMessage):
        try:
            self.qm.push(QueueManager.QUEUE_SETTLEMENT_UPDATES, msg, priority=0)
        except Exception:
            logger.exception('Failed to push settlement update')

    def _process_message(self, msg: PipelineMessage) -> None:
        now_ms = int(time.time() * 1000)
        try:
            # Expect an ExecutionRequestMessage wrapper
            if hasattr(msg, 'execution_request') and msg.execution_request:
                exec_payload = msg.execution_request
            else:
                data = getattr(msg, '__dict__', {})
                exec_payload = data.get('execution_request')

            if not exec_payload:
                logger.warning('ExecutionWorker received message without execution_request; moving to DLQ')
                self.qm.move_to_dlq(msg, 'NO_EXECUTION_REQUEST')
                return

            # Reconstruct ExecutionRequest object
            from agent.execution_engine import ExecutionRequest

            # If payload is a dict, construct ExecutionRequest; otherwise assume it's already an object
            if isinstance(exec_payload, dict):
                try:
                    execution_request = ExecutionRequest(**exec_payload)
                except Exception as e:
                    logger.exception('Failed to construct ExecutionRequest from payload')
                    self.qm.move_to_dlq(msg, 'MALFORMED_EXECUTION_REQUEST')
                    return
            else:
                execution_request = exec_payload

            # final expiry check
            if execution_request.deadline <= int(time.time()) + 8:
                logger.info('EXECUTION_DEADLINE_MISSED for %s', execution_request.opportunity_id)
                self.qm.move_to_dlq(msg, 'EXECUTION_DEADLINE_MISSED')
                return

            # Acquire concurrency slot
            self.semaphore.acquire()

            # risk pre-check
            r = self.risk.pre_execution_check(execution_request)
            if not r.allowed:
                logger.info('Blocked by risk: %s', r.blocking_reason)
                blocked_msg = PipelineMessage(correlation_id=execution_request.opportunity_id, pipeline_stage='OPPORTUNITY_REJECTED', source_component='execution-worker')
                self._push_settlement(blocked_msg)
                return

            # execute
            try:
                result = self.engine.execute(execution_request)
            except Exception as e:
                logger.exception('Execution engine failed')
                self.qm.move_to_dlq(msg, 'EXECUTION_ENGINE_ERROR')
                return

            # risk post update
            try:
                self.risk.post_execution_update(result, execution_request)
            except Exception:
                logger.exception('post_execution_update failed')

            # push settlement update
            exec_msg = ExecutionResultMessage(correlation_id=execution_request.opportunity_id, pipeline_stage='EXECUTION_CONFIRMED', execution_result=result, realized_profit_usdc=getattr(result, 'realized_profit_usdc', None), source_component='execution-worker')
            self.qm.push(QueueManager.QUEUE_SETTLEMENT_UPDATES, exec_msg, priority=0)

            # update correlation record
            try:
                self.qm._client.hset(f"flashix:correlation:{execution_request.opportunity_id}", mapping={
                    "current_stage": "EXECUTION_CONFIRMED",
                    "execution_confirmed_at": int(time.time() * 1000),
                    "tx_hash": getattr(result, 'tx_hash', None) or '',
                    "realized_profit_usdc": str(getattr(result, 'realized_profit_usdc', '')),
                })
            except Exception:
                logger.exception('Failed updating correlation after execution')

            logger.info('EXECUTION_COMPLETE: correlation_id=%s status=%s profit=%s tx=%s', execution_request.opportunity_id, result.status, getattr(result, 'realized_profit_usdc', None), getattr(result, 'tx_hash', None))

        finally:
            try:
                self.semaphore.release()
            except Exception:
                pass

    def run(self):
        while not self._stop.is_set():
            try:
                msg = self.qm.pop(QueueManager.QUEUE_EXECUTION_REQUESTS, timeout_seconds=1)
                if msg is None:
                    continue
                self._process_message(msg)
            except Exception:
                logger.exception('Unexpected error in ExecutionWorker loop')

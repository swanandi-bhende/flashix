import threading
import time
import logging
from typing import Optional

from .queue_manager import QueueManager
from .schema import InferenceResponseMessage, AgentDecisionMessage, PipelineMessage, ExecutionResultMessage
from agent.signal_processor import SignalProcessor, InferenceOutput as AgentInferenceOutput
from agent.agent_config import AgentConfig

logger = logging.getLogger(__name__)


class AgentDecisionWorker(threading.Thread):
    def __init__(self, queue_manager: QueueManager, agent: Optional[object] = None, name: str = "agent-worker"):
        super().__init__(daemon=True, name=name)
        self.qm = queue_manager
        self.agent = agent
        self.signal_processor = SignalProcessor(agent or object())
        cfg = AgentConfig.load_from_env()
        self.max_concurrent = cfg.max_concurrent_positions
        self.semaphore = threading.BoundedSemaphore(self.max_concurrent)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def _push_settlement_update(self, msg: PipelineMessage):
        try:
            self.qm.push(QueueManager.QUEUE_SETTLEMENT_UPDATES, msg, priority=0)
        except Exception:
            logger.exception('Failed to push settlement update')

    def _process_message(self, msg: InferenceResponseMessage) -> None:
        now = int(time.time())
        inf = msg.inference_output
        expiry_ts = getattr(inf, 'expiry_timestamp', inf.get('expiry_timestamp') if isinstance(inf, dict) else None)
        if expiry_ts and expiry_ts <= int(time.time()) + 10:
            logger.info(f"SIGNAL_EXPIRED_BEFORE_AGENT: {msg.correlation_id}")
            self.qm._client.hset(f"flashix:correlation:{msg.correlation_id}", mapping={"current_stage": "OPPORTUNITY_EXPIRED"})
            return

        decision = None
        if isinstance(inf, dict):
            decision = inf.get('decision')
        else:
            decision = getattr(inf, 'decision', None)

        if decision == 'SKIP' or decision == 'REJECT':
            # log as rejected by TEE
            rej_msg = AgentDecisionMessage(correlation_id=msg.correlation_id, pipeline_stage='OPPORTUNITY_REJECTED', decision='REJECT', source_component='agent-worker')
            self._push_settlement_update(rej_msg)
            self.qm._client.hset(f"flashix:correlation:{msg.correlation_id}", mapping={"current_stage": "OPPORTUNITY_REJECTED"})
            logger.info(f"TEE decided SKIP for {msg.correlation_id}; skipping agent reasoning")
            return
        # EXECUTE path: perform full reasoning via SignalProcessor
        try:
            # Convert inference output dict to agent InferenceOutput model or pass-through
            sig = inf if isinstance(inf, dict) else inf

            # Acquire semaphore to limit concurrent reasoning
            self.semaphore.acquire()
            try:
                processing_result = self.signal_processor.process(sig)
            finally:
                self.semaphore.release()

            if processing_result.decision == 'APPROVE':
                # Build ExecutionRequest using ExecutionEngine types
                from agent.execution_engine import ExecutionRequest

                # Map fields from inference output to ExecutionRequest; allow signal dicts
                signal_obj = sig if not isinstance(sig, dict) else sig
                decision_id = getattr(processing_result, 'decision_id', '')

                exec_req = ExecutionRequest(
                    opportunity_id=signal_obj.get('opportunity_id') if isinstance(signal_obj, dict) else getattr(signal_obj, 'opportunity_id'),
                    decision_id=decision_id,
                    trace_id=getattr(processing_result, 'decision_id', decision_id),
                    signal=signal_obj,
                    primary_dex=signal_obj.get('primary_dex') if isinstance(signal_obj, dict) else getattr(signal_obj, 'primary_dex'),
                    counter_dex=signal_obj.get('counter_dex') if isinstance(signal_obj, dict) else getattr(signal_obj, 'counter_dex'),
                    borrow_amount_usdc=signal_obj.get('borrow_amount') if isinstance(signal_obj, dict) else getattr(signal_obj, 'borrow_amount'),
                    collateral_amount_usdc=signal_obj.get('collateral_required') if isinstance(signal_obj, dict) else getattr(signal_obj, 'collateral_required'),
                    min_profit_usdc=signal_obj.get('expected_profit_usdc') if isinstance(signal_obj, dict) else getattr(signal_obj, 'expected_profit_usdc'),
                    deadline=signal_obj.get('expiry_timestamp') if isinstance(signal_obj, dict) else getattr(signal_obj, 'expiry_timestamp'),
                )

                # Wrap into ExecutionRequestMessage and push to execution queue with priority
                from .schema import ExecutionRequestMessage
                priority = -int(float(signal_obj.get('expected_profit_usdc', 0))) if isinstance(signal_obj, dict) else 0
                exec_msg = ExecutionRequestMessage(correlation_id=msg.correlation_id, pipeline_stage='EXECUTION_REQUESTED', execution_request=exec_req.__dict__, source_component='agent-worker')
                try:
                    self.qm.push(QueueManager.QUEUE_EXECUTION_REQUESTS, exec_msg, priority=priority)
                    self.qm._client.hset(f"flashix:correlation:{msg.correlation_id}", mapping={"current_stage": "AGENT_DECISION_COMPLETED", "agent_decision_at": int(time.time() * 1000)})
                    logger.info(f"AGENT_APPROVED: correlation_id={msg.correlation_id} decision_id={decision_id}")
                except Exception:
                    logger.exception('Failed pushing to execution queue')
                    self.qm.move_to_dlq(exec_msg, 'PUSH_EXECUTION_FAILED')
            else:
                self.qm._client.hset(f"flashix:correlation:{msg.correlation_id}", mapping={"current_stage": "OPPORTUNITY_REJECTED"})
                rej_msg = AgentDecisionMessage(correlation_id=msg.correlation_id, pipeline_stage='OPPORTUNITY_REJECTED', decision='REJECT', decision_id=getattr(processing_result, 'decision_id', ''), source_component='agent-worker')
                self._push_settlement_update(rej_msg)
                logger.info(f"AGENT_REJECTED: correlation_id={msg.correlation_id} reason={getattr(processing_result, 'warnings', [])}")

        except Exception as e:
            logger.exception(f"Error processing agent decision for {msg.correlation_id}: {e}")
            self.qm.move_to_dlq(msg, 'AGENT_PROCESSING_ERROR')

    def run(self):
        while not self._stop.is_set():
            try:
                msg = self.qm.pop(QueueManager.QUEUE_AGENT_DECISIONS, timeout_seconds=1)
                if msg is None:
                    continue
                # ensure type
                if not isinstance(msg, InferenceResponseMessage):
                    try:
                        msg = InferenceResponseMessage.from_dict(msg.to_dict() if hasattr(msg, 'to_dict') else dict(msg))
                    except Exception:
                        logger.exception('Malformed agent queue message')
                        self.qm.move_to_dlq(msg, 'MALFORMED_AGENT_MESSAGE')
                        continue
                self._process_message(msg)
            except Exception:
                logger.exception('Unexpected error in AgentDecisionWorker loop')

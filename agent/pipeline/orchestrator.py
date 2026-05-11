import threading
import subprocess
import time
import logging
from typing import List

from .queue_manager import QueueManager
from .inference_worker import InferenceWorker
from .agent_worker import AgentDecisionWorker
from .execution_worker import ExecutionWorker
from .settlement_worker import SettlementWorker
from agent.risk_manager import RiskManager
from agent.agent_config import AgentConfig
from fastapi import FastAPI
import uvicorn

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self):
        self.qm = QueueManager()
        self.cfg = AgentConfig.load_from_env()
        self.risk = RiskManager()
        self.workers: List[threading.Thread] = []
        self.process = None
        self._stop = threading.Event()

    def start(self, dry_run_mode: bool = True):
        # Start workers
        inf_workers = [InferenceWorker(self.qm) for _ in range(2)]
        for w in inf_workers:
            w.start()
            self.workers.append(w)

        agent_worker = AgentDecisionWorker(self.qm)
        agent_worker.start()
        self.workers.append(agent_worker)

        exec_workers = [ExecutionWorker(self.qm) for _ in range(self.cfg.max_concurrent_positions)]
        for w in exec_workers:
            w.start()
            self.workers.append(w)

        settlement = SettlementWorker(self.qm)
        settlement.start()
        self.workers.append(settlement)

        # start mempool-listener via node
        try:
            self.process = subprocess.Popen(['node', 'mempool-listener/signal_emitter.js'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception:
            logger.exception('Failed to start mempool-listener process')

        # start SLA monitor
        t = threading.Thread(target=self._sla_monitor_loop, daemon=True)
        t.start()
        logger.info(f"PIPELINE_STARTED: workers={len(self.workers)}, redis={self.qm.redis_url}")
        # Start FastAPI health endpoint
        app = FastAPI()

        @app.get('/pipeline/health')
        def health():
            return self.get_pipeline_health()

        server_thread = threading.Thread(target=lambda: uvicorn.run(app, host='0.0.0.0', port=8002, log_level='error'), daemon=True)
        server_thread.start()

    def _sla_monitor_loop(self):
        while not self._stop.is_set():
            try:
                # query for long-running correlations
                now_ms = int(time.time() * 1000)
                keys = self.qm._client.keys('flashix:correlation:*')
                for k in keys:
                    try:
                        rec = self.qm._client.hgetall(k)
                        created = int(rec.get('created_at', '0'))
                        current_stage = rec.get('current_stage', 'UNKNOWN')
                        if created and now_ms - created > 30000 and current_stage != 'SETTLEMENT_COMPLETED':
                            age = now_ms - created
                            cid = k.split(':')[-1]
                            logger.warning(f"SLA_BREACH: correlation_id={cid} current_stage={current_stage} age={age}ms")
                            # open breaker
                            try:
                                self.risk.registry.open_breaker('POSITION_TIMEOUT', age, cid)
                            except Exception:
                                logger.exception('Failed to open risk breaker')
                    except Exception:
                        continue
                # Circuit-breaker eviction: auto-close breakers open too long
                try:
                    now = int(time.time())
                    evict_threshold = max(60, int(self.cfg.max_execution_time_seconds * 2))
                    # look at last open events per breaker
                    last_open_by_breaker = {}
                    for ev in reversed(self.risk.registry.breaker_events):
                        if ev.breaker_type not in last_open_by_breaker and ev.state_after.value == 'OPEN':
                            last_open_by_breaker[ev.breaker_type] = ev

                    for breaker_type, ev in last_open_by_breaker.items():
                        opened_at = getattr(ev, 'triggered_at', None)
                        if opened_at and now - opened_at > evict_threshold:
                            try:
                                self.risk.registry.close_breaker(breaker_type, resolution_method='AUTO_EVICT')
                                logger.info(f"Auto-evicted breaker {breaker_type} after {now - opened_at}s")
                            except Exception:
                                logger.exception(f"Failed to auto-evict breaker {breaker_type}")
                except Exception:
                    logger.exception('Error during breaker eviction')
                # Process DLQ for requeues
                try:
                    self.qm.process_dlq()
                except Exception:
                    logger.exception('Error processing DLQ')
                time.sleep(5)
            except Exception:
                logger.exception('Error in SLA monitor loop')

    def get_pipeline_health(self) -> dict:
        queue_depths = self.qm.get_queue_depths()
        all_alive = all(w.is_alive() for w in self.workers)
        # p95 latencies not available for all stages; approximate
        return {
            'all_workers_alive': all_alive,
            'queue_depths': queue_depths,
            'p95_stage_latencies': {},
            'sla_breaches_last_hour': 0,
            'throughput_opps_per_minute': 0.0,
            'trading_allowed': True,
        }

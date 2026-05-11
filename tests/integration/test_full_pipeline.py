import os
import sys
import time
import pytest
import threading

# Make internal packages importable as top-level modules for tests
sys.path.insert(0, os.path.join(os.getcwd(), 'agent'))

from agent.pipeline.queue_manager import QueueManager
from agent.pipeline.orchestrator import PipelineOrchestrator
from agent.pipeline.schema import InferenceRequestMessage


@pytest.fixture(autouse=True)
def env_setup(monkeypatch):
    monkeypatch.setenv('TEE_MODE', 'local')
    monkeypatch.setenv('DRY_RUN_MODE', 'true')
    monkeypatch.setenv('TEE_ADDRESS', '0x1111111111111111111111111111111111111111')
    monkeypatch.setenv('SIGNAL_VALIDATOR_ADDRESS', '0x2222222222222222222222222222222222222222')
    monkeypatch.setenv('ARBITRAGE_EXECUTOR_ADDRESS', '0x3333333333333333333333333333333333333333')
    monkeypatch.delenv('TEE_ATTESTATION_CERT_PATH', raising=False)
    yield


def make_inference_input(i):
    now = int(time.time())
    import uuid
    return {
        'opportunity_id': str(uuid.uuid4()),
        'dex_a': '0x0000000000000000000000000000000000000001',
        'dex_b': '0x0000000000000000000000000000000000000002',
        'price_a': 100.0 + i,
        'price_b': 99.0,
        'borrow_amount_usdc': 1000,
        'funding_rate_a': 0.0,
        'funding_rate_b': 0.0,
        'timestamp': now,
        'chain_id': int(os.getenv('CHAIN_ID', '16600')),
    }


def test_pipeline_happy_path(tmp_path):
    qm = QueueManager()
    orch = PipelineOrchestrator()
    orch.start(dry_run_mode=True)

    # inject 10 messages
    for i in range(10):
        inp = make_inference_input(i)
        msg = InferenceRequestMessage(correlation_id=inp['opportunity_id'], pipeline_stage='INFERENCE_REQUESTED', inference_input=inp, inference_deadline_ms=int(time.time() * 1000) + 30000, source_component='test')
        qm.push(QueueManager.QUEUE_INFERENCE_REQUESTS, msg, priority=0)

    # wait up to 60s for 10 records in sqlite
    start = time.time()
    found = False
    while time.time() - start < 60:
        try:
            import sqlite3
            conn = sqlite3.connect('data/trades.db')
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM trade_records')
            cnt = cur.fetchone()[0]
            conn.close()
            if cnt >= 10:
                found = True
                break
        except Exception:
            pass
        time.sleep(1)

    assert found, 'Expected 10 trade records to appear in SQLite within 60s'

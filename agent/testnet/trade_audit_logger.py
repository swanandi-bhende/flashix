import json
import sqlite3
import os
import time
from dataclasses import dataclass, asdict
from decimal import Decimal
import redis

DB_PATH = os.environ.get('TESTNET_SQLITE_DB', 'data/testnet_trades.db')

@dataclass
class TestnetTradeRecord:
    trade_id: str
    session_id: str
    sequence_number: int
    mempool_detection_timestamp_ms: int
    filter_pass_timestamp_ms: int
    inference_request_timestamp_ms: int
    inference_response_timestamp_ms: int
    inference_latency_ms: float
    agent_decision_timestamp_ms: int
    agent_decision_time_ms: float
    decision_reasoning_summary: str
    full_reasoning_trace_id: str
    tx_submitted_timestamp_ms: int
    tx_hash: str
    block_number: int
    on_chain_execution_time_ms: float
    expected_profit_usdc: Decimal
    realized_profit_usdc: Decimal
    profit_variance_pct: float
    gas_used: int
    gas_cost_usdc: Decimal
    net_profit_after_gas_usdc: Decimal
    settlement_confirmation_timestamp_ms: int
    total_pipeline_latency_ms: float
    revert_reason: str = None
    risk_checks_passed: list = None
    oracle_sources_used: list = None
    testnet_explorer_link: str = ''

class TradeAuditLogger:
    def __init__(self, session_id: str):
        os.makedirs('data/testnet_sessions', exist_ok=True)
        self.session_id = session_id
        self.jsonl_path = f"data/testnet_sessions/{session_id}_trades.jsonl"
        self.sqlite_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._ensure_table()
        self.redis = redis.Redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))

    def _ensure_table(self):
        c = self.sqlite_conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS testnet_trades (
            trade_id TEXT PRIMARY KEY,
            session_id TEXT,
            seq INTEGER,
            payload TEXT
        )''')
        self.sqlite_conn.commit()

    def log_trade(self, record: TestnetTradeRecord):
        rec = asdict(record)
        # 1) SQLite
        cur = self.sqlite_conn.cursor()
        cur.execute('INSERT OR REPLACE INTO testnet_trades(trade_id, session_id, seq, payload) VALUES (?,?,?,?)',
                    (record.trade_id, record.session_id, record.sequence_number, json.dumps(rec, default=str)))
        self.sqlite_conn.commit()

        # 2) JSONL
        with open(self.jsonl_path, 'a') as f:
            f.write(json.dumps(rec, default=str) + "\n")

        # 3) Redis sorted set
        zkey = f"trades:session:{self.session_id}"
        self.redis.zadd(zkey, {record.trade_id: record.sequence_number})

    def close(self):
        try:
            self.sqlite_conn.close()
        except Exception:
            pass

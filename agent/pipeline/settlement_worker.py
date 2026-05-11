import threading
import time
import json
import sqlite3
import os
import logging
from dataclasses import asdict
from typing import Dict, Any

from .queue_manager import QueueManager
from .schema import ExecutionResultMessage, CorrelationRecord

logger = logging.getLogger(__name__)


class SettlementWorker(threading.Thread):
    def __init__(self, queue_manager: QueueManager, db_path: str = 'data/trades.db', jsonl_path: str = 'data/trade_history.jsonl', name: str = 'settlement-worker'):
        super().__init__(daemon=True, name=name)
        self.qm = queue_manager
        self.db_path = db_path
        self.jsonl_path = jsonl_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.jsonl_path), exist_ok=True)
        self._init_db()
        self._stop = threading.Event()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('''
            CREATE TABLE IF NOT EXISTS trade_records (
                correlation_id TEXT PRIMARY KEY,
                final_status TEXT,
                realized_profit_usdc TEXT,
                created_at INTEGER,
                payload TEXT
            )
            ''')
            conn.commit()
        finally:
            conn.close()

    def stop(self):
        self._stop.set()

    def _write_record(self, correlation_id: str, final_status: str, realized_profit: Any, payload: Dict[str, Any]):
        now = int(time.time())
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('''INSERT OR REPLACE INTO trade_records (correlation_id, final_status, realized_profit_usdc, created_at, payload) VALUES (?, ?, ?, ?, ?)''', (correlation_id, final_status, str(realized_profit) if realized_profit is not None else None, now, json.dumps(payload)))
            conn.commit()
        finally:
            conn.close()

        # append to jsonl
        with open(self.jsonl_path, 'a') as fh:
            fh.write(json.dumps({'correlation_id': correlation_id, 'final_status': final_status, 'realized_profit_usdc': realized_profit, 'payload': payload, 'created_at': now}) + '\n')

    def compute_session_stats(self) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM trade_records')
            total = cur.fetchone()[0]
            return {'total_trades': total}
        finally:
            conn.close()

    def run(self):
        while not self._stop.is_set():
            try:
                msg = self.qm.pop(QueueManager.QUEUE_SETTLEMENT_UPDATES, timeout_seconds=1)
                if msg is None:
                    continue
                # Attempt to parse ExecutionResultMessage
                if isinstance(msg, ExecutionResultMessage):
                    corr = msg.correlation_id
                    final_status = getattr(msg.execution_result, 'status', 'UNKNOWN') if msg.execution_result else getattr(msg, 'decision', 'REJECTED')
                    realized = getattr(msg, 'realized_profit_usdc', None)
                    payload = msg.to_dict()
                    self._write_record(corr, final_status, realized, payload)
                    # update redis correlation record final status and ttl
                    try:
                        self.qm._client.hset(f"flashix:correlation:{corr}", mapping={"current_stage": "SETTLEMENT_COMPLETED", "final_status": final_status, "settlement_completed_at": int(time.time() * 1000)})
                        self.qm._client.expire(f"flashix:correlation:{corr}", 604800)
                    except Exception:
                        logger.exception('Failed to update redis correlation after settlement')
                else:
                    # generic message
                    corr = getattr(msg, 'correlation_id', None) or 'unknown'
                    payload = getattr(msg, 'to_dict', lambda: {})()
                    self._write_record(corr, 'REJECTED', None, payload)
            except Exception:
                logger.exception('Unexpected error in SettlementWorker loop')

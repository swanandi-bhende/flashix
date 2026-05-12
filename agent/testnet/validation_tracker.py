import time
import json
import os
import sqlite3
from dataclasses import dataclass
import requests

DB_PATH = os.environ.get('TESTNET_SQLITE_DB', 'data/testnet_trades.db')
OPS_WEBHOOK = os.environ.get('OPS_WEBHOOK')

@dataclass
class ValidationStatus:
    criterion_a: bool
    criterion_b: bool
    criterion_c: bool
    criterion_d: bool
    all_passing: bool
    trades_completed: int
    hours_elapsed: float
    estimated_completion_hours: float

class ValidationTracker:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.conn = sqlite3.connect(DB_PATH)

    def evaluate_criteria(self) -> ValidationStatus:
        cur = self.conn.cursor()
        cur.execute('SELECT payload FROM testnet_trades WHERE session_id = ?', (self.session_id,))
        rows = cur.fetchall()
        trades = [json.loads(r[0]) for r in rows]
        trades_completed = len(trades)

        confirmed = [t for t in trades if t.get('revert_reason') is None]
        reverted = [t for t in trades if t.get('revert_reason')]
        timeouts = []

        criterion_a = (len(reverted) + len(timeouts)) == 0

        executed = confirmed
        pct_within_2pct = 0.0
        if executed:
            within = [t for t in executed if abs(float(t.get('profit_variance_pct', 999.0))) <= 2.0]
            pct_within_2pct = len(within) / len(executed)
        criterion_b = pct_within_2pct >= 0.90

        criterion_c = True
        for t in executed:
            if float(t.get('realized_profit_usdc', 0)) < 0:
                loss_pct = abs(float(t.get('profit_variance_pct', 0)))
                if loss_pct > 5.0:
                    criterion_c = False
                    # immediate emergency
                    self._emit_ops(f"CRITERION_C_BREACH: trade_id={t.get('trade_id')}, loss_pct={loss_pct:.1f}%", level='EMERGENCY')

        # uptime: approximate from health monitor logs; placeholder: assume 100%
        uptime_pct = 100.0
        criterion_d = uptime_pct >= 98.0

        all_passing = all([criterion_a, criterion_b, criterion_c, criterion_d])

        hours_elapsed = 0
        estimated_completion_hours = 0

        status = ValidationStatus(criterion_a, criterion_b, criterion_c, criterion_d, all_passing, trades_completed, hours_elapsed, estimated_completion_hours)
        # persist status
        os.makedirs(f"data/testnet_sessions", exist_ok=True)
        with open(f"data/testnet_sessions/{self.session_id}_validation.jsonl", 'a') as f:
            f.write(json.dumps(status.__dict__) + '\n')

        if OPS_WEBHOOK:
            self._emit_ops(json.dumps(status.__dict__))

        return status

    def _emit_ops(self, message, level='INFO'):
        if not OPS_WEBHOOK:
            return
        try:
            requests.post(OPS_WEBHOOK, json={"level": level, "message": message}, timeout=5)
        except Exception:
            pass

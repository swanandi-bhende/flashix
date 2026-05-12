from decimal import Decimal
import uuid
import time
import threading
import json
import os
from agent.configs import testnet_config
from agent.testnet.trade_audit_logger import TradeAuditLogger
from agent.testnet.validation_tracker import ValidationTracker

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)



class SessionHealthMonitor(threading.Thread):
    def __init__(self, session):
        super().__init__(daemon=True)
        self.session = session
        self._stop = threading.Event()
        self.total_downtime = 0
        self.last_up = time.time()

    def run(self):
        while not self._stop.is_set():
            # placeholder checks
            # In production, check agent process, redis queue depths, last trade time
            time.sleep(60)

    def stop(self):
        self._stop.set()

    def get_uptime_pct(self, session_seconds):
        return 100.0 if session_seconds == 0 else ((session_seconds - self.total_downtime) / session_seconds) * 100.0


class TestnetValidationSession:
    def __init__(self, target_trades=50, target_duration_hours=36):
        self.session_id = str(uuid.uuid4())
        self.start_time = int(time.time())
        self.target_trades = target_trades
        self.target_duration_hours = target_duration_hours
        self.trades_completed = 0
        self.session_log_path = f"data/testnet_sessions/{self.session_id}.jsonl"
        os.makedirs('data/testnet_sessions', exist_ok=True)
        self.audit_logger = TradeAuditLogger(self.session_id)
        self.health_monitor = SessionHealthMonitor(self)
        self.validation_tracker = ValidationTracker(self.session_id)
        self.restart_count = 0

    def start(self):
        # write session start record
        start_record = {
            'event': 'SESSION_START',
            'session_id': self.session_id,
            'start_time': self.start_time,
            'target_trades': self.target_trades,
            'target_duration_hours': self.target_duration_hours,
            'config_used': 'testnet_config'
        }
        with open(self.session_log_path, 'a') as f:
            f.write(json.dumps(start_record) + '\n')

        # start components
        self.health_monitor.start()

        try:
            self.main_loop()
        except Exception as e:
            self.handle_unexpected_shutdown(e)

    def main_loop(self):
        # placeholder main agent loop - in real system this will start actual agent components
        end_time = time.time() + (self.target_duration_hours * 3600)
        while self.trades_completed < self.target_trades and time.time() < end_time:
            # wait for trade events simulated here by sleep
            time.sleep(10)
            # simulate a trade record increment
            self.trades_completed += 1
            # write a tiny session progress event
            with open(self.session_log_path, 'a') as f:
                f.write(json.dumps({'event': 'TRADE_SIM', 'session_id': self.session_id, 'seq': self.trades_completed}) + '\n')

            if self.trades_completed % 5 == 0:
                self.validation_tracker.evaluate_criteria()

        # session end
        with open(self.session_log_path, 'a') as f:
            f.write(json.dumps({'event': 'SESSION_END', 'session_id': self.session_id, 'trades_completed': self.trades_completed}) + '\n')
        self.health_monitor.stop()

    def handle_unexpected_shutdown(self, error: Exception):
        import traceback
        trace = traceback.format_exc()
        with open(self.session_log_path, 'a') as f:
            f.write(json.dumps({'event': 'CRASH_DETECTED', 'error': str(error), 'trace': trace}) + '\n')
        # send webhook, wait and attempt restart (limited)
        self.restart_count += 1
        if self.restart_count <= 3:
            time.sleep(30)
            self.start()
        else:
            with open(self.session_log_path, 'a') as f:
                f.write(json.dumps({'event': 'CRASH_PERMANENT', 'restart_count': self.restart_count}) + '\n')


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--target-trades', type=int, default=50)
    p.add_argument('--duration-hours', type=float, default=36)
    args = p.parse_args()
    s = TestnetValidationSession(target_trades=args.target_trades, target_duration_hours=args.duration_hours)
    s.start()

import os
import json
from dataclasses import asdict

class ReplayAnalysisReport(dict):
    pass

class TestnetTradeReplayer:
    def __init__(self, session_id: str):
        self.session_id = session_id

    def replay_all(self, session_id: str) -> ReplayAnalysisReport:
        path = f"data/testnet_sessions/{session_id}_trades.jsonl"
        if not os.path.exists(path):
            return ReplayAnalysisReport({"reason": "no_data"})
        trades = [json.loads(l) for l in open(path)]

        report = ReplayAnalysisReport()
        report['total_trades'] = len(trades)
        report['replays'] = []

        # Populate ground truth and run validators - placeholders callable by project
        for t in trades:
            # example: feed to InferenceRecorder, AccuracyValidator, etc.
            report['replays'].append({'trade_id': t.get('trade_id'), 'status': 'processed'})

        outdir = 'docs/testnet_reports'
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, f'session_{session_id}_analysis.md'), 'w') as f:
            f.write('# Replay Analysis Report\n')
            f.write(f'Trades processed: {report["total_trades"]}\n')

        return report

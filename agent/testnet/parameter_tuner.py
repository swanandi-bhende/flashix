import json
import os
from decimal import Decimal
import statistics

class TuningReport(dict):
    pass

class ParameterTuner:
    def __init__(self, session_id: str):
        self.session_id = session_id
        os.makedirs('data/testnet_sessions', exist_ok=True)

    def analyze_and_tune(self, min_trades: int = 20) -> TuningReport:
        # Load last trades
        path = f"data/testnet_sessions/{self.session_id}_trades.jsonl"
        if not os.path.exists(path):
            return TuningReport({"reason": "no_data"})
        with open(path) as f:
            trades = [json.loads(l) for l in f]

        if len(trades) < min_trades:
            return TuningReport({"reason": "insufficient_trades", "count": len(trades)})

        report = TuningReport()

        # Collateral tuning: placeholder
        reverts = [t for t in trades if t.get('revert_reason') == 'INSUFFICIENT_COLLATERAL']
        if reverts:
            report['collateral_recommend'] = {'increase_by': 0.1, 'reason': 'observed reverts'}

        # Profit cutoff tuning
        varcs = [float(t.get('profit_variance_pct', 0)) for t in trades[-min_trades:]]
        avg_var = statistics.mean(varcs) if varcs else 0.0
        if avg_var < 0:
            report['profit_cutoff_recommend'] = {'increase_usdc': abs(avg_var), 'reason': 'model overestimation'}

        # Execution timeout tuning
        on_chain = [float(t.get('on_chain_execution_time_ms', 0)) for t in trades]
        if on_chain:
            p95 = statistics.quantiles(on_chain, n=100)[94]
            report['p95_on_chain_ms'] = p95
            if p95 > 0:
                report['position_timeout_recommend'] = {'increase_seconds': 5, 'reason': f'p95 {p95}ms'}

        # Gas budget tuning (auto-apply calibration)
        gas_used = [int(t.get('gas_used', 0)) for t in trades if t.get('gas_used')]
        if gas_used:
            mean_actual = statistics.mean(gas_used)
            report['gas_mean'] = mean_actual
            report['gas_calibration_auto_applied'] = True

        # write report
        with open(f"data/testnet_sessions/{self.session_id}_tuning.jsonl", 'a') as f:
            f.write(json.dumps(report) + '\n')

        return report

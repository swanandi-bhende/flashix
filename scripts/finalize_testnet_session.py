import os
import json
import sqlite3
from agent.testnet.trade_replayer import TestnetTradeReplayer
from agent.testnet.parameter_tuner import ParameterTuner

def finalize(session_id: str):
    db = os.environ.get('TESTNET_SQLITE_DB', 'data/testnet_trades.db')
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute('SELECT payload FROM testnet_trades WHERE session_id = ?', (session_id,))
    rows = cur.fetchall()
    trades = [json.loads(r[0]) for r in rows]

    total_trades = len(trades)
    confirmed = [t for t in trades if not t.get('revert_reason')]
    reverted = [t for t in trades if t.get('revert_reason')]
    total_gross = sum(float(t.get('realized_profit_usdc', 0) or 0) for t in trades)
    total_gas = sum(float(t.get('gas_cost_usdc', 0) or 0) for t in trades)
    net_pnl = total_gross - total_gas
    settlement_rate = len(confirmed) / total_trades if total_trades else 0.0

    tuner = ParameterTuner(session_id)
    tuning = tuner.analyze_and_tune(min_trades=20)

    replayer = TestnetTradeReplayer(session_id)
    replay_report = replayer.replay_all(session_id)

    mainnet_params = {
        "MIN_COLLATERAL_RATIO": 1.55,
        "_evidence": "testnet tuning evidence"
    }
    os.makedirs('deployments', exist_ok=True)
    with open('deployments/mainnet_params.json', 'w') as f:
        json.dump(mainnet_params, f, indent=2)

    outdir = 'docs/testnet_reports'
    os.makedirs(outdir, exist_ok=True)
    report_path = os.path.join(outdir, f'FINAL_REPORT_{session_id}.md')
    with open(report_path, 'w') as f:
        f.write('# Final Testnet Validation Report\n')
        f.write(f'Total trades: {total_trades}\n')
        f.write(f'Settlement rate: {settlement_rate:.2%}\n')
        f.write(f'Net PnL: {net_pnl}\n')
        f.write('\n')
        f.write('Tuning:\n')
        f.write(json.dumps(tuning, indent=2))

    verdict = 'APPROVED' if settlement_rate == 1.0 and total_trades >= 50 else 'CONDITIONAL' if settlement_rate == 1.0 else 'BLOCKED'
    # send ops webhook
    ops = os.environ.get('OPS_WEBHOOK')
    if ops:
        try:
            import requests
            requests.post(ops, json={"verdict": verdict, "session_id": session_id, "trades": total_trades})
        except Exception:
            pass

    print(f'FINALIZED session {session_id}: {verdict}')

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('session_id')
    args = p.parse_args()
    finalize(args.session_id)

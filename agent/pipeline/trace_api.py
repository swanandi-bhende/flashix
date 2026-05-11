from fastapi import FastAPI, HTTPException
from .queue_manager import QueueManager
import sqlite3
import json
from typing import Any

app = FastAPI()
qm = QueueManager()


@app.get('/pipeline/trace/{correlation_id}')
def get_trace(correlation_id: str):
    # try redis
    key = f'flashix:correlation:{correlation_id}'
    rec = qm._client.hgetall(key)
    if rec and rec.get('current_stage'):
        # build timeline from timestamps in record
        stage_timestamps = {k: int(v) for k, v in rec.items() if k.endswith('_at')}
        timeline = []
        for k, v in stage_timestamps.items():
            timeline.append({'stage': k.replace('_at','').upper(), 'entered_at_ms': v, 'exited_at_ms': None, 'duration_ms': None, 'component': 'unknown', 'notes': ''})
        return {'correlation_id': correlation_id, 'final_status': rec.get('outcome') or rec.get('current_stage'), 'stage_timeline': timeline, 'total_latency_ms': rec.get('total_latency_ms')}

    # fallback to sqlite
    conn = sqlite3.connect('data/trades.db')
    try:
        cur = conn.cursor()
        cur.execute('SELECT payload FROM trade_records WHERE correlation_id = ?', (correlation_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Correlation not found')
        payload = json.loads(row[0])
        return {'correlation_id': correlation_id, 'final_status': payload.get('final_status'), 'stage_timeline': payload.get('payload', {}).get('stage_timestamps', {}), 'total_latency_ms': payload.get('payload', {}).get('total_latency_ms')}
    finally:
        conn.close()


@app.get('/pipeline/funnel')
def get_funnel():
    # simple funnel counts from sqlite
    conn = sqlite3.connect('data/trades.db')
    try:
        cur = conn.cursor()
        cur.execute('SELECT final_status, COUNT(*) FROM trade_records GROUP BY final_status')
        rows = cur.fetchall()
        funnel = {r[0]: r[1] for r in rows}
        return {'rejection_funnel': funnel}
    finally:
        conn.close()

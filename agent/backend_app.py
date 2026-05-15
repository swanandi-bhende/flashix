from __future__ import annotations

from fastapi import FastAPI

from agent.market_data import api as market_data_api
from agent.metrics import dashboard_api as metrics_dashboard_api
from agent.pipeline import trace_api as pipeline_trace_api
from agent.reasoning import trace_api as reasoning_trace_api
from agent.settlement import ledger as settlement_ledger_api

app = FastAPI(
    title="Flashix Backend",
    version="1.0.0",
    description="Consolidated Flashix backend API for market data, tracing, metrics, and settlement.",
)

app.include_router(market_data_api.app.router)
app.include_router(reasoning_trace_api.app.router)
app.include_router(metrics_dashboard_api.app.router)
app.include_router(settlement_ledger_api.app.router)
app.include_router(pipeline_trace_api.app.router)


@app.get("/")
def root() -> dict[str, object]:
    return {
        "service": "flashix-backend",
        "status": "ok",
        "description": "Single consolidated backend for the Flashix stack.",
        "services": [
            "market-data",
            "reasoning-trace",
            "metrics-dashboard",
            "settlement-ledger",
            "pipeline-trace",
        ],
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "service": "flashix-backend"}

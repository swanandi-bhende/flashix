"""FastAPI service for trace inspection and verification."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query

from .reasoning_parser import ReasoningParser
from .trace_db import TraceDB

app = FastAPI(title="Flashix Reasoning Trace API", version="1.0.0")
trace_db = TraceDB()
parser = ReasoningParser()


def _trace_summary(trace) -> Dict[str, Any]:
    return trace.to_dict()


@app.get("/traces")
def list_traces(
    limit: int = Query(10, ge=1, le=100),
    decision: Optional[str] = Query(default=None, pattern="^(APPROVE|REJECT)$"),
    min_profit: Optional[float] = Query(default=None),
    since_timestamp: Optional[int] = Query(default=None, ge=0),
) -> List[Dict[str, Any]]:
    traces = trace_db.get_recent_traces(
        limit=limit,
        decision_filter=decision,
        min_profit=min_profit,
        since_timestamp=since_timestamp,
    )
    return [_trace_summary(trace) for trace in traces]


@app.get("/traces/stats")
def get_stats() -> Dict[str, Any]:
    return trace_db.get_reasoning_stats()


@app.get("/traces/{opportunity_id}")
def get_trace(opportunity_id: str) -> Dict[str, Any]:
    trace = trace_db.get_trace(opportunity_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    payload = trace.to_dict()
    payload["full_trace_json"] = trace.to_json()
    return payload


@app.get("/traces/{opportunity_id}/verify")
def verify_trace(opportunity_id: str) -> Dict[str, Any]:
    trace = trace_db.get_trace(opportunity_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    warnings = parser.validate_numeric_consistency(trace)
    return {"consistent": len(warnings) == 0, "warnings": warnings}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent.reasoning.trace_api:app", host="0.0.0.0", port=8001, reload=False)

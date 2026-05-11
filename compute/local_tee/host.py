"""Local TEE sandbox host for offline development and interface parity testing."""

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from compute.payload_schema import InferenceRequest
from compute.arbitrage_analyzer import ArbitrageAnalyzer

app = FastAPI()

os.environ.setdefault("TEE_MODE", "local")

class Req(BaseModel):
    opportunity_id: str

@app.post("/v1/chat/completions")
@app.post("/infer")
async def infer(payload: dict):
    try:
        req = InferenceRequest.model_validate(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    analyzer = ArbitrageAnalyzer()
    resp = analyzer.analyze(req)
    return resp.model_dump()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8081)

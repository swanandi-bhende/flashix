"""Very small host stub to mirror the 0G TEE inference interface for local testing."""
import json
from fastapi import FastAPI
from pydantic import BaseModel
from compute.payload_schema import InferenceRequest
from compute.arbitrage_analyzer import ArbitrageAnalyzer

app = FastAPI()

class Req(BaseModel):
    opportunity_id: str

@app.post("/infer")
async def infer(payload: dict):
    # validate and call analyzer
    try:
        req = InferenceRequest.model_validate(payload)
    except Exception as e:
        return {"error": str(e)}, 400
    analyzer = ArbitrageAnalyzer()
    resp = analyzer.analyze(req)
    return resp.model_dump()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8081)

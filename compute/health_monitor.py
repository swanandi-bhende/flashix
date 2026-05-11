import os
import time
import asyncio
import statistics
import logging
from collections import deque
from typing import Deque

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
logger = logging.getLogger(__name__)

class ComputeStatus:
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"

class ComputeHealthMonitor:
    def __init__(self, client=None):
        self.endpoint = os.getenv("TEE_ENDPOINT")
        self.samples: Deque[int] = deque(maxlen=20)
        self.client = client or httpx.AsyncClient(timeout=5.0)
        self.last_failures = 0
        self.last_checked_at = 0.0

    async def ping(self) -> int:
        payload = {"health_check": True}
        start = time.time()
        try:
            if os.getenv("TEE_MODE", "local") == "local":
                # local quick response
                await asyncio.sleep(0.01)
                latency = int((time.time() - start) * 1000)
            else:
                headers = {}
                api_key = os.getenv("TEE_API_KEY")
                if api_key and str(api_key).startswith("app-sk-"):
                    headers["Authorization"] = f"Bearer {api_key}"
                resp = await self.client.post(self.endpoint, json=payload, headers=headers)
                latency = int((time.time() - start) * 1000)
                if resp.status_code != 200:
                    raise RuntimeError("non-200")
            self.samples.append(latency)
            self.last_failures = 0
            self.last_checked_at = time.time()
            logger.info("compute_health latency_ms=%s status=%s", latency, ComputeStatus.HEALTHY)
            return latency
        except Exception:
            self.last_failures += 1
            self.samples.append(9999)
            self.last_checked_at = time.time()
            logger.warning("compute_health latency_ms=%s status=%s", 9999, ComputeStatus.UNAVAILABLE)
            return 9999

    def percentiles(self):
        if not self.samples:
            return {"p50": 0, "p95": 0, "p99": 0}
        arr = list(self.samples)
        ordered = sorted(arr)

        def pick_percentile(percentile: float) -> int:
            if len(ordered) == 1:
                return int(ordered[0])
            index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
            return int(ordered[index])

        return {
            "p50": int(statistics.median(arr)),
            "p95": pick_percentile(0.95),
            "p99": pick_percentile(0.99),
        }

    def get_status(self):
        p = self.percentiles()
        p95 = p.get("p95", 0)
        if self.last_failures >= 3 or p95 > 3000:
            return ComputeStatus.UNAVAILABLE
        if p95 > 1000:
            return ComputeStatus.DEGRADED
        return ComputeStatus.HEALTHY

monitor = ComputeHealthMonitor()

class HealthResponse(BaseModel):
    status: str
    p50: int
    p95: int
    p99: int
    last_sample_ms: int

@app.get("/health", response_model=HealthResponse)
async def health():
    p = monitor.percentiles()
    last = monitor.samples[-1] if monitor.samples else 0
    return HealthResponse(status=monitor.get_status(), p50=p["p50"], p95=p["p95"], p99=p["p99"], last_sample_ms=last)

async def _background_loop():
    while True:
        await monitor.ping()
        await asyncio.sleep(30)

# background task can be started by an app runner in production

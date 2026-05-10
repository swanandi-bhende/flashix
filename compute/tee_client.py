import asyncio
import os
import json
import time
import hmac
import hashlib
from typing import Any, Dict

import httpx

from .payload_schema import InferenceRequest, InferenceResponse

class TEEInferenceError(Exception):
    pass

class TEEClient:
    def __init__(self):
        self.mode = os.getenv("TEE_MODE", "local")
        self.endpoint = os.getenv("TEE_ENDPOINT")
        self.api_key = os.getenv("TEE_API_KEY")
        self.attestation_cert = os.getenv("TEE_ATTESTATION_CERT_PATH")
        self.timeout_ms = int(os.getenv("TEE_REQUEST_TIMEOUT_MS", "5000"))
        self._client = httpx.AsyncClient(timeout=self.timeout_ms/1000.0, verify=self.attestation_cert or True)

    def sign_request(self, payload: Dict[str, Any]) -> Dict[str, str]:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        sig = hmac.new(self.api_key.encode(), body.encode(), hashlib.sha256).hexdigest()
        return {"X-TEE-Signature": sig}

    async def infer(self, payload: Dict[str, Any], timeout_ms: int = None) -> Dict[str, Any]:
        if timeout_ms is None:
            timeout_ms = self.timeout_ms
        request_id = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
        headers = self.sign_request(payload)
        headers.update({"Content-Type": "application/json"})
        attempt = 0
        backoffs = [1, 2, 4]
        start = time.time()
        while True:
            attempt += 1
            try:
                if self.mode == "local":
                    # local mode: call local compute module directly to avoid network
                    from .arbitrage_analyzer import ArbitrageAnalyzer
                    analyzer = ArbitrageAnalyzer()
                    # validate payload
                    InferenceRequest.model_validate(payload)
                    resp = analyzer.analyze(InferenceRequest.model_validate(payload))
                    latency = int((time.time() - start) * 1000)
                    # Log request (in real app use structured logger)
                    print(f"TEEClient request_id={request_id} payload_size={len(json.dumps(payload))} latency_ms={latency} status=200")
                    return resp.model_dump()

                resp = await self._client.post(self.endpoint, json=payload, headers=headers)
                latency = int((time.time() - start) * 1000)
                print(f"TEEClient request_id={request_id} payload_size={len(json.dumps(payload))} latency_ms={latency} status={resp.status_code}")

                if resp.status_code == 200:
                    data = resp.json()
                    # validate response shape before returning
                    InferenceResponse.model_validate(data)
                    return data
                if resp.status_code == 429 and attempt <= 3:
                    await asyncio.sleep(backoffs[attempt-1])
                    continue
                if resp.status_code == 503:
                    # switch to local mode automatically
                    print("TEE service unavailable (503) — switching to local mode")
                    self.mode = "local"
                    continue
                # other non-200 responses
                raise TEEInferenceError(f"TEE inference failed status={resp.status_code} body={resp.text}")
            except httpx.RequestError as e:
                if attempt <= 3:
                    await asyncio.sleep(backoffs[min(attempt-1, len(backoffs)-1)])
                    continue
                raise TEEInferenceError(f"TEE request error: {e}")

    async def close(self):
        await self._client.aclose()

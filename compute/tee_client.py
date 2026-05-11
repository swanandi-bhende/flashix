import asyncio
import os
import json
import time
import hmac
import hashlib
import logging
from typing import Any, Dict

import httpx

from .payload_schema import InferenceRequest, InferenceResponse


logger = logging.getLogger(__name__)

class TEEInferenceError(Exception):
    pass

class TEEClient:
    def __init__(self):
        self.mode = os.getenv("TEE_MODE", "local")
        self.endpoint = os.getenv("TEE_ENDPOINT")
        self.api_key = os.getenv("TEE_API_KEY")
        self.attestation_cert = os.getenv("TEE_ATTESTATION_CERT_PATH")
        self.timeout_ms = int(os.getenv("TEE_REQUEST_TIMEOUT_MS", "5000"))
        self.signature_validation = os.getenv("TEE_SIGNATURE_VALIDATION", "true").lower() == "true"
        verify = self.attestation_cert if self.attestation_cert else True
        self._client = httpx.AsyncClient(timeout=self.timeout_ms/1000.0, verify=verify)

    def sign_request(self, payload: Dict[str, Any]) -> Dict[str, str]:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        headers: Dict[str, str] = {}
        if not self.api_key:
            raise TEEInferenceError("TEE_API_KEY is not configured")
        if str(self.api_key).startswith("app-sk-"):
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"
        sig = hmac.new(self.api_key.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-TEE-Signature"] = sig
        return headers

    async def infer(self, payload: Dict[str, Any], timeout_ms: int = None) -> Dict[str, Any]:
        if timeout_ms is None:
            timeout_ms = self.timeout_ms
        request_id = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
        attempt = 0
        backoffs = [1, 2, 4]
        start = time.perf_counter()
        request_body = InferenceRequest.model_validate(payload)
        headers = self.sign_request(payload)
        headers.update({"Content-Type": "application/json"})
        while True:
            attempt += 1
            try:
                if self.mode == "local":
                    # local mode: call local compute module directly to avoid network
                    from .arbitrage_analyzer import ArbitrageAnalyzer
                    analyzer = ArbitrageAnalyzer()
                    resp = analyzer.analyze(request_body)
                    latency = int((time.perf_counter() - start) * 1000)
                    logger.info(
                        "tee_inference request_id=%s payload_size=%s latency_ms=%s status=%s mode=%s",
                        request_id,
                        len(json.dumps(payload, sort_keys=True, separators=(",", ":"))),
                        latency,
                        200,
                        self.mode,
                    )
                    return resp.model_dump()

                resp = await self._client.post(self.endpoint, json=payload, headers=headers, timeout=timeout_ms/1000.0)
                latency = int((time.perf_counter() - start) * 1000)
                logger.info(
                    "tee_inference request_id=%s payload_size=%s latency_ms=%s status=%s mode=%s",
                    request_id,
                    len(json.dumps(payload, sort_keys=True, separators=(",", ":"))),
                    latency,
                    resp.status_code,
                    self.mode,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if self.signature_validation:
                        InferenceResponse.model_validate(data)
                    return data
                if resp.status_code == 429 and attempt <= 3:
                    await asyncio.sleep(backoffs[attempt-1])
                    continue
                if resp.status_code == 503:
                    logger.warning("TEE service unavailable (503); switching to local mode")
                    self.mode = "local"
                    from .arbitrage_analyzer import ArbitrageAnalyzer

                    local_response = ArbitrageAnalyzer().analyze(request_body)
                    return local_response.model_dump()
                raise TEEInferenceError(f"TEE inference failed status={resp.status_code} body={resp.text}")
            except httpx.RequestError as e:
                if attempt <= 3:
                    await asyncio.sleep(backoffs[min(attempt-1, len(backoffs)-1)])
                    continue
                raise TEEInferenceError(f"TEE request error: {e}")

    async def close(self):
        await self._client.aclose()

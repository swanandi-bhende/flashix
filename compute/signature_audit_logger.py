"""
Signature Audit Logger

Maintains an append-only audit trail of every signature operation performed by
the TEE. This makes cryptographic activity transparent and auditable while
minimizing exposure of sensitive signature material.

Records are written as newline-delimited JSON to data/audit/signatures_{date}.jsonl.
Only the first 16 hex characters of the signature are logged to avoid turning
logs into a signature extraction source.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, List, Optional
from urllib import request, error


@dataclass
class AnomalyAlert:
    """Represents an anomaly detected in the signing audit trail."""
    anomaly_type: str
    severity: str
    message: str
    detected_at: int
    metadata: dict


class SignatureAuditLogger:
    """Append-only signing audit logger with lightweight anomaly detection."""

    def __init__(self, audit_dir: Optional[str] = None, webhook_url: Optional[str] = None):
        self.audit_dir = Path(audit_dir or "data/audit")
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.webhook_url = webhook_url or os.getenv("OPS_WEBHOOK_URL")
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _current_log_path(self) -> Path:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.audit_dir / f"signatures_{date_str}.jsonl"

    def log_signing_event(
        self,
        output: Any,
        signature: str,
        self_verification_passed: bool,
        signing_latency_ms: float,
    ) -> None:
        """Append a structured JSONL signing record to the daily audit file."""
        record = {
            "event_type": "SIGNING",
            "opportunity_id": getattr(output, "opportunity_id", None),
            "input_hash": getattr(output, "input_hash", None),
            "output_hash": getattr(output, "output_hash", None),
            "tee_signature": f"{signature[:16]}..." if signature else "",
            "signer_address": getattr(output, "signer_address", None),
            "self_verification_passed": self_verification_passed,
            "signing_latency_ms": signing_latency_ms,
            "signed_at": int(time.time()),
            "model_version": getattr(output, "model_version", None),
            "enclave_measurement": getattr(output, "enclave_measurement", None),
        }

        log_path = self._current_log_path()
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")

    def detect_anomalies(self, window_minutes: int = 5) -> List[AnomalyAlert]:
        """Scan recent audit records and flag suspicious signing patterns."""
        cutoff = int(time.time()) - (window_minutes * 60)
        records = self._load_recent_records(cutoff)
        alerts: List[AnomalyAlert] = []

        if not records:
            return alerts

        per_minute_counts = {}
        input_hash_streak = 0
        previous_input_hash = None

        for record in records:
            minute_bucket = record["signed_at"] // 60
            per_minute_counts[minute_bucket] = per_minute_counts.get(minute_bucket, 0) + 1

            if record.get("self_verification_passed") is False:
                alerts.append(
                    AnomalyAlert(
                        anomaly_type="SELF_VERIFICATION_FAILED",
                        severity="critical",
                        message="TEE self-verification failed during signing",
                        detected_at=int(time.time()),
                        metadata={"record": record},
                    )
                )

            current_input_hash = record.get("input_hash")
            if current_input_hash and current_input_hash == previous_input_hash:
                input_hash_streak += 1
            else:
                input_hash_streak = 1
                previous_input_hash = current_input_hash

            if input_hash_streak > 3:
                alerts.append(
                    AnomalyAlert(
                        anomaly_type="REPEATED_INPUT_HASH",
                        severity="warning",
                        message="More than 3 consecutive identical input hashes detected",
                        detected_at=int(time.time()),
                        metadata={"input_hash": current_input_hash, "streak": input_hash_streak},
                    )
                )

            if float(record.get("signing_latency_ms", 0)) > 500:
                alerts.append(
                    AnomalyAlert(
                        anomaly_type="SIGNING_LATENCY_HIGH",
                        severity="warning",
                        message="Signing latency exceeded 500ms",
                        detected_at=int(time.time()),
                        metadata={"record": record},
                    )
                )

        for bucket, count in per_minute_counts.items():
            if count > 50:
                alerts.append(
                    AnomalyAlert(
                        anomaly_type="HIGH_SIGNING_RATE",
                        severity="critical",
                        message="More than 50 signing events per minute detected",
                        detected_at=int(time.time()),
                        metadata={"minute_bucket": bucket, "count": count},
                    )
                )

        return alerts

    def start_background_monitoring(self, interval_seconds: int = 60) -> None:
        """Start a daemon thread that periodically scans for anomalies."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()

        def _monitor() -> None:
            while not self._stop_event.wait(interval_seconds):
                alerts = self.detect_anomalies()
                for alert in alerts:
                    self._emit_alert(alert)

        self._monitor_thread = threading.Thread(target=_monitor, daemon=True)
        self._monitor_thread.start()

    def stop_background_monitoring(self) -> None:
        """Stop the anomaly monitoring thread."""
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)

    def _load_recent_records(self, cutoff: int) -> List[dict]:
        records: List[dict] = []
        for path in sorted(self.audit_dir.glob("signatures_*.jsonl")):
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if int(record.get("signed_at", 0)) >= cutoff:
                        records.append(record)
        return records

    def _emit_alert(self, alert: AnomalyAlert) -> None:
        """Send alert to the operations webhook if configured."""
        if not self.webhook_url:
            return

        payload = json.dumps(asdict(alert)).encode("utf-8")
        req = request.Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=5):
                pass
        except error.URLError:
            pass

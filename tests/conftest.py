import os
import sys
import json
from pathlib import Path

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ.setdefault("TEE_SIGNING_KEY", "1" * 64)


def _load_validation_summary() -> dict | None:
    candidates = [
        Path(REPO_ROOT) / "docs" / "validation_reports" / "latest.json",
        Path(REPO_ROOT) / "replay_report.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            if "deployment_recommended" in payload:
                return payload
            if isinstance(payload.get("report"), dict) and "deployment_recommended" in payload["report"]:
                return payload["report"]
    return None


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    summary = _load_validation_summary()
    if not summary:
        return
    if not summary.get("deployment_recommended", False):
        pytest.exit("Inference validation failed — deployment blocked", returncode=1)

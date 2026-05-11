from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import importlib
import json
import logging
from pathlib import Path
from typing import Any

from .inference_replay import DeterminismResult, TestCase, json_dumps, stable_hash


_logger = logging.getLogger(__name__)


class DeterminismValidator:
    def __init__(self) -> None:
        self._analyzer = importlib.import_module("compute.arbitrage_analyzer")

    def _run_once(self, test_case: TestCase) -> dict[str, Any]:
        response = self._analyzer.analyze(test_case.input.__dict__)
        if isinstance(response, dict) and "result" in response:
            return response["result"]
        return response

    def validate_single(self, test_case: TestCase, n_runs: int = 20) -> DeterminismResult:
        outputs: list[dict[str, Any]] = []
        hash_values: list[str] = []

        for _ in range(n_runs):
            output = self._run_once(test_case)
            outputs.append(output)
            hash_values.append(json.dumps(output, sort_keys=True, default=str))

        stable_hash_values = [stable_hash(output) for output in outputs]
        all_identical = len(set(stable_hash_values)) == 1

        differing_fields: list[str] = []
        if not all_identical and outputs:
            all_keys: set[str] = set()
            for output in outputs:
                all_keys.update(output.keys())
            for key in sorted(all_keys):
                values = [json.dumps(output.get(key), sort_keys=True, default=str) for output in outputs]
                if len(set(values)) > 1:
                    differing_fields.append(key)

        return DeterminismResult(
            record_id=test_case.test_id,
            n_runs=n_runs,
            all_identical=all_identical,
            differing_fields=differing_fields,
            hash_values=stable_hash_values,
        )

    def validate_across_restarts(self, test_case: TestCase, fixture_path: str) -> DeterminismResult:
        path = Path(fixture_path)
        output = self._run_once(test_case)
        output_hash = stable_hash(output)

        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_dumps({"output": output, "output_hash": output_hash}, indent=2), encoding="utf-8")
            return DeterminismResult(
                record_id=test_case.test_id,
                n_runs=1,
                all_identical=True,
                differing_fields=[],
                hash_values=[output_hash],
            )

        stored = json.loads(path.read_text(encoding="utf-8"))
        stored_hash = stored.get("output_hash", "")
        stored_output = stored.get("output", {})
        all_identical = output_hash == stored_hash
        differing_fields: list[str] = []
        if not all_identical:
            all_keys = set(stored_output) | set(output)
            for key in sorted(all_keys):
                if json.dumps(stored_output.get(key), sort_keys=True, default=str) != json.dumps(output.get(key), sort_keys=True, default=str):
                    differing_fields.append(key)

        return DeterminismResult(
            record_id=test_case.test_id,
            n_runs=1,
            all_identical=all_identical,
            differing_fields=differing_fields,
            hash_values=[stored_hash, output_hash],
        )

    def validate_batch(self, test_cases: list[TestCase], n_runs: int = 10) -> list[DeterminismResult]:
        results: list[DeterminismResult] = []
        total = len(test_cases)
        pass_count = 0

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self.validate_single, test_case, n_runs): test_case for test_case in test_cases}
            for index, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                results.append(result)
                if result.all_identical:
                    pass_count += 1
                _logger.info(
                    "DETERMINISM_CHECK: %s/%s cases, %s passing",
                    index,
                    total,
                    pass_count,
                )

        return results

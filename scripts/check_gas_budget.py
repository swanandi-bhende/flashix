#!/usr/bin/env python3
"""Validate Hardhat gas reporter output against the Flashix gas budgets."""

from __future__ import annotations

import re
import sys
from pathlib import Path


BUDGETS = {
    "executeArbitrage": 180_000,
    "commitSignal": 8_000,
    "estimateMevBurnAmount": 5_000,
}


def parse_report(report_text: str) -> dict[str, int]:
    parsed: dict[str, int] = {}
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    pattern = re.compile(
        r"^\|\s+(?P<contract>[A-Za-z0-9_]+)\s+·\s+(?P<method>[A-Za-z0-9_]+)\s+·\s+"
        r"(?P<min>[0-9,\-]+)\s+·\s+(?P<max>[0-9,\-]+)\s+·\s+(?P<avg>[0-9,\-]+)\s+·"
    )
    for line in report_text.splitlines():
        clean_line = ansi_pattern.sub("", line)
        match = pattern.match(clean_line)
        if not match:
            continue
        method = match.group("method")
        avg = match.group("avg")
        if avg == "-":
            continue
        gas = int(avg.replace(",", ""))
        parsed[method] = gas
    return parsed


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_gas_budget.py <gas-report.txt>", file=sys.stderr)
        return 2

    report_path = Path(sys.argv[1])
    if not report_path.exists():
        print(f"Gas report not found: {report_path}", file=sys.stderr)
        return 2

    report = parse_report(report_path.read_text())
    failures: list[str] = []

    for function_name, budget in BUDGETS.items():
        gas_used = report.get(function_name)
        if gas_used is None:
            continue
        if gas_used > budget:
            failures.append(f"{function_name}: {gas_used} > {budget}")

    if failures:
        print("Gas budget violations detected:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("All gas budgets passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
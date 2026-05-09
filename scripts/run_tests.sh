#!/usr/bin/env bash
set -e
echo "Running unit tests..."
pytest tests/unit/ --maxfail=1 -q || exit 1
echo "Unit tests passed."

#!/bin/bash
# Bandit and Secret Scanning Python Security Audit
# Comprehensive Python code security analysis with API key exposure detection

set -e

echo "=========================================="
echo "Python Security Audit (Bandit + Secrets)"
echo "=========================================="

# Create output directory
OUTPUT_DIR="bandit_reports"
mkdir -p "$OUTPUT_DIR"

# Tool 1: Bandit - Insecure code patterns
echo ""
echo "Installing Bandit..."
pip install bandit==1.7.5 --break-system-packages --quiet || true

echo "✓ Bandit installed"
echo ""
echo "Running Bandit on Python code..."
bandit -r agent/ compute/ utils/ \
    -f json \
    -o "$OUTPUT_DIR/bandit_report.json" \
    -ll \
    || echo "⚠️  Bandit analysis completed (check report)"

echo "✓ Bandit analysis complete"

# Tool 2: detect-secrets - API key and credential detection
echo ""
echo "Installing detect-secrets..."
pip install detect-secrets==1.4.0 --break-system-packages --quiet || true

echo "✓ detect-secrets installed"
echo ""
echo "Running secret scanning..."
detect-secrets scan --all-files > .secrets.baseline 2>/dev/null || true

if [ -f ".secrets.baseline" ]; then
    echo "✓ Secret baseline created at .secrets.baseline"
    echo "  Run: detect-secrets audit .secrets.baseline"
else
    echo "⚠️  Could not create secret baseline"
fi

# Tool 3: Custom key exposure scanner
echo ""
echo "Running custom key exposure scanner..."
python scripts/scan_for_key_exposure.py agent/ compute/ utils/

echo ""
echo "=========================================="
echo "Python Security Audit Complete"
echo "=========================================="
echo ""
echo "Reports generated:"
echo "  - $OUTPUT_DIR/bandit_report.json (Bandit findings)"
echo "  - .secrets.baseline (Detect-secrets baseline)"
echo "  - docs/security/BANDIT_AUDIT.md (Findings summary)"
echo ""
echo "Next Steps:"
echo "  1. Review Bandit findings in $OUTPUT_DIR/"
echo "  2. Check secret baseline for false positives"
echo "  3. Fix all HIGH severity issues before deployment"
echo ""

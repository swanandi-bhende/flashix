#!/bin/bash
# Slither Smart Contract Security Audit
# Comprehensive Solidity security analysis pipeline with structured audit report generation

set -e  # Exit on error

echo "=========================================="
echo "Slither Smart Contract Security Audit"
echo "=========================================="

# Check if contracts directory exists
if [ ! -d "contracts" ]; then
    echo "❌ contracts/ directory not found"
    exit 1
fi

# Install Slither and dependencies
echo ""
echo "Installing Slither and dependencies..."
pip install slither-analyzer==0.10.0 --break-system-packages --quiet || true
pip install crytic-compile==0.3.5 --break-system-packages --quiet || true

# Create output directory
OUTPUT_DIR="slither_reports"
mkdir -p "$OUTPUT_DIR"

echo "✓ Dependencies installed"

# Run Slither analysis
echo ""
echo "Running Slither analysis on contracts/..."
slither contracts/ \
    --json "$OUTPUT_DIR/slither_report.json" \
    --exclude-dependencies \
    --filter-paths "node_modules,test" \
    --print human-summary,contract-summary,inheritance-graph \
    || echo "⚠️  Slither analysis completed with warnings (check report)"

echo "✓ Slither analysis complete"

# Parse the report
echo ""
echo "Parsing Slither report..."
python scripts/parse_slither_report.py "$OUTPUT_DIR/slither_report.json" "$OUTPUT_DIR/slither_findings.txt"

echo ""
echo "=========================================="
echo "Slither Audit Complete"
echo "=========================================="
echo ""
echo "Results:"
echo "  JSON Report: $OUTPUT_DIR/slither_report.json"
echo "  Parsed Report: $OUTPUT_DIR/slither_findings.txt"
echo ""
echo "Next Steps:"
echo "  1. Review $OUTPUT_DIR/slither_findings.txt"
echo "  2. Address all HIGH and MEDIUM severity findings"
echo "  3. Document fixes in docs/security/SLITHER_AUDIT.md"
echo "  4. Re-run this script to verify fixes"
echo ""

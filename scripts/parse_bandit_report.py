#!/usr/bin/env python3
"""
Parse Bandit JSON report and generate structured audit findings.

Analyzes security issues found by Bandit and groups them by severity.
Blocks deployment on any HIGH severity finding.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
from collections import defaultdict


SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

REMEDIATION_GUIDANCE = {
    "B105": {
        "title": "Possible password in variable assignment",
        "fix": "Use environment variables or secure secret management instead of hardcoded passwords",
    },
    "B106": {
        "title": "Possible password in function definition",
        "fix": "Never hardcode passwords in function parameters; use environment variables or secure storage",
    },
    "B107": {
        "title": "Possible hardcoded password or API key",
        "fix": "Remove hardcoded credentials; load from environment or secure secret manager",
    },
    "B322": {
        "title": "Potential insecure pickle usage",
        "fix": "Use json.loads() instead of pickle.loads() for untrusted data",
    },
    "B501": {
        "title": "Request with unverified SSL certificate",
        "fix": "Set verify=True in requests.get() or use certificate pinning",
    },
    "B502": {
        "title": "Insecure temporary file creation",
        "fix": "Use tempfile.NamedTemporaryFile(delete=False) with secure permissions",
    },
    "B608": {
        "title": "Potential SQL injection via string formatting",
        "fix": "Use parameterized queries or ORMs instead of string concatenation for SQL",
    },
    "B303": {
        "title": "Use of insecure MD5 hash function",
        "fix": "Use hashlib.sha256() instead of md5 for security-sensitive applications",
    },
}


def load_bandit_report(report_path: str) -> dict:
    """Load Bandit JSON report."""
    try:
        with open(report_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load Bandit report: {e}")
        sys.exit(1)


def parse_findings(report: dict) -> Dict[str, List[dict]]:
    """Parse Bandit results into grouped findings."""
    grouped = defaultdict(list)
    
    for result in report.get("results", []):
        severity = result.get("severity", "MEDIUM").upper()
        
        # Normalize severity
        if severity not in SEVERITY_ORDER:
            severity = "LOW"
        
        finding = {
            "test_id": result.get("test_id", ""),
            "test_name": result.get("test_name", ""),
            "severity": severity,
            "issue_text": result.get("issue_text", ""),
            "issue_confidence": result.get("issue_confidence", "UNKNOWN"),
            "filename": result.get("filename", ""),
            "line_number": result.get("line_number", 0),
        }
        
        grouped[severity].append(finding)
    
    return grouped


def format_findings_report(findings: Dict[str, List[dict]], output_path: str) -> int:
    """Format and write findings report. Returns exit code."""
    high_count = len(findings.get("HIGH", []))
    medium_count = len(findings.get("MEDIUM", []))
    low_count = len(findings.get("LOW", []))
    
    with open(output_path, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("BANDIT PYTHON SECURITY AUDIT FINDINGS\n")
        f.write("=" * 80 + "\n\n")
        
        # Summary
        f.write("SUMMARY\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total HIGH findings:   {high_count}\n")
        f.write(f"Total MEDIUM findings: {medium_count}\n")
        f.write(f"Total LOW findings:    {low_count}\n")
        f.write("\n")
        
        if high_count > 0:
            f.write("⚠️  ⚠️  ⚠️  DEPLOYMENT BLOCKED: HIGH SEVERITY FINDINGS PRESENT ⚠️  ⚠️  ⚠️\n\n")
        elif medium_count > 0:
            f.write("⚠️  CAUTION: MEDIUM SEVERITY FINDINGS PRESENT\n\n")
        else:
            f.write("✓ All HIGH and MEDIUM findings resolved\n\n")
        
        # Critical rules to verify
        f.write("CRITICAL RULES FOR THIS CODEBASE:\n")
        f.write("-" * 80 + "\n")
        f.write("B105/B106/B107: Hardcoded passwords and API keys\n")
        f.write("  → All credentials must come from environment variables\n")
        f.write("B322: Insecure eval/pickle\n")
        f.write("  → Use safe alternatives (json, ast, etc.)\n")
        f.write("B501/B502: Insecure TLS and temp files\n")
        f.write("  → Verify SSL certificates; use secure temp file creation\n")
        f.write("B608: SQL injection via string formatting\n")
        f.write("  → All SQLite queries must use parameterized statements\n")
        f.write("\n\n")
        
        # Detailed findings by severity
        for severity in ["HIGH", "MEDIUM", "LOW"]:
            findings_list = findings.get(severity, [])
            if not findings_list:
                continue
            
            f.write("\n")
            f.write("=" * 80 + "\n")
            f.write(f"{severity} SEVERITY FINDINGS ({len(findings_list)})\n")
            f.write("=" * 80 + "\n\n")
            
            for i, finding in enumerate(findings_list, 1):
                test_id = finding.get("test_id", "")
                test_name = finding.get("test_name", "")
                filename = finding.get("filename", "")
                line_number = finding.get("line_number", 0)
                issue_text = finding.get("issue_text", "")
                confidence = finding.get("issue_confidence", "UNKNOWN")
                
                f.write(f"{i}. {test_id} - {test_name}\n")
                f.write(f"   Severity: {severity}\n")
                f.write(f"   Confidence: {confidence}\n")
                f.write(f"   File: {filename}:{line_number}\n")
                f.write(f"\n   Issue:\n")
                f.write(f"   {issue_text}\n")
                
                # Get remediation guidance
                if test_id in REMEDIATION_GUIDANCE:
                    guidance = REMEDIATION_GUIDANCE[test_id]
                    f.write(f"\n   Recommended Fix:\n")
                    f.write(f"   {guidance['fix']}\n")
                
                f.write("\n")
        
        # Summary and next steps
        f.write("\n")
        f.write("=" * 80 + "\n")
        f.write("NEXT STEPS\n")
        f.write("=" * 80 + "\n\n")
        
        if high_count > 0:
            f.write("1. URGENT: Fix all HIGH severity findings immediately\n")
            f.write("2. Implement recommended fixes listed above\n")
            f.write("3. Re-run Bandit audit to verify fixes\n")
            f.write("4. Deployment is blocked until HIGH findings are resolved\n")
        elif medium_count > 0:
            f.write("1. Review and address MEDIUM severity findings\n")
            f.write("2. For each finding, verify the fix is appropriate\n")
            f.write("3. Add comments explaining why some findings are acceptable\n")
            f.write("4. Re-run Bandit audit after fixes\n")
        else:
            f.write("✓ All HIGH and MEDIUM severity findings have been resolved\n")
            f.write("✓ Python code is ready for deployment\n")
        
        f.write("\nDocumentation:\n")
        f.write("  - Full JSON report: bandit_reports/bandit_report.json\n")
        f.write("  - Audit record: docs/security/BANDIT_AUDIT.md\n")
    
    return 1 if high_count > 0 else 0


def main():
    if len(sys.argv) < 2:
        print("Usage: parse_bandit_report.py <report.json> [output.txt]")
        sys.exit(1)
    
    report_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "bandit_findings.txt"
    
    print(f"Loading Bandit report from {report_path}...")
    report = load_bandit_report(report_path)
    
    print("Parsing findings...")
    findings = parse_findings(report)
    
    print(f"Generating report to {output_path}...")
    exit_code = format_findings_report(findings, output_path)
    
    # Print summary
    high_count = len(findings.get("HIGH", []))
    medium_count = len(findings.get("MEDIUM", []))
    
    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)
    print(f"HIGH findings:   {high_count}")
    print(f"MEDIUM findings: {medium_count}")
    print(f"Report written to: {output_path}")
    print()
    
    if exit_code != 0:
        print("❌ DEPLOYMENT BLOCKED: HIGH severity findings present")
    else:
        print("✓ Security audit passed")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

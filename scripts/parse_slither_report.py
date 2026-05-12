#!/usr/bin/env python3
"""
Parse Slither JSON report and generate structured audit findings.

Groups findings by severity and generates human-readable output with remediation guidance.
Exits with code 1 if any HIGH severity findings exist, code 0 otherwise.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict


SEVERITY_LEVELS = ["HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFORMATIONAL": 3}

# Common Slither detectors and recommended fixes
REMEDIATION_GUIDANCE = {
    "reentrancy-eth": {
        "description": "Reentrancy vulnerability in ETH transfer",
        "fix": "Apply ReentrancyGuard from OpenZeppelin to all state-changing functions that transfer ETH",
    },
    "reentrancy-benign": {
        "description": "Benign reentrancy pattern (typically safe but should be reviewed)",
        "fix": "Verify the function cannot be exploited; apply ReentrancyGuard if uncertain",
    },
    "divide-before-multiply": {
        "description": "Division before multiplication causes precision loss",
        "fix": "Reorder arithmetic to multiply before dividing to maintain precision",
    },
    "unchecked-transfer": {
        "description": "ERC-20 transfer return value not checked",
        "fix": "Add require(success, \"Transfer failed\") after every transfer() or transferFrom() call",
    },
    "missing-zero-check": {
        "description": "Address parameter not checked for zero address",
        "fix": "Add require(address != address(0)) validation in constructors and setters",
    },
    "locked-ether": {
        "description": "Contract can receive ETH but has no withdrawal function",
        "fix": "Add withdraw() function or use payable() with appropriate guards",
    },
    "constant-function-asm": {
        "description": "Constant function modified via assembly",
        "fix": "Review assembly code; ensure state is not modified in view/pure functions",
    },
    "tx-origin": {
        "description": "Use of tx.origin for authentication (vulnerable to phishing)",
        "fix": "Use msg.sender instead of tx.origin for all authorization checks",
    },
    "assembly": {
        "description": "Use of inline assembly",
        "fix": "Review assembly code carefully; ensure it matches expected behavior",
    },
    "solc-version": {
        "description": "Use of floating pragma or version incompatibility",
        "fix": "Pin pragma to specific version: pragma solidity 0.8.X;",
    },
}


def load_slither_report(report_path: str) -> dict:
    """Load and parse Slither JSON report."""
    try:
        with open(report_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load Slither report: {e}")
        sys.exit(1)


def parse_findings(report: dict) -> Dict[str, List[dict]]:
    """
    Parse Slither results into grouped findings.
    
    Returns:
        Dict mapping severity to list of findings
    """
    grouped = defaultdict(list)
    
    if "results" not in report:
        print("⚠️  No results in Slither report")
        return grouped
    
    for result in report.get("results", []):
        severity = result.get("impact", "INFORMATIONAL").upper()
        
        # Normalize severity
        if severity not in SEVERITY_LEVELS:
            severity = "INFORMATIONAL"
        
        finding = {
            "detector": result.get("check_name", "unknown"),
            "severity": severity,
            "description": result.get("description", ""),
            "elements": result.get("elements", []),
            "type": result.get("type", ""),
        }
        
        grouped[severity].append(finding)
    
    return grouped


def format_findings_report(findings: Dict[str, List[dict]], output_path: str) -> Tuple[int, int]:
    """
    Format and write findings report.
    
    Returns:
        Tuple of (high_count, medium_count)
    """
    high_count = len(findings.get("HIGH", []))
    medium_count = len(findings.get("MEDIUM", []))
    low_count = len(findings.get("LOW", []))
    info_count = len(findings.get("INFORMATIONAL", []))
    
    with open(output_path, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("SLITHER SMART CONTRACT SECURITY AUDIT FINDINGS\n")
        f.write("=" * 80 + "\n\n")
        
        # Summary
        f.write("SUMMARY\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total HIGH findings:          {high_count}\n")
        f.write(f"Total MEDIUM findings:        {medium_count}\n")
        f.write(f"Total LOW findings:           {low_count}\n")
        f.write(f"Total INFORMATIONAL findings: {info_count}\n")
        f.write("\n")
        
        if high_count > 0:
            f.write("⚠️  ⚠️  ⚠️  DEPLOYMENT BLOCKED: HIGH SEVERITY FINDINGS PRESENT ⚠️  ⚠️  ⚠️\n\n")
        elif medium_count > 0:
            f.write("⚠️  CAUTION: MEDIUM SEVERITY FINDINGS PRESENT\n\n")
        else:
            f.write("✓ All HIGH and MEDIUM findings resolved\n\n")
        
        # Detailed findings by severity
        for severity in SEVERITY_LEVELS:
            findings_list = findings.get(severity, [])
            if not findings_list:
                continue
            
            f.write("\n")
            f.write("=" * 80 + "\n")
            f.write(f"{severity} SEVERITY FINDINGS ({len(findings_list)})\n")
            f.write("=" * 80 + "\n\n")
            
            for i, finding in enumerate(findings_list, 1):
                detector = finding.get("detector", "unknown")
                description = finding.get("description", "No description")
                
                f.write(f"{i}. {detector.upper()}\n")
                f.write(f"   Severity: {severity}\n")
                f.write(f"   Type: {finding.get('type', 'N/A')}\n")
                f.write(f"\n   Description:\n")
                f.write(f"   {description}\n")
                
                # Get remediation guidance
                if detector in REMEDIATION_GUIDANCE:
                    guidance = REMEDIATION_GUIDANCE[detector]
                    f.write(f"\n   Recommended Fix:\n")
                    f.write(f"   {guidance['fix']}\n")
                
                # List affected elements
                elements = finding.get("elements", [])
                if elements:
                    f.write(f"\n   Affected Elements:\n")
                    for elem in elements[:3]:  # Show first 3
                        if isinstance(elem, dict):
                            name = elem.get("name", "unknown")
                            contract = elem.get("contract", "")
                            f.write(f"   - {contract}.{name}\n")
                        else:
                            f.write(f"   - {elem}\n")
                    if len(elements) > 3:
                        f.write(f"   ... and {len(elements) - 3} more\n")
                
                f.write("\n")
        
        # Summary and next steps
        f.write("\n")
        f.write("=" * 80 + "\n")
        f.write("NEXT STEPS\n")
        f.write("=" * 80 + "\n\n")
        
        if high_count > 0:
            f.write("1. URGENT: Fix all HIGH severity findings immediately\n")
            f.write("2. Implement recommended fixes listed above\n")
            f.write("3. Re-run Slither audit to verify fixes\n")
            f.write("4. Deployment is blocked until HIGH findings are resolved\n")
        elif medium_count > 0:
            f.write("1. Review and address MEDIUM severity findings\n")
            f.write("2. For each finding, verify the fix is appropriate\n")
            f.write("3. Consider adding comments explaining why some findings are acceptable\n")
            f.write("4. Re-run Slither audit after fixes\n")
        else:
            f.write("✓ All HIGH and MEDIUM severity findings have been resolved\n")
            f.write("✓ Contract is ready for security review and deployment\n")
        
        f.write("\n")
        f.write("Documentation:\n")
        f.write("  - Full JSON report: slither_reports/slither_report.json\n")
        f.write("  - Audit record: docs/security/SLITHER_AUDIT.md\n")
    
    return high_count, medium_count


def main():
    if len(sys.argv) < 2:
        print("Usage: parse_slither_report.py <report.json> [output.txt]")
        sys.exit(1)
    
    report_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "slither_findings.txt"
    
    print(f"Loading Slither report from {report_path}...")
    report = load_slither_report(report_path)
    
    print("Parsing findings...")
    findings = parse_findings(report)
    
    print(f"Generating report to {output_path}...")
    high_count, medium_count = format_findings_report(findings, output_path)
    
    # Print summary
    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)
    print(f"HIGH findings:    {high_count}")
    print(f"MEDIUM findings:  {medium_count}")
    print(f"Report written to: {output_path}")
    print()
    
    if high_count > 0:
        print("❌ DEPLOYMENT BLOCKED: HIGH severity findings present")
        sys.exit(1)
    else:
        print("✓ Security audit passed")
        sys.exit(0)


if __name__ == "__main__":
    main()

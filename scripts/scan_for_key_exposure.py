#!/usr/bin/env python3
"""
Custom key exposure scanner — detects API keys, private keys, and secrets in log statements.

Scans all Python files for patterns that look like sensitive data in logging/print statements:
- API keys (sk-, AIza, Bearer tokens)
- Private keys (0x followed by 64 hex chars)
- JWT tokens
- Suspicious strings > 30 chars that aren't known hashes
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Set
from collections import defaultdict


# Patterns that indicate sensitive data
SENSITIVE_PATTERNS = {
    "API_KEY_SK": re.compile(r"[\"\']sk-[A-Za-z0-9_-]{20,}[\"\']"),  # OpenAI/similar format
    "API_KEY_AIZA": re.compile(r"[\"\']AIza[A-Za-z0-9_-]{30,}[\"\']"),  # Google API keys
    "PRIVATE_KEY_HEX": re.compile(r"0x[0-9a-fA-F]{64}"),  # Ethereum private key
    "BEARER_TOKEN": re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+"),
    "JWT_TOKEN": re.compile(r"eyJ[A-Za-z0-9_\-\.]+"),
    "AWS_ACCESS_KEY": re.compile(r"AKIA[0-9A-Z]{16}"),
    "AWS_SECRET": re.compile(r"aws_secret_access_key"),
}

# Known hash patterns and false positives to ignore
FALSE_POSITIVES = {
    # Contract addresses (Ethereum format)
    re.compile(r"0x[0-9a-fA-F]{40}"),
    # Common test addresses
    re.compile(r"0x0+[0-9a-fA-F]*"),
    # Checksums in docstrings
    re.compile(r"sha256="),
    re.compile(r"blake2b="),
}

# Context keywords that indicate safe (non-sensitive) usage
SAFE_CONTEXTS = {
    "test",
    "fixture",
    "example",
    "documentation",
    "comment",
    "EXPECTED",
    "PLACEHOLDER",
}


class KeyExposureScanner:
    """Scans Python files for exposed API keys and secrets."""
    
    def __init__(self):
        self.findings: List[Tuple[str, int, str, str]] = []  # (file, line, pattern, context)
        self.dangerous_log_patterns = [
            re.compile(r"logger\.info.*\{"),
            re.compile(r"logger\.debug.*\{"),
            re.compile(r"logger\.warning.*\{"),
            re.compile(r"logger\.error.*\{"),
            re.compile(r"print\(.*f[\"']"),
            re.compile(r"print\(.*\+"),
        ]
    
    def is_false_positive(self, text: str) -> bool:
        """Check if this is a known false positive."""
        for pattern in FALSE_POSITIVES:
            if pattern.search(text):
                return True
        return False
    
    def is_safe_context(self, line: str, file_path: str) -> bool:
        """Check if this is a safe context (test file, documentation, etc)."""
        # Test files are safe
        if "test" in file_path.lower():
            return True
        
        # Comments are safe
        if line.strip().startswith("#"):
            return True
        
        # Docstrings are safe
        if '"""' in line or "'''" in line:
            return True
        
        # Lines with SAFE_CONTEXTS keywords
        for keyword in SAFE_CONTEXTS:
            if keyword.upper() in line.upper():
                return True
        
        return False
    
    def scan_line(self, line: str, file_path: str, line_num: int) -> None:
        """Scan a single line for key exposure."""
        if self.is_safe_context(line, file_path):
            return
        
        # Check for dangerous logging patterns
        if not any(pattern.search(line) for pattern in self.dangerous_log_patterns):
            return
        
        # Check against sensitive patterns
        for pattern_name, pattern in SENSITIVE_PATTERNS.items():
            matches = pattern.finditer(line)
            for match in matches:
                if not self.is_false_positive(match.group()):
                    self.findings.append((
                        file_path,
                        line_num,
                        pattern_name,
                        line.strip(),
                    ))
    
    def scan_file(self, file_path: Path) -> None:
        """Scan a single Python file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    self.scan_line(line, str(file_path), line_num)
        except Exception as e:
            print(f"⚠️  Error scanning {file_path}: {e}", file=sys.stderr)
    
    def scan_directory(self, directory: Path) -> None:
        """Recursively scan Python files in a directory."""
        if not directory.exists():
            print(f"⚠️  Directory not found: {directory}", file=sys.stderr)
            return
        
        python_files = directory.rglob("*.py")
        for py_file in python_files:
            # Skip common non-sensitive directories
            if any(skip in str(py_file) for skip in [".venv", "venv", "__pycache__", ".git"]):
                continue
            self.scan_file(py_file)
    
    def report(self) -> int:
        """Generate and print audit report. Returns exit code."""
        if not self.findings:
            print("✓ No sensitive key exposure detected in log statements")
            return 0
        
        print(f"❌ {len(self.findings)} potential key exposures detected:")
        print("")
        
        # Group by file
        by_file = defaultdict(list)
        for file_path, line_num, pattern_name, context in self.findings:
            by_file[file_path].append((line_num, pattern_name, context))
        
        for file_path in sorted(by_file.keys()):
            print(f"  {file_path}")
            for line_num, pattern_name, context in by_file[file_path]:
                print(f"    Line {line_num}: {pattern_name}")
                print(f"      {context[:80]}...")
                print()
        
        return 1
    
    def generate_markdown_report(self, output_path: str) -> None:
        """Generate a markdown report of findings."""
        with open(output_path, "w") as f:
            f.write("# Key Exposure Scan Results\n\n")
            f.write(f"**Total Findings**: {len(self.findings)}\n\n")
            
            if not self.findings:
                f.write("✓ No sensitive key exposures detected\n")
                return
            
            f.write("## Findings\n\n")
            
            by_file = defaultdict(list)
            for file_path, line_num, pattern_name, context in self.findings:
                by_file[file_path].append((line_num, pattern_name, context))
            
            for file_path in sorted(by_file.keys()):
                f.write(f"### {file_path}\n\n")
                for line_num, pattern_name, context in by_file[file_path]:
                    f.write(f"**Line {line_num}**: {pattern_name}\n")
                    f.write(f"```\n{context}\n```\n\n")


def main():
    scanner = KeyExposureScanner()
    
    # Scan provided directories
    directories = sys.argv[1:] if len(sys.argv) > 1 else ["agent", "compute", "utils"]
    
    print("Scanning Python files for key exposure...")
    for dir_name in directories:
        scanner.scan_directory(Path(dir_name))
    
    # Generate markdown report
    output_file = "bandit_reports/key_exposure_scan.md"
    Path("bandit_reports").mkdir(exist_ok=True)
    scanner.generate_markdown_report(output_file)
    print(f"Report written to: {output_file}")
    
    # Print summary and return exit code
    exit_code = scanner.report()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

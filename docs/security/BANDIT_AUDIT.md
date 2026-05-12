# Bandit Python Security Audit

**Audit Date**: [To be populated after first audit run]  
**Bandit Version**: 1.7.5  
**Status**: [To be updated as findings are resolved]

## Executive Summary

This document records all findings from the Bandit static analysis tool applied to the Flashix Python codebase (agent/, compute/, utils/).

### Audit Results Summary

| Severity | Count | Status |
|----------|-------|--------|
| HIGH | [TBD] | [Pending] |
| MEDIUM | [TBD] | [Pending] |
| LOW | [TBD] | [Pending] |

**Deployment Status**: [Blocked until HIGH findings = 0]

---

## Critical Rules for Flashix

The following Bandit rules are especially critical for this codebase:

### B105/B106/B107: Hardcoded Credentials
**Issue**: API keys, private keys, or passwords hardcoded in source  
**Impact**: Credential exposure in Git history and production deployments  
**Fix**: All credentials must come from environment variables

```python
# ❌ WRONG - Never do this
API_KEY = "sk-1234567890abcdef"

# ✓ CORRECT
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable not set")
```

### B322: Insecure Deserialization
**Issue**: Using pickle.loads() on untrusted data  
**Impact**: Remote code execution vulnerability  
**Fix**: Use json.loads() or ast.literal_eval() for safe parsing

```python
# ❌ WRONG
data = pickle.loads(untrusted_data)

# ✓ CORRECT
import json
data = json.loads(untrusted_data)
```

### B501/B502: Insecure TLS and Temp Files
**Issue**: Unverified SSL certificates; insecure temporary file creation  
**Impact**: Man-in-the-middle attacks; temporary file hijacking  
**Fix**: Always verify SSL; use secure temp file operations

```python
# ❌ WRONG
response = requests.get(url, verify=False)

# ✓ CORRECT
response = requests.get(url, verify=True)

# ❌ WRONG
import tempfile
with open("/tmp/data.txt", "w") as f:
    f.write(data)

# ✓ CORRECT
import tempfile
with tempfile.NamedTemporaryFile(delete=False) as f:
    f.write(data)
    temp_path = f.name
```

### B608: SQL Injection via String Formatting
**Issue**: SQL queries built via string concatenation  
**Impact**: SQL injection vulnerability  
**Fix**: Use parameterized queries with placeholders

```python
# ❌ WRONG
query = f"SELECT * FROM users WHERE id = {user_id}"
cursor.execute(query)

# ✓ CORRECT
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_id,))
```

---

## Finding Details

This section will be populated with detailed findings from each audit run.

### HIGH Severity Findings

| Finding ID | Test ID | Location | Issue | Resolution | Status |
|-----------|---------|----------|-------|-----------|--------|
| [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |

### MEDIUM Severity Findings

| Finding ID | Test ID | Location | Issue | Resolution | Status |
|-----------|---------|----------|-------|-----------|--------|
| [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |

---

## Secret Scanning

### API Key Exposure Detection

The custom secret scanner detects:
- OpenAI API keys (sk-*)
- Google API keys (AIza*)
- AWS credentials
- Ethereum private keys (0x followed by 64 hex chars)
- JWT tokens
- Bearer tokens

**Baseline File**: `.secrets.baseline`

To audit the baseline:
```bash
detect-secrets audit .secrets.baseline
```

### Last Scan Results

- **API Keys Found**: [TBD]
- **Private Keys Found**: [TBD]
- **Suspicious Strings Found**: [TBD]
- **Status**: [TBD]

---

## Audit Process

1. **Install Bandit and detect-secrets**:
   ```bash
   pip install bandit==1.7.5 detect-secrets==1.4.0
   ```

2. **Run the audit**:
   ```bash
   bash scripts/security_audit_python.sh
   ```

3. **Review findings**:
   - Bandit report: `bandit_reports/bandit_report.json`
   - Parsed summary: `bandit_reports/bandit_findings.txt`
   - Secret scan: `bandit_reports/key_exposure_scan.md`

4. **Fix issues**:
   - Implement recommended fixes for all HIGH severity findings
   - For MEDIUM findings, document why they are acceptable

5. **Verify fixes**:
   ```bash
   bash scripts/security_audit_python.sh
   ```

---

## Logging Best Practices

To prevent accidental credential exposure in logs, follow these patterns:

```python
import logging
logger = logging.getLogger(__name__)

# ❌ WRONG - Logs the full API key
api_key = os.getenv("API_KEY")
logger.info(f"Using API key: {api_key}")

# ✓ CORRECT - Masks the key
def sanitize_for_logging(value: str, show_chars: int = 4) -> str:
    """Mask sensitive strings for logging."""
    if len(value) <= show_chars * 2:
        return "*" * len(value)
    return f"{value[:show_chars]}...{value[-show_chars:]}"

logger.info(f"Using API key: {sanitize_for_logging(api_key)}")
# Output: "Using API key: sk-1...def5"
```

---

## Final Approval Checklist

- [ ] All HIGH severity findings resolved
- [ ] All MEDIUM severity findings reviewed and justified
- [ ] No API keys or secrets in logs or error messages
- [ ] Secret baseline reviewed (.secrets.baseline)
- [ ] Custom key exposure scan passed
- [ ] Code review completed for all fixes
- [ ] Bandit audit passed with zero HIGH findings

---

## Audit History

| Date | Auditor | Status | HIGH | MEDIUM | LOW |
|------|---------|--------|------|--------|-----|
| [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |

---

*Last Updated: [TBD]*  
*Maintained by: Flashix Security Team*

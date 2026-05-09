CONTRIBUTING
============

Please see the CONTRIBUTING.md in the repository root for guidelines.
CONTRIBUTING
============

Development Process
- Fork the repo and create a feature branch named `feat/your-feature` or `fix/issue-123`.
- Run tests and linters locally before submitting a PR.
- Write clear commit messages and follow Conventional Commits where possible.

Code Style
- Python: PEP 8, autoformat with Black. Type hints required; run `mypy` in CI.
- Node: Airbnb style guided by ESLint.
- Docstrings: Google-style required for public functions.

Testing
- Unit tests required for new features, >80% coverage for major modules.
- Integration tests required for cross-component changes.

Code Review
- Reviewers check correctness, security (no secrets), performance, and documentation.

Issue Reporting
- Use issue templates in .github/ISSUE_TEMPLATE/ when opening new issues.

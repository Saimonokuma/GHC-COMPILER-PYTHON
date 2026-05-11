## REPO CONTEXT (Last updated: 2024-05-24)
**Project:** ghc-compiler-python
**Languages:** Python, Bash
**Build:** hatchling (PEP 621), `python -m build`
**Test:** pytest
**Lint:** (no specific listed, standard ruff/flake8 would be expected)
**Docs:** README.md, DEPLOYMENT_OPERATIVE_PLAN.md
**Key Conventions:**
- Python code uses `pathlib` heavily instead of `os.path`.
- Bash scripts use `set -euo pipefail`.
- Strong emphasis on hermetic environment and avoiding pollution from local installations.

## 2024-05-24 - Centralized Error Handling & Path Resolution Extraction
**Pattern:** Scattered error logging via `sys.stderr.write`, duplicate logic for path scanning in `wrapper.py`, repeated `echo "FATAL..." >&2` in shell scripts.
**Improvement:** Centralized logic into `_fatal_error()` in Python and `die()` in Bash, replacing magic numbers with constants. Abstracted duplicated directory searches into `_walk_ghc_lib_dir` and `_get_base_lib_paths`. Added `pythonpath = ["."]` in `pyproject.toml` to clean up Pytest.
**Impact:** Enhances the single-source-of-truth for runtime paths, standardizes exit mechanisms across the Python/Bash polyglot footprint, reduces error-handling technical debt, and improves long-term testability without environment hacks.

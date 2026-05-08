## REPO CONTEXT (Last updated: 2025-05-08)
**Project:** ghc-compiler-python
**Languages:** Python, Bash
**Build:** uv build
**Test:** uv run pytest
**Lint:** uv run ruff check .
**Docs:** README.md, DEPLOYMENT_OPERATIVE_PLAN.md
**Key Conventions:** Uses PEP 621, wrapper script to dynamically execute bundled binaries, Python 3.8+ required.

## 2025-05-08 - Centralized Error Handling, Type Safety, and Deduplication
**Pattern:** wrapper.py was using legacy `from typing import List, Optional` type hints, redundant `sys.exit(1)` and `sys.stderr.write` throughout for error handling, and duplicated file search logic.
**Improvement:** Updated type hints to PEP 585/PEP 604 modern Python 3.12 syntax. Abstracted repeated logic in `_find_ghc_settings` and `_find_package_databases` to a generic `_find_in_locations`. Replaced scatter `sys.exit()` and output with a single custom `WrapperError` caught inside `_execute_tool`.
**Impact:** Consistent modern Python practices, reduced code duplication by a measurable margin, and a reliable centralized exception hierarchy.

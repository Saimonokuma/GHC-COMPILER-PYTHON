## REPO CONTEXT (Last updated: 2024-05-10)
**Project:** ghc-compiler-python
**Languages:** Python, Bash, Shell
**Build:** hatchling
**Test:** pytest
**Lint:** (no specific configuration spotted, but ruff is commonly used)
**Docs:** README.md, DEPLOYMENT_OPERATIVE_PLAN.md, WHITEPAPER.md, Interactive_Plan.md (missing)
**Key Conventions:**
- Python code uses `pathlib` mostly, but `wrapper.py` needs better types and refactoring.
- Consistent error handling logic should be enforced with a central `die` method.
- No magic constants.
- Don't duplicate code snippets.

## YYYY-MM-DD - Initial Structural Refactor
**Pattern:** Duplicated `os.walk` code and verbose `sys.stderr.write(..); sys.exit(1)`.
**Improvement:** Centralize error reporting (`die`), path resolution logic, and eliminate repeated directory walking (`_iter_lib_dirs()`).
**Impact:** `wrapper.py` becomes more readable, maintainable, and type-safe.
## Handoff (2026-05-18) — From: OUROBOROS → To: FORGE
**File:** tests/test_e2e.py
**Finding:** End-to-end tests fail when run locally using `uv run pytest`. The tests (`test_ghc_version`, `test_ghc_compilation`, `test_cabal_version`) fail because `ghc-wrapper` executes but fails to locate the bundled compiler binaries (`ghc`, `cabal`). The skip condition in `test_e2e.py` only checks for the existence of `ghc-wrapper` and a C-linker, but does not verify if the actual `ghc-bindist` payload has been fetched.
**Suggested Action:** Fix the test environment so that e2e tests correctly fetch and stage the binaries before running, or improve the skip conditions in `tests/test_e2e.py` to skip these tests if the bundled `ghc` and `cabal` binaries are not present in `ghc-bindist`.

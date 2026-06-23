## Handoff (2026-06-23) — From: OUROBOROS → To: CRUCIBLE
**File:** tests/test_e2e.py
**Finding:** `test_e2e.py` does not correctly skip tests when `ghc-wrapper` is installed via `uv` or `pip` but the underlying bundled binaries (`ghc`, `cabal`) are not downloaded/present. This causes `uv run pytest` to fail with `FATAL ERROR: Bundled compiler binary 'ghc' could not be located.` during standard development cycles.
**Suggested Action:** Update the `@pytest.mark.skipif` conditions in `tests/test_e2e.py` to verify that the actual bundled `ghc` and `cabal` binaries exist before allowing the E2E tests to run, or mock the subprocess calls so the test can pass without requiring the full toolchain download.

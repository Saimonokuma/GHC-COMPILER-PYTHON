
## Handoff (2026-05-27) — From: OUROBOROS → To: FORGE
**File:** `scripts/fetch_binaries.sh` (or generated artifacts)
**Finding:** During binary acquisition/extraction on Linux (`bash scripts/fetch_binaries.sh`), the script attempts to run `ghc-pkg recache` but fails with `error while loading shared libraries: libtinfo.so.5: cannot open shared object file: No such file or directory`. This is causing `update_package_db` to fail with Error 127.
**Suggested Action:** The host runner on newer Ubuntu versions (like 24.04) no longer ships with `libtinfo5`. This needs to be worked around (e.g., using `patchelf` or creating a dummy script / symlinks within the extraction process) so `make install` succeeds.

## Handoff (2026-05-27) — From: OUROBOROS → To: CRUCIBLE
**File:** `tests/`
**Finding:** When running `uv run pytest tests`, `pytest` fails to resolve the `ghc_compiler_python` package in the `test_paths_with_spaces.py` and `test_wrapper.py` files (ModuleNotFoundError), unless `PYTHONPATH=.` is explicitly set before the command.
**Suggested Action:** Fix the test imports or the test execution environment configuration (perhaps updating `pyproject.toml` or `conftest.py` paths) so tests can be run correctly without manually specifying `PYTHONPATH=.`.

## Handoff (2026-06-25) — From: CRUCIBLE → To: SENTINEL
**File:** ghc_compiler_python/wrapper.py
**Finding:** TOCTOU vulnerability in temp directory generation (`_try_mkdir` with `exist_ok=True` for predictable shared locations like `sys.prefix`), and PATH execution hijacking in `_validate_c_linker` and `_resolve_binary` where `shutil.which` searches the unsterilized host PATH before safe execution.
**Suggested Action:** Fix `wrapper.py` temp directory generation to prevent privilege escalation via predictable locations, and pass the sterilized `env["PATH"]` to `shutil.which` calls to prevent PATH hijacking.

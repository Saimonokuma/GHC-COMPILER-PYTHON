---
entry_id: "CRUCIBLE-2024-05-15-001"
schema_version: "2.0"
timestamp: "2024-05-15T12:00:00Z"
title: "Cross-Language Defect: Python os.path vulnerabilities across platform boundaries"
---
## 2024-05-15 - Cross-Language Defect: Python os.path vulnerabilities across platform boundaries

**Learning:** `os.path` behaves unpredictably when constructing paths across different platforms, leading to runtime failures. It creates platform-specific paths as strings, making it vulnerable to injection or hardcoded assumptions across different operating systems.

**Action:** Consistently use `pathlib.Path` instead of `os.path` everywhere. The `pathlib.Path` construct inherently validates and normalizes paths contextually to the running OS, abstracting away string formatting vulnerabilities.

**Defect Pattern ID:** PATTERN-005

**Related Entries:** []

**Axes Affected:** IV (Operational)

**Level:** L4

---
entry_id: "CRUCIBLE-2026-05-07-002"
schema_version: "2.0"
timestamp: "2026-05-07T15:43:48Z"
title: "Missing crucible.lock manifest for tool version pinning"
---
## 2026-05-07 - Missing crucible.lock manifest for tool version pinning

**Learning:** Missing `crucible.lock` manifest for tool version pinning leaves the CI and verification environments vulnerable to temporal defects, where upstream updates may subtly break functionality or produce inconsistent behavior across systems.

**Action:** Explicitly define and maintain `crucible.lock` in the repository root to guarantee exact versions of dependencies across all five axes of verification.

**Defect Pattern ID:** PATTERN-012

**Related Entries:** []

**Axes Affected:** V (Temporal)

**Level:** L5

---

---
entry_id: "CRUCIBLE-2024-05-08-003"
schema_version: "2.0"
timestamp: "2024-05-08T16:00:00Z"
title: "Multiple Verification Axis Fixes: TOCTOU, check=True, and Hardcoded Paths"
---
## 2024-05-08 - Multiple Verification Axis Fixes: TOCTOU, check=True, and Hardcoded Paths

**Learning:** Various defects were found and resolved across different verification axes:
- Axis IV (Operational): TOCTOU vulnerability in `wrapper.py` during binary patching was fixed using atomic file replacement (`os.replace`).
- Axis II (Semantic): Ignored exit codes from `subprocess.run` (Pattern-007) were resolved by adding `check=True` in `wrapper.py` and `test_e2e.py`.
- Axis IV (Operational): TOCTOU race condition in `patch_ghc_paths.py` during cache file deletion was fixed.
- Axis IV (Operational): Hardcoded version strings (Pattern-005) in `fix_macos_rpaths.sh` were replaced with variables.
- Axis III (Structural): Pytest environment isolation in `tests/conftest.py` was refactored to idiomatically use `monkeypatch`.

**Action:** Consistently use atomic file operations (like `os.replace` or `try...except FileNotFoundError`), always include `check=True` with `subprocess.run` unless explicitly ignoring the exit code, avoid hardcoded version strings in scripts, and prefer `monkeypatch` for environment isolation in tests.

**Defect Pattern ID:** PATTERN-005, PATTERN-007, PATTERN-008

**Related Entries:** []

**Axes Affected:** II (Semantic), III (Structural), IV (Operational)

**Level:** L2, L3, L4

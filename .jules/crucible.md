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
entry_id: "CRUCIBLE-2026-05-13-003"
schema_version: "2.0"
timestamp: "2026-05-13T12:00:00Z"
title: "No Defects Found"
---
## 2026-05-13 - No Defects Found

**Learning:** All five verification axes currently pass with no regressions. Previous defects (PATTERN-005, PATTERN-012) are fully resolved.

**Action:** No code changes necessary. Updated journal and queue.

**Defect Pattern ID:** None

**Related Entries:** []

**Axes Affected:** None

**Level:** None
---
entry_id: "CRUCIBLE-2026-05-17-004"
schema_version: "2.0"
timestamp: "2026-05-17T12:00:00Z"
title: "Multiple Hardening Fixes: TOCTOU, ignored exit code, side-effect comprehension"
---
## 2026-05-17 - Multiple Hardening Fixes: TOCTOU, ignored exit code, side-effect comprehension

**Learning:** Replaced check-then-act with  to fix a TOCTOU race condition (PATTERN-008). Added  to  to enforce error handling (PATTERN-007). Eliminated a side-effecting list comprehension.

**Action:** Addressed the vulnerabilities in  in ,  and .

**Defect Pattern ID:** PATTERN-008, PATTERN-007

**Related Entries:** []

**Axes Affected:** II (Semantic), III (Structural), IV (Operational)

**Level:** L2, L3

---
---
entry_id: "CRUCIBLE-2026-05-17-004"
schema_version: "2.0"
timestamp: "2026-05-17T12:00:00Z"
title: "Multiple Hardening Fixes: TOCTOU, ignored exit code, side-effect comprehension"
---
## 2026-05-17 - Multiple Hardening Fixes: TOCTOU, ignored exit code, side-effect comprehension

**Learning:** Replaced check-then-act with `unlink(missing_ok=True)` to fix a TOCTOU race condition (PATTERN-008). Added `check=True` to `subprocess.run` to enforce error handling (PATTERN-007). Eliminated a side-effecting list comprehension.

**Action:** Addressed the vulnerabilities in `wrapper.py` in `PackageDBResource.patch_build_time`, `_resolve_runtime_paths` and `_ghc_pkg_recache`.

**Defect Pattern ID:** PATTERN-008, PATTERN-007

**Related Entries:** []

**Axes Affected:** II (Semantic), III (Structural), IV (Operational)

**Level:** L2, L3

---
---
entry_id: "CRUCIBLE-2026-05-25-005"
schema_version: "2.0"
timestamp: "2026-05-25T16:00:00Z"
title: "Fix unquoted standalone path regex parsing"
---
## 2026-05-25 - Fix unquoted standalone path regex parsing

**Learning:** When matching and quoting placeholders with a regex that ensures trailing text is included (e.g. `(@GHC_PREFIX@[^\s"]+)`), the `+` quantifier incorrectly requires at least one character to follow the placeholder. If the placeholder is completely standalone, it won't be matched and therefore won't be quoted. This can lead to unquoted paths when the prefix contains spaces, causing shell and parsing errors downstream.

**Action:** Changed the quantifier from `+` to `*` (`[^\s"]*`) in the regex replacement logic inside `_resolve_runtime_paths` to properly match and quote standalone `@GHC_PREFIX@` markers.

**Defect Pattern ID:** PATTERN-004

**Related Entries:** []

**Axes Affected:** II (Semantic), IV (Operational)

**Level:** L2

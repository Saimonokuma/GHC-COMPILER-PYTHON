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
entry_id: "CRUCIBLE-$(date +%Y-%m-%d)-003"
schema_version: "2.0"
timestamp: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
title: "Axis II: Subprocess run failure handling"
---
## $(date +%Y-%m-%d) - Axis II: Subprocess run failure handling

**Learning:** When using `subprocess.run()`, failures (non-zero exit codes) are ignored by default. If you intend to catch these failures via `except subprocess.SubprocessError:`, you must explicitly pass `check=True` to `subprocess.run()`. Otherwise, the exception block becomes dead code and errors fail silently.

**Action:** Always use `check=True` in `subprocess.run()` when expecting to catch execution failures via try-except blocks.

**Defect Pattern ID:** PATTERN-007

**Related Entries:** []

**Axes Affected:** II (Semantic)

**Level:** L2

---
entry_id: "CRUCIBLE-$(date +%Y-%m-%d)-004"
schema_version: "2.0"
timestamp: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
title: "Axis V: Package manager determinism (pip vs uv)"
---
## $(date +%Y-%m-%d) - Axis V: Package manager determinism (pip vs uv)

**Learning:** Relying on `pip` in CI environments can lead to non-deterministic builds and temporal defects due to floating dependency resolution and slower installation times.

**Action:** Consistently replace `pip` with `uv` across all environments (including GitHub Actions workflows) to enforce strict determinism and performance, adhering to the "uv/uvx (never pip)" constraint.

**Defect Pattern ID:** PATTERN-012

**Related Entries:** []

**Axes Affected:** V (Temporal)

**Level:** L5

---

## REPO CONTEXT (Last updated: 2024-05-24)
**Project:** ghc-compiler-python | **Languages:** Python, Bash | **Build/Test:** hatchling, pytest
**Attack Surface:** CLI / Local execution
**Known Vulnerabilities:**
- Local Privilege Escalation / TOCTOU via predictable fallback temp directory.
- PATH execution hijacking via incorrect `shutil.which` priority.
**Fixed Vulnerabilities:** None yet.
**Security Dependencies:** None specific.

**Critical Learnings:**
- Removed `shutil.which` fallback in `_resolve_binary` to prevent PATH-based execution hijacking. The wrapper now strictly enforces bundled binary execution.
- Fixed a TOCTOU vulnerability in `_sterilize_environment` by explicitly verifying ownership, permissions, and ensuring the fallback `.ghc-compiler-python-home` directory is securely created (mode 0o700). Avoided Windows-specific crashes by skipping `os.getuid()` when `sys.platform == "win32"`.

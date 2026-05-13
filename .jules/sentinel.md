## REPO CONTEXT (Last updated: 2024-05-24)
**Project:** ghc-compiler-python | **Languages:** Python, Bash | **Build/Test:** hatchling, pytest
**Attack Surface:** CLI / Local execution
**Known Vulnerabilities:**
- Local Privilege Escalation / TOCTOU via predictable fallback temp directory.
- PATH execution hijacking via incorrect `shutil.which` priority.
**Fixed Vulnerabilities:** Local Privilege Escalation / TOCTOU via predictable fallback temp directory, PATH execution hijacking via incorrect shutil.which priority.
**Security Dependencies:** None specific.

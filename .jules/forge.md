## REPO CONTEXT (Last updated: 2024-05-06)
**Project:** ghc-compiler-python | **Languages:** Python, Bash | **Build/Test/Lint:** hatch, pytest
**Known Bug Patterns:** Missing trap cleanups, unhandled OS failures in wrappers, paths with spaces
**Fixed Bugs:** Wrapper crashed on read-only sys.prefix, shell script trap cleanup missing.

### Critical Learnings (YYYY-MM-DD):
- Fixed silent exception swallowing (`except OSError: pass`) in `ghc_compiler_python/wrapper.py` during path patching and recache, replacing them with proper `sys.stderr.write` logging. This enables better debugging for missing permissions or missing files.
Deleted test script files that I added during my debugging phase.

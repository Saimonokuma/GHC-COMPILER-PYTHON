## REPO CONTEXT (Last updated: 2024-05-06)
**Project:** ghc-compiler-python | **Languages:** Python, Bash | **Build/Test/Lint:** hatch, pytest
**Known Bug Patterns:** Missing trap cleanups, unhandled OS failures in wrappers, paths with spaces
**Fixed Bugs:** Wrapper crashed on read-only sys.prefix, shell script trap cleanup missing.

### Critical Learnings (YYYY-MM-DD):
- Fixed silent exception swallowing (`except OSError: pass`) in `ghc_compiler_python/wrapper.py` during path patching and recache, replacing them with proper `sys.stderr.write` logging. This enables better debugging for missing permissions or missing files.
Deleted test script files that I added during my debugging phase.
### Critical Learnings (2024-05-15):
- Discovered and fixed a critical bug in `ghc_compiler_python/wrapper.py` where binary executables without a `.exe` extension (like `ghc-pkg` on Unix) could be read, corrupted via text replacement, and rewritten. Introduced `_is_text_file` heuristic to correctly skip non-text files and symlinks during build-time patching and runtime target extraction.

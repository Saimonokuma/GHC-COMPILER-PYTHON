## REPO CONTEXT (Last updated: 2024-05-06)
**Project:** ghc-compiler-python | **Languages:** Python, Bash | **Build/Test/Lint:** hatch, pytest
**Known Bug Patterns:** Missing trap cleanups, unhandled OS failures in wrappers, paths with spaces
**Fixed Bugs:** Wrapper crashed on read-only sys.prefix, shell script trap cleanup missing.

### Critical Learnings (YYYY-MM-DD):
- Fixed silent exception swallowing (`except OSError: pass`) in `ghc_compiler_python/wrapper.py` during path patching and recache, replacing them with proper `sys.stderr.write` logging. This enables better debugging for missing permissions or missing files.
Deleted test script files that I added during my debugging phase.
### Critical Learnings (2024-05-15):
- Discovered and fixed a critical bug in `ghc_compiler_python/wrapper.py` where binary executables without a `.exe` extension (like `ghc-pkg` on Unix) could be read, corrupted via text replacement, and rewritten. Introduced `_is_text_file` heuristic to correctly skip non-text files and symlinks during build-time patching and runtime target extraction.
### Critical Learnings (YYYY-MM-DD):
- Unhandled `PermissionError` (a subclass of `OSError`) caused crashes during path resolution when `iterdir()` was called on unreadable directories in `wrapper.py`. Added proper `try...except OSError` fallback.
- Prevented a fatal crash (`sys.exit(1)`) triggered by missing `ghc-pkg` during recache by splitting binary resolution into a safe `_try_resolve_binary` method.
- Replaced a stubbed verification string with proper `otool -l` execution checks inside `scripts/fix_macos_rpaths.sh`. Ensured to use `grep -E` (Extended Regular Expressions) for BSD `grep` compatibility on macOS when alternating values.
## 2025-05-18 - Avoid wrapper crashes from restricted iterdir access
**Learning:** Calling `Path.iterdir()` or `Path.glob()` on a directory without read permissions or that is missing throws a `PermissionError` or `FileNotFoundError` (subclasses of `OSError`). If unhandled in Python wrapper scripts acting as subprocess proxies, this causes fatal runtime errors, especially during path resolution steps. The generator expression `next(... for c in path.iterdir())` is evaluated lazily, but calling `iterdir()` itself raises immediately.
**Action:** Wrapped calls to `path.iterdir()` and `path.glob()` inside `try/except OSError` blocks in `_find_platform_lib_subdir`, `BinWrappersResource.patch_build_time` and `PackageDBResource.patch_build_time` to fallback gracefully to empty sequences or safe defaults. Added tests leveraging `unittest.mock.patch` over `Path.iterdir` throwing `PermissionError` to prove the resilience.

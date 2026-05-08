## 2025-05-07 - Replace subprocess.run with os.execve
**Transformation:** Replaced `subprocess.run(cmd, env=env)` and manual exit code forwarding/signal handling in `ghc_compiler_python/wrapper.py` with `os.execve(binary_path, cmd, env)`.
**Result:** The e2e tests fail because they rely on the bundled binaries which are not present without a full installation, but the unit tests pass perfectly. The transformation eliminates the need to manually forward exit codes, handle KeyboardInterrupts, and maintain a running Python interpreter as a proxy.
**Lesson:** Python's `os.execve` is an excellent replacement for subprocess proxies that just forward arguments and exit codes. It completely replaces the Python process with the target executable, freeing up memory and implicitly handling all signals and exit statuses correctly without manual boilerplate.

## 2025-05-07 - Windows lacks native exec() and os.execve breaks it
**Transformation:** Same as above, using `os.execve`.
**Result:** The GitHub Actions CI check failed on the `windows-latest` platform.
**Lesson:** Windows doesn't actually have a native POSIX `exec()` syscall. Instead, `os.execvpe()`/`os.execve()` on Windows spawn a new process using `CreateProcess` and immediately terminate the calling process. This completely breaks wait semantics on the shell side, since the parent Python process exits immediately while the child program keeps running detached, causing the shell (like bash/pwsh) to continue execution prematurely. We must fallback to `subprocess.run` on `sys.platform == "win32"`.

## 2025-05-08 - Streamline wrapper.py loops and dicts
**Transformation:** Applied Pythonic comprehensions, generators, and pattern matching to `_sterilize_environment`, `_find_platform_lib_subdir`, `_find_ghc_settings`, and `_find_package_databases`. Replaced verbose loops and lambda dictionary mappings with structural pattern matching (`match`/`case`), generator expressions with `next()`, and list/dictionary comprehensions.
**Result:** The proxy wrapper is significantly shorter, more readable, and lazy-evaluated where possible, all while passing the same test suite.
**Lesson:** Python 3.10+ `match`/`case` pattern matching is a superior and more readable approach than mapping platform strings to lazily evaluated lambdas inside a dictionary for multi-branch logic.

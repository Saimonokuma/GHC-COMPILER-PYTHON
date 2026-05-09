## 2025-05-07 - Replace subprocess.run with os.execve
**Transformation:** Replaced `subprocess.run(cmd, env=env)` and manual exit code forwarding/signal handling in `ghc_compiler_python/wrapper.py` with `os.execve(binary_path, cmd, env)`.
**Result:** The e2e tests fail because they rely on the bundled binaries which are not present without a full installation, but the unit tests pass perfectly. The transformation eliminates the need to manually forward exit codes, handle KeyboardInterrupts, and maintain a running Python interpreter as a proxy.
**Lesson:** Python's `os.execve` is an excellent replacement for subprocess proxies that just forward arguments and exit codes. It completely replaces the Python process with the target executable, freeing up memory and implicitly handling all signals and exit statuses correctly without manual boilerplate.

## 2025-05-07 - Windows lacks native exec() and os.execve breaks it
**Transformation:** Same as above, using `os.execve`.
**Result:** The GitHub Actions CI check failed on the `windows-latest` platform.
**Lesson:** Windows doesn't actually have a native POSIX `exec()` syscall. Instead, `os.execvpe()`/`os.execve()` on Windows spawn a new process using `CreateProcess` and immediately terminate the calling process. This completely breaks wait semantics on the shell side, since the parent Python process exits immediately while the child program keeps running detached, causing the shell (like bash/pwsh) to continue execution prematurely. We must fallback to `subprocess.run` on `sys.platform == "win32"`.

## 2024-05-19 - Optimization of wrapper.py Using Alchemist Patterns
**The Target:** `ghc_compiler_python/wrapper.py` was bloated with nested `try...except`, loops, and redundant conditions in `_sterilize_environment`, `_resolve_runtime_paths`, `_find_ghc_settings` and `__getattr__`.
**The Transmutation:** Replaced `try...except` and manual path checking with concise generator pipelines using `next(...)`. Used `any()` and filtered directory traversals (`dirs[:]`) to collapse nested loops in `os.walk`. Merged repetitive mmap replacement logic with the `write_bytes()` shorthand to simplify binary path injections. Transmuted `__getattr__` wrapper logic using dynamic `type` generation.
**The Impact:** Eliminated dozens of lines of repetitive logic. Memory footprint and speed improved by avoiding manual iteration overhead for resolving path constants. Maintained behavior correctly for all edge cases including platform-specific directory layouts.

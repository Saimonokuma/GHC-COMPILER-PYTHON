## 2025-05-07 - Replace subprocess.run with os.execve
**Transformation:** Replaced `subprocess.run(cmd, env=env)` and manual exit code forwarding/signal handling in `ghc_compiler_python/wrapper.py` with `os.execve(binary_path, cmd, env)`.
**Result:** The e2e tests fail because they rely on the bundled binaries which are not present without a full installation, but the unit tests pass perfectly. The transformation eliminates the need to manually forward exit codes, handle KeyboardInterrupts, and maintain a running Python interpreter as a proxy.
**Lesson:** Python's `os.execve` is an excellent replacement for subprocess proxies that just forward arguments and exit codes. It completely replaces the Python process with the target executable, freeing up memory and implicitly handling all signals and exit statuses correctly without manual boilerplate.

## 2025-05-07 - Windows lacks native exec() and os.execve breaks it
**Transformation:** Same as above, using `os.execve`.
**Result:** The GitHub Actions CI check failed on the `windows-latest` platform.
**Lesson:** Windows doesn't actually have a native POSIX `exec()` syscall. Instead, `os.execvpe()`/`os.execve()` on Windows spawn a new process using `CreateProcess` and immediately terminate the calling process. This completely breaks wait semantics on the shell side, since the parent Python process exits immediately while the child program keeps running detached, causing the shell (like bash/pwsh) to continue execution prematurely. We must fallback to `subprocess.run` on `sys.platform == "win32"`.
## 2025-05-07 - Refactoring Resource Registration and re.sub Consolidation
**Transformation:**
- Replaced verbose `ResourceMeta` metaclass with `__init_subclass__` on `BaseResource` for dynamic resource registration.
- Consolidated redundant `re.sub` logic in `PackageDBResource.patch_build_time` using regex grouping (`rf"\g<1>..."`).
- Chain `sys.exit` directly onto `subprocess.run(...).returncode` to remove intermediate assignments.
**Result:** Code is shorter, more idiomatic, and conceptually simpler without breaking correctness. Tests pass.
**Lesson:** `__init_subclass__` is almost always a cleaner and more native-feeling alternative to metaclasses when the only goal is registering subclasses.

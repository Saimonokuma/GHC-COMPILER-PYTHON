# ghc_compiler_python/wrapper.py
"""
Subprocess proxy wrappers for GHC and Cabal binaries.

Provides hermetic execution isolation, environment sterilization,
pre-flight C-linker validation, runtime path resolution, and process proxying.

FIX v5: Fixed LD_LIBRARY_PATH propagation to ghc-pkg recache.
       Added platform-specific lib subdir to LD_LIBRARY_PATH on Linux.
       Thread sterilized environment through _resolve_runtime_paths → _rebuild_package_cache → _ghc_pkg_recache.
FIX v4: Added ghc-pkg recache after @GHC_PREFIX@ replacement to regenerate package.cache.
FIX v3: Fixed platform-specific path detection for settings and package.conf.d.
FIX v2: Added DYLD_LIBRARY_PATH for macOS runtime library resolution.
"""

import os
import sys
import shutil
import subprocess
import tempfile
import functools
import mmap
from pathlib import Path
from typing import Any, List, NoReturn, Optional


GHC_VERSION = "9.4.8"
CABAL_VERSION = "3.10.3.0"

HASKELL_POLLUTION_VARS = frozenset(
    {
        "GHC_PACKAGE_PATH",
        "GHC_ENVIRONMENT",
        "CABAL_DIR",
        "CABAL_CONFIG",
        "HASKELL_DIST_DIR",
        "HASKELL_PACKAGE_SANDBOX",
        "HASKELL_PACKAGE_SANDBOXES",
        "STACK_ROOT",
        "STACK_YAML",
        "GHCRTS",
        "GHCRTS_OPTS",
        "HEAPSIZE",
        "HOME",
    }
)

_HOME_ORIGINAL: Optional[str] = None


def _resolve_binary(name: str) -> str:
    """Resolve the absolute path to a bundled native binary."""
    binary_name = f"{name}.exe" if sys.platform == "win32" else name

    # 🧪 Alchemist: Find the first matching binary concisely with `next()`
    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    if resolved := next((p for p in (
        shutil.which(binary_name),
        str(Path(sys.prefix) / bin_dir / binary_name),
        str(Path(__file__).resolve().parent.parent / bin_dir / binary_name)
    ) if p and (p == shutil.which(binary_name) or Path(p).exists())), None):
        return resolved

    sys.stderr.write(
        f"FATAL ERROR: Bundled compiler binary '{binary_name}' could not be located.\n"
    )
    sys.exit(1)


def _validate_c_linker() -> None:
    """Pre-flight validation: assert the existence of a host C-linker."""
    if not shutil.which("gcc") and not shutil.which("clang"):
        sys.stderr.write(
            "FATAL ERROR: The GHC compiler requires a host C-linker (gcc or clang).\n"
        )
        sys.exit(1)


def _find_platform_lib_subdir() -> str:
    """Find the platform-specific library subdirectory inside the GHC lib directory.

    On Linux:   lib/ghc-9.4.8/lib/x86_64-linux-ghc-9.4.8/
    On macOS:   lib/ghc-9.4.8/lib/aarch64-osx-ghc-9.4.8/ (or similar)
    On Windows: Does not exist (DLLs are in mingw/bin/)
    """
    ghc_lib_dir = Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib"
    if not ghc_lib_dir.is_dir():
        return ""

    # Look for the platform-specific subdirectory (e.g., x86_64-linux-ghc-9.4.8)
    for candidate in ghc_lib_dir.iterdir():
        if candidate.is_dir() and candidate.name.endswith(f"-ghc-{GHC_VERSION}"):
            return str(candidate)

    return ""


def _sterilize_environment() -> dict:
    """Create a sterilized subprocess environment with proper library paths."""
    global _HOME_ORIGINAL
    env = {k: v for k, v in os.environ.items() if k not in HASKELL_POLLUTION_VARS}

    _HOME_ORIGINAL = env.get("HOME", env.get("USERPROFILE", ""))

    # 🧪 Alchemist: Streamlined fallback resolution using sequential attempts
    safe_home = next((
        p for path in (
            Path(sys.prefix) / ".ghc-compiler-python-home",
            Path(tempfile.gettempdir()) / ".ghc-compiler-python-home"
        ) if (p := path) and (not p.exists() and not p.mkdir(parents=True, exist_ok=True) or p.exists())
    ), Path(_HOME_ORIGINAL or tempfile.gettempdir()))

    env["HOME"] = str(safe_home)

    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    env_bin = Path(sys.prefix) / bin_dir
    current_path = env.get("PATH", "")
    env["PATH"] = f"{env_bin}{os.pathsep}{current_path}"

    # 🧪 Alchemist: Dictionary mapping with lambdas and generators replace verbose if-chains and manual append loops
    # Lambdas are used for lazy evaluation so that platform-specific code doesn't evaluate eagerly.
    platform_config = {
        "darwin": lambda: (
            [
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib",
                Path(sys.prefix) / "lib",
            ],
            ["DYLD_LIBRARY_PATH", "LD_LIBRARY_PATH"],
        ),
        "linux": lambda: (
            [
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}",
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib",
                Path(_find_platform_lib_subdir() or "."),
                Path(__file__).resolve().parent.parent / "ghc_compiler_python.libs",
            ],
            ["LD_LIBRARY_PATH"],
        ),
    }
    candidates, vars_to_update = platform_config.get(sys.platform, lambda: ([], []))()

    if lib_dirs_str := os.pathsep.join(
        str(p) for p in candidates if p.is_dir() and str(p) != "."
    ):
        for var in vars_to_update:
            env[var] = (
                f"{lib_dirs_str}{os.pathsep}{env[var]}"
                if env.get(var)
                else lib_dirs_str
            )

    return env


@functools.lru_cache(maxsize=None)
def _find_ghc_settings() -> Optional[str]:
    """Find the GHC settings file in platform-specific locations."""
    if candidate := next(
        (str(p) for p in (
            Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib" / "settings",
            Path(sys.prefix) / "lib" / "settings",
            Path(sys.prefix) / "settings"
        ) if p.exists()),
        None
    ):
        return candidate

    # Dynamic fallback: search recursively
    if (lib_dir := Path(sys.prefix) / "lib").exists():
        for root, dirs, files in os.walk(lib_dir):
            dirs[:] = [d for d in dirs if d not in ("site-packages", "dist-packages")]
            if "settings" in files:
                candidate = Path(root) / "settings"
                try:
                    content = candidate.read_text(encoding="utf-8", errors="replace")
                    if '"C compiler command"' in content or '"C preprocessor command"' in content:
                        return str(candidate)
                except OSError:
                    continue
    return None


@functools.lru_cache(maxsize=None)
def _find_package_databases() -> List[str]:
    """Find all GHC package database directories in platform-specific locations."""
    found = [str(p) for p in (
        Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib" / "package.conf.d",
        Path(sys.prefix) / "lib" / "package.conf.d",
        Path(sys.prefix) / "package.conf.d"
    ) if p.is_dir()]

    # Dynamic fallback: search recursively
    if not found and (lib_dir := Path(sys.prefix) / "lib").exists():
        for root, dirs, files in os.walk(lib_dir):
            dirs[:] = [d for d in dirs if d not in ("site-packages", "dist-packages")]
            if "package.conf.d" in dirs:
                candidate = Path(root) / "package.conf.d"
                if any(f.name.endswith(".conf") for f in candidate.iterdir()):
                    found.append(str(candidate))

    return found


def _resolve_runtime_paths(env: dict) -> None:
    """Dynamically replace @GHC_PREFIX@ with the active sys.prefix at runtime,
    then regenerate package.cache.

    Args:
            env: The sterilized environment dict with proper LD_LIBRARY_PATH set.
    """
    prefix_clean = sys.prefix.replace("\\", "/")

    # 🧪 Alchemist: Build targets array efficiently using generator expression and sum to flatten
    targets = [s for s in [_find_ghc_settings()] if s] + [
        str(f)
        for pkg_db in _find_package_databases()
        for f in Path(pkg_db).iterdir() if f.name.endswith(".conf")
    ] + [
        str(f)
        for bin_dir_path in (
            Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin"),
            Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "bin",
            Path(sys.prefix) / "bin",
            Path(sys.prefix) / "lib" / "bin",
        )
        if bin_dir_path.exists()
        for f in bin_dir_path.iterdir()
        if f.is_file() and not f.name.endswith(".exe")
    ]

    # Replace @GHC_PREFIX@ in all target files
    prefix_clean_bytes = prefix_clean.encode("utf-8")
    patched_any_conf = False
    for target in set(targets):  # 🧪 Alchemist: Deduplicate targets in a single pass
        target_path = Path(target)
        try:
            # ⚡ Bolt: Use mmap to efficiently search for @GHC_PREFIX@ without loading
            # the entire binary into memory. Drastically reduces I/O latency for large binaries.
            content_to_write = None
            with target_path.open("rb") as f:
                try:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
                        if m.find(b"@GHC_PREFIX@") != -1:
                            f.seek(0)
                            content_to_write = f.read()
                except ValueError:
                    # mmap throws ValueError for empty files
                    pass

            if content_to_write is not None:
                target_path.write_bytes(content_to_write.replace(b"@GHC_PREFIX@", prefix_clean_bytes))
                if target.endswith(".conf"):
                    patched_any_conf = True
        except OSError:
            pass  # Ignore read-only files if already patched

    # 🧪 Alchemist: any() replaces manual flag variables and loops for succinct boolean reduction
    if patched_any_conf or any(
        not (Path(pkg_db) / "package.cache").exists()
        for pkg_db in _find_package_databases()
    ):
        _rebuild_package_cache(env)


def _rebuild_package_cache(env: dict) -> None:
    """Run ghc-pkg recache to regenerate package.cache.

    GHC requires package.cache to function properly. The build process
    deletes it after patching .conf files, so we must regenerate it
    at runtime after @GHC_PREFIX@ replacement.

    Args:
            env: The sterilized environment dict with proper LD_LIBRARY_PATH set.
    """
    for pkg_db in _find_package_databases():
        _ghc_pkg_recache(pkg_db, env)


def _ghc_pkg_recache(pkg_db_dir: str, env: dict) -> None:
    """Run ghc-pkg recache for the given package database directory.

    Args:
            pkg_db_dir: Path to the package.conf.d directory.
            env: The sterilized environment dict with proper LD_LIBRARY_PATH set.
    """
    ghc_pkg = _resolve_binary("ghc-pkg")
    if not ghc_pkg:
        return  # Can't recache without ghc-pkg

    try:
        # Use the sterilized environment which has LD_LIBRARY_PATH properly set
        recache_env = env.copy()
        recache_env["GHC_PACKAGE_PATH"] = pkg_db_dir

        subprocess.run(
            [ghc_pkg, "recache", "--package-db", pkg_db_dir],
            env=recache_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        # Silently ignore errors - GHC will fall back to reading .conf files directly
    except (subprocess.SubprocessError, OSError):
        pass  # Non-fatal: if recache fails, GHC can still work without cache


def _execute_tool(tool_name: str, extra_args: Optional[List[str]] = None) -> NoReturn:
    """Generic subprocess proxy for bundled Haskell tooling."""
    _validate_c_linker()
    env = _sterilize_environment()
    _resolve_runtime_paths(env)
    binary_path = _resolve_binary(tool_name)

    cmd = [binary_path]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(sys.argv[1:])

    try:
        # 🧪 Alchemist: On POSIX systems, os.execve replaces the Python interpreter entirely.
        # This eliminates the need for subprocess.run(), manual exit code forwarding,
        # and signal handlers, freeing the memory of the wrapper script completely.
        # However, Windows lacks native exec() and implements it by creating a new process
        # and terminating the current one, which breaks shell wait() expectations.
        if sys.platform != "win32":
            os.execve(binary_path, cmd, env)
        else:
            result = subprocess.run(cmd, env=env)
            sys.exit(result.returncode)
    except FileNotFoundError:
        sys.stderr.write(f"FATAL ERROR: Binary not found at '{binary_path}'.\n")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
    except (subprocess.SubprocessError, OSError) as e:
        sys.stderr.write(f"FATAL ERROR: Execution failed: {e}\n")
        sys.exit(1)


def __getattr__(name: str) -> Any:
    """Dynamic console script entry point generator.

    Generates execution closures dynamically for any binary requested via entry points
    (e.g., execute_ghc, execute_cabal, execute_haddock).
    """
    if name.startswith("execute_"):
        # 🧪 Alchemist: Type instantiation dynamically creates callable classes compactly
        return type('',(),{
            '__name__': name,
            '__call__': lambda self: _execute_tool(name[8:].replace("_", "-"), extra_args=["-v0"] if name == "execute_ghc" else None)
        })()

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> List[str]:
    """Provide explicit autocompletion for common dynamically generated entry points."""
    base_dir = list(globals().keys())
    dynamic_tools = ["execute_ghc", "execute_ghci", "execute_cabal"]
    return base_dir + dynamic_tools

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
import re
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

    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    fallback_path = Path(sys.prefix) / bin_dir / binary_name

    if fallback_path.exists():
        return str(fallback_path)

    package_dir = Path(__file__).resolve().parent
    env_bin = package_dir.parent / bin_dir / binary_name
    if env_bin.exists():
        return str(env_bin)

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
    env = os.environ.copy()

    _HOME_ORIGINAL = env.get("HOME", env.get("USERPROFILE", ""))

    for var in HASKELL_POLLUTION_VARS:
        env.pop(var, None)

    # Securely create or reuse a temporary home directory
    candidates = [Path(sys.prefix) / ".ghc-compiler-python-home"]
    try:
        candidates.append(Path.home() / ".ghc-compiler-python-home")
    except RuntimeError:
        pass

    safe_home_path = None
    for candidate in candidates:
        try:
            candidate.mkdir(mode=0o700, parents=True, exist_ok=False)
            safe_home_path = candidate
            break
        except FileExistsError:
            if candidate.is_dir() and not candidate.is_symlink():
                if sys.platform == "win32":
                    safe_home_path = candidate
                    break
                try:
                    if candidate.stat().st_uid == os.getuid():
                        candidate.chmod(0o700)
                        safe_home_path = candidate
                        break
                except OSError:
                    pass
        except OSError:
            pass

    if safe_home_path is None:
        safe_home_path = Path(tempfile.mkdtemp(prefix="ghc-compiler-python-home-"))

    env["HOME"] = str(safe_home_path)

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
    candidates = [
        # Linux/macOS: settings lives inside the nested lib dir
        Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib" / "settings",
        # Windows: settings lives directly in lib/
        Path(sys.prefix) / "lib" / "settings",
        # In hatch shared-data it could be directly in sys.prefix
        Path(sys.prefix) / "settings",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # Dynamic fallback: search recursively
    lib_dir = Path(sys.prefix) / "lib"
    if lib_dir.exists():
        for root, dirs, files in os.walk(lib_dir):
            dirs[:] = [d for d in dirs if d not in {"site-packages", "dist-packages"} and not d.startswith(("python", "pypy"))]
            if "settings" in files:
                candidate = Path(root) / "settings"
                try:
                    content = candidate.read_text(encoding="utf-8", errors="replace")
                    if (
                        '"C compiler command"' in content
                        or '"C preprocessor command"' in content
                    ):
                        return str(candidate)
                except OSError:
                    continue
    return None


@functools.lru_cache(maxsize=None)
def _find_package_databases() -> List[str]:
    """Find all GHC package database directories in platform-specific locations."""
    candidates = [
        # Linux/macOS: package.conf.d lives inside the nested lib dir
        Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib" / "package.conf.d",
        # Windows: package.conf.d lives directly in lib/
        Path(sys.prefix) / "lib" / "package.conf.d",
        # In hatch shared-data it could be directly in sys.prefix
        Path(sys.prefix) / "package.conf.d",
    ]
    found = []
    for candidate in candidates:
        if candidate.is_dir():
            found.append(str(candidate))

    # Dynamic fallback: search recursively
    if not found:
        lib_dir = Path(sys.prefix) / "lib"
        if lib_dir.exists():
            for root, dirs, files in os.walk(lib_dir):
                dirs[:] = [d for d in dirs if d not in {"site-packages", "dist-packages"} and not d.startswith(("python", "pypy"))]
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

    targets = []

    # 🧪 Alchemist: Walrus operator replaces verbose assignments
    if settings_file := _find_ghc_settings():
        targets.append(settings_file)

    for pkg_db in _find_package_databases():
        db_path = Path(pkg_db)
        targets.extend(
            str(f) for f in db_path.iterdir() if f.name.endswith(".conf") and not f.is_symlink()
        )

    # 🧪 Alchemist: Consolidate repetitive directory scanning into a compact tuple traversal
    for bin_dir_path in (
        Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin"),
        Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "bin",
        Path(sys.prefix) / "bin",
        Path(sys.prefix) / "lib" / "bin",
    ):
        if bin_dir_path.exists():
            targets.extend(
                str(f)
                for f in bin_dir_path.iterdir()
                if f.is_file() and not f.name.endswith(".exe") and not f.is_symlink()
            )

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
                if target.endswith(".conf") and b" " in prefix_clean_bytes:
                    s = content_to_write.decode("utf-8", errors="replace")
                    s = re.sub(r'(?<!")(@GHC_PREFIX@[^\s"]+)', r'"\1"', s)
                    content_to_write = s.encode("utf-8", errors="replace")
                with target_path.open("wb") as out:
                    out.write(content_to_write.replace(b"@GHC_PREFIX@", prefix_clean_bytes))
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
        tool_name = name[8:].replace("_", "-")
        extra_args = ["-v0"] if tool_name == "ghc" else None

        def executor() -> NoReturn:
            _execute_tool(tool_name, extra_args=extra_args)

        executor.__name__ = name
        return executor

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> List[str]:
    """Provide explicit autocompletion for common dynamically generated entry points."""
    base_dir = list(globals().keys())
    dynamic_tools = ["execute_ghc", "execute_ghci", "execute_cabal"]
    return base_dir + dynamic_tools

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
import signal
from typing import List, NoReturn, Optional


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

    resolved = shutil.which(binary_name)
    if resolved:
        return resolved

    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    fallback_path = os.path.join(sys.prefix, bin_dir, binary_name)

    if os.path.exists(fallback_path):
        return fallback_path

    package_dir = os.path.dirname(os.path.abspath(__file__))
    env_bin = os.path.join(os.path.dirname(package_dir), bin_dir, binary_name)
    if os.path.exists(env_bin):
        return env_bin

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
    ghc_lib_dir = os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}", "lib")
    if not os.path.isdir(ghc_lib_dir):
        return ""

    # Look for the platform-specific subdirectory (e.g., x86_64-linux-ghc-9.4.8)
    for entry in os.listdir(ghc_lib_dir):
        candidate = os.path.join(ghc_lib_dir, entry)
        if os.path.isdir(candidate) and entry.endswith(f"-ghc-{GHC_VERSION}"):
            return candidate

    return ""


def _sterilize_environment() -> dict:
    """Create a sterilized subprocess environment with proper library paths."""
    global _HOME_ORIGINAL
    env = os.environ.copy()

    for var in HASKELL_POLLUTION_VARS:
        env.pop(var, None)

    _HOME_ORIGINAL = env.get("HOME", env.get("USERPROFILE", ""))
    safe_home = os.path.join(sys.prefix, ".ghc-compiler-python-home")
    os.makedirs(safe_home, exist_ok=True)
    env["HOME"] = safe_home

    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    env_bin = os.path.join(sys.prefix, bin_dir)
    current_path = env.get("PATH", "")
    env["PATH"] = f"{env_bin}{os.pathsep}{current_path}"

    # Collect all library directories for LD_LIBRARY_PATH / DYLD_LIBRARY_PATH
    lib_dirs = []

    if sys.platform == "darwin":
        # macOS: GHC libraries are in lib/ghc-9.4.8/lib/
        ghc_lib_dir = os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}", "lib")
        if os.path.isdir(ghc_lib_dir):
            lib_dirs.append(ghc_lib_dir)
        # Also add the top-level lib dir for delocate-processed dylibs
        top_lib_dir = os.path.join(sys.prefix, "lib")
        if os.path.isdir(top_lib_dir):
            lib_dirs.append(top_lib_dir)

    elif sys.platform == "linux":
        # Linux: Multiple library locations needed
        # 1. Top-level GHC lib dir (contains settings, package.conf.d)
        ghc_lib_dir = os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}")
        if os.path.isdir(ghc_lib_dir):
            lib_dirs.append(ghc_lib_dir)

        # 2. Nested lib dir (contains settings, package.conf.d on Linux/macOS)
        nested_lib_dir = os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}", "lib")
        if os.path.isdir(nested_lib_dir):
            lib_dirs.append(nested_lib_dir)

        # 3. Platform-specific subdir (contains .so files like libffi.so, libHS*.so)
        platform_subdir = _find_platform_lib_subdir()
        if platform_subdir and os.path.isdir(platform_subdir):
            lib_dirs.append(platform_subdir)

        # 4. Auditwheel dependencies (.libs directory)
        package_dir = os.path.dirname(os.path.abspath(__file__))
        auditwheel_libs = os.path.join(
            os.path.dirname(package_dir), "ghc_compiler_python.libs"
        )
        if os.path.isdir(auditwheel_libs):
            lib_dirs.append(auditwheel_libs)

    # Set library path environment variables
    if lib_dirs:
        lib_dirs_str = os.pathsep.join(lib_dirs)

        if sys.platform == "darwin":
            existing = env.get("DYLD_LIBRARY_PATH", "")
            env["DYLD_LIBRARY_PATH"] = (
                f"{lib_dirs_str}{os.pathsep}{existing}" if existing else lib_dirs_str
            )
            # Also set LD_LIBRARY_PATH for consistency
            existing_ld = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = (
                f"{lib_dirs_str}{os.pathsep}{existing_ld}"
                if existing_ld
                else lib_dirs_str
            )

        elif sys.platform == "linux":
            existing = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = (
                f"{lib_dirs_str}{os.pathsep}{existing}" if existing else lib_dirs_str
            )

    return env


def _find_ghc_settings() -> Optional[str]:
    """Find the GHC settings file in platform-specific locations."""
    candidates = [
        # Linux/macOS: settings lives inside the nested lib dir
        os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}", "lib", "settings"),
        # Windows: settings lives directly in lib/
        os.path.join(sys.prefix, "lib", "settings"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    # Dynamic fallback: search recursively
    for root, dirs, files in os.walk(os.path.join(sys.prefix, "lib")):
        if "settings" in files:
            full_path = os.path.join(root, "settings")
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                if (
                    '"C compiler command"' in content
                    or '"C preprocessor command"' in content
                ):
                    return full_path
            except Exception:
                continue
    return None


def _find_package_databases() -> List[str]:
    """Find all GHC package database directories in platform-specific locations."""
    candidates = [
        # Linux/macOS: package.conf.d lives inside the nested lib dir
        os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}", "lib", "package.conf.d"),
        # Windows: package.conf.d lives directly in lib/
        os.path.join(sys.prefix, "lib", "package.conf.d"),
    ]
    found = []
    for candidate in candidates:
        if os.path.exists(candidate) and os.path.isdir(candidate):
            found.append(candidate)

    # Dynamic fallback: search recursively
    if not found:
        for root, dirs, files in os.walk(os.path.join(sys.prefix, "lib")):
            if "package.conf.d" in dirs:
                full_path = os.path.join(root, "package.conf.d")
                if any(f.endswith(".conf") for f in os.listdir(full_path)):
                    found.append(full_path)

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
        targets.extend(
            os.path.join(pkg_db, f) for f in os.listdir(pkg_db) if f.endswith(".conf")
        )

    # 🧪 Alchemist: Consolidate repetitive directory scanning into a compact tuple traversal
    for bin_dir in (
        os.path.join(sys.prefix, "Scripts" if sys.platform == "win32" else "bin"),
        os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}", "bin"),
        os.path.join(sys.prefix, "bin"),
        os.path.join(sys.prefix, "lib", "bin"),
    ):
        if os.path.exists(bin_dir):
            targets.extend(
                os.path.join(bin_dir, f)
                for f in os.listdir(bin_dir)
                if os.path.isfile(os.path.join(bin_dir, f)) and not f.endswith(".exe")
            )

    # Replace @GHC_PREFIX@ in all target files
    for target in set(targets):  # 🧪 Alchemist: Deduplicate targets in a single pass
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                # 🧪 Alchemist: Walrus operator removes redundant content assignment
                if "@GHC_PREFIX@" in (content := f.read()):
                    with open(target, "w", encoding="utf-8") as out:
                        out.write(content.replace("@GHC_PREFIX@", prefix_clean))
        except Exception:
            pass  # Ignore read-only files if already patched

    # Regenerate package.cache after patching .conf files
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
    except Exception:
        pass  # Non-fatal: if recache fails, GHC can still work without cache


def _handle_sigterm(signum: int, frame) -> None:
    sys.exit(128 + signum)


def _handle_sigint(signum: int, frame) -> None:
    sys.exit(130)


def _execute_tool(tool_name: str, extra_args: Optional[List[str]] = None) -> NoReturn:
    """Generic subprocess proxy for bundled Haskell tooling."""
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigint)

    _validate_c_linker()
    env = _sterilize_environment()
    _resolve_runtime_paths(env)
    binary_path = _resolve_binary(tool_name)

    cmd = [binary_path]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(sys.argv[1:])

    try:
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
    except FileNotFoundError:
        sys.stderr.write(f"FATAL ERROR: Binary not found at '{binary_path}'.\n")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        sys.stderr.write(f"FATAL ERROR: Subprocess proxy exception: {e}\n")
        sys.exit(1)


def execute_ghc() -> NoReturn:
    _execute_tool("ghc", extra_args=["-v0"])


def execute_ghci() -> NoReturn:
    _execute_tool("ghci")


def execute_cabal() -> NoReturn:
    _execute_tool("cabal")

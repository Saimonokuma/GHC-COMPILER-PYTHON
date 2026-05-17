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
from typing import Any, List, NoReturn, Optional, Type


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


def _die(msg: str) -> NoReturn:
    sys.stderr.write(f"{msg}\n")
    sys.exit(1)


def _is_text_file(filepath: Path) -> bool:
    """Check if a file is a text file by looking for null bytes in the first 1024 bytes."""
    try:
        with filepath.open("rb") as f:
            chunk = f.read(1024)
            return b"\0" not in chunk
    except OSError:
        return False


def _resolve_binary(name: str) -> str:
    """Resolve the absolute path to a bundled native binary."""
    binary_name = f"{name}.exe" if sys.platform == "win32" else name
    bin_dir = "Scripts" if sys.platform == "win32" else "bin"

    candidates = [
        Path(sys.prefix) / bin_dir / binary_name,
        Path(__file__).resolve().parent.parent / bin_dir / binary_name
    ]

    return next(
        (str(p) for p in candidates if p.exists()),
        shutil.which(binary_name)
    ) or _die(f"FATAL ERROR: Bundled compiler binary '{binary_name}' could not be located.")


def _validate_c_linker() -> None:
    """Pre-flight validation: assert the existence of a host C-linker."""
    if not shutil.which("gcc") and not shutil.which("clang"):
        _die("FATAL ERROR: The GHC compiler requires a host C-linker (gcc or clang).")


def _find_platform_lib_subdir() -> str:
    """Find the platform-specific library subdirectory inside the GHC lib directory.

    On Linux:   lib/ghc-9.4.8/lib/x86_64-linux-ghc-9.4.8/
    On macOS:   lib/ghc-9.4.8/lib/aarch64-osx-ghc-9.4.8/ (or similar)
    On Windows: Does not exist (DLLs are in mingw/bin/)
    """
    ghc_lib_dir = Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib"
    if not ghc_lib_dir.is_dir():
        return ""

    # 🧪 Alchemist: Generator expression with next() replaces manual iteration loop
    return next((str(c) for c in ghc_lib_dir.iterdir() if c.is_dir() and c.name.endswith(f"-ghc-{GHC_VERSION}")), "")


def _sterilize_environment() -> dict:
    """Create a sterilized subprocess environment with proper library paths."""
    global _HOME_ORIGINAL
    env = {k: v for k, v in os.environ.items() if k not in HASKELL_POLLUTION_VARS}

    _HOME_ORIGINAL = os.environ.get("HOME", os.environ.get("USERPROFILE", ""))

    def _get_home_path() -> Path:
        try:
            return Path.home() / ".ghc-compiler-python-home"
        except RuntimeError:
            return Path()

    def _try_mkdir(path: Path) -> Optional[Path]:
        try:
            if str(path) != ".":
                path.mkdir(parents=True, exist_ok=True)
                return path
        except (OSError, RuntimeError):
            pass
        return None

    # 🧪 Alchemist: Declarative fallback chain replaces nested try-except blocks.
    # Lazily evaluate Path.home() to prevent premature RuntimeError.
    safe_home = (
        _try_mkdir(Path(sys.prefix) / ".ghc-compiler-python-home") or
        _try_mkdir(_get_home_path()) or
        Path(tempfile.mkdtemp(prefix="ghc-compiler-python-home-"))
    )

    env["HOME"] = str(safe_home)

    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    env_bin = Path(sys.prefix) / bin_dir
    current_path = env.get("PATH", "")
    env["PATH"] = f"{env_bin}{os.pathsep}{current_path}"

    # 🧪 Alchemist: Structural pattern matching replaces lambda-based dictionary lookup
    match sys.platform:
        case "darwin":
            candidates = [
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib",
                Path(sys.prefix) / "lib",
            ]
            vars_to_update = ["DYLD_LIBRARY_PATH", "LD_LIBRARY_PATH"]
        case "linux":
            candidates = [
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}",
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib",
                Path(_find_platform_lib_subdir() or "."),
                Path(__file__).resolve().parent.parent / "ghc_compiler_python.libs",
            ]
            vars_to_update = ["LD_LIBRARY_PATH"]
        case _:
            candidates, vars_to_update = [], []

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



class BaseResource:
    """Base class for all GHC resource locators and patchers."""
    name: str = ""
    is_dir: bool = False
    registry = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.registry.append(cls)

    @classmethod
    @functools.lru_cache(maxsize=None)
    def locate(cls, base: str = sys.prefix, version: str = GHC_VERSION) -> List[Path]:
        """Locate all instances of this resource relative to a base directory."""
        base_path = Path(base)
        candidates = cls.get_candidates(base_path, version)

        # Check explicit candidates first
        for c in candidates:
            # 🧪 Alchemist: Ternary conditional combines file and directory checks
            if (c.is_dir() if cls.is_dir else c.is_file()) and cls.validate(c):
                return [c]

        # Dynamic fallback
        found = []
        if base_path.exists():
            lib_dir = base_path / "lib"
            search_dir = lib_dir if lib_dir.exists() else base_path

            for root, dirs, files in os.walk(search_dir):
                # ⚡ Bolt: Prune os.walk to prevent recursion into massive Python directories.
                # Modifying `dirs` in place avoids walking into these branches entirely.
                dirs[:] = [
                    d for d in dirs
                    if d not in {"site-packages", "dist-packages"}
                    and not d.startswith(("python", "pypy"))
                ]

                if cls.is_dir:
                    if cls.name in dirs:
                        p = Path(root) / cls.name
                        if cls.validate(p):
                            found.append(p)
                else:
                    if cls.name in files:
                        p = Path(root) / cls.name
                        if cls.validate(p):
                            found.append(p)
        return found

    @classmethod
    def get_candidates(cls, base: Path, version: str) -> List[Path]:
        return []

    @classmethod
    def validate(cls, path: Path) -> bool:
        return True

    @classmethod
    def extract_targets(cls, path: Path) -> List[str]:
        """Extract actual file targets to be patched at runtime from the located resource."""
        if not cls.is_dir:
            return [str(path)]
        return []

    @classmethod
    def patch_build_time(cls, path: Path, version: str, placeholder: str) -> int:
        """Patch the resource for relocatability during build."""
        return 0


class SettingsResource(BaseResource):
    name = "settings"

    @classmethod
    def get_candidates(cls, base: Path, version: str) -> List[Path]:
        return [
            base / "lib" / f"ghc-{version}" / "lib" / "settings",
            base / "lib" / "settings",
            base / "settings"
        ]

    @classmethod
    def validate(cls, path: Path) -> bool:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return '"C compiler command"' in content or '"C preprocessor command"' in content
        except OSError:
            return False

    @classmethod
    def patch_build_time(cls, path: Path, version: str, placeholder: str) -> int:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            # 🧪 Alchemist: Combine regex patterns into a single pass using alternation
            pattern = re.compile(
                r"/(?:usr/local/lib|usr/lib|opt|ghc-prefix)/ghc(?:-|/)" + re.escape(version) + r"|/ghc-prefix"
            )

            def repl(m: re.Match) -> str:
                match = m.group(0)
                if match == "/ghc-prefix":
                    return placeholder
                return f"{placeholder}/lib/ghc-{version}"

            new_content = pattern.sub(repl, content)
            if new_content != content:
                path.write_text(new_content, encoding="utf-8")
                return 1
        except OSError as e:
            sys.stderr.write(f"WARNING: Failed to patch {path}: {e}\n")
        return 0


class PackageDBResource(BaseResource):
    name = "package.conf.d"
    is_dir = True

    @classmethod
    def get_candidates(cls, base: Path, version: str) -> List[Path]:
        return [
            base / "lib" / f"ghc-{version}" / "lib" / "package.conf.d",
            base / "lib" / "package.conf.d",
            base / "package.conf.d"
        ]

    @classmethod
    def validate(cls, path: Path) -> bool:
        return any(f.name.endswith(".conf") for f in path.iterdir())

    @classmethod
    def extract_targets(cls, path: Path) -> List[str]:
        return [str(f) for f in path.iterdir() if f.name.endswith(".conf") and not f.is_symlink()]

    @classmethod
    def patch_build_time(cls, path: Path, version: str, placeholder: str) -> int:
        patched_count = 0
        for conf_file in path.glob("*.conf"):
            try:
                original = conf_file.read_text(encoding="utf-8", errors="replace")
                # 🧪 Alchemist: Consolidate redundant re.sub logic using groupings
                content = re.sub(r"(dynamic-library-dirs:\s*|library-dirs:\s*)/[^\s]+", rf"\g<1>{placeholder}/lib/ghc-{version}", original)
                content = re.sub(r"(include-dirs:\s*)/[^\s]+", rf"\g<1>{placeholder}/lib/ghc-{version}/include", content)
                content = re.sub(r"/ghc-prefix/lib/ghc-" + re.escape(version), f"{placeholder}/lib/ghc-{version}", content)
                content = re.sub(r"/ghc-prefix", placeholder, content)

                if content != original:
                    conf_file.write_text(content, encoding="utf-8")
                    patched_count += 1
            except OSError as e:
                sys.stderr.write(f"WARNING: Failed to patch {conf_file}: {e}\n")

        # 🧪 Alchemist: Walrus operator (:=) consolidates variable assignment and existence check
        try:
            (path / "package.cache").unlink(missing_ok=True)
        except OSError as e:
            sys.stderr.write(f"WARNING: Failed to unlink {path / 'package.cache'}: {e}\n")
        return patched_count


class BinWrappersResource(BaseResource):
    name = "bin"
    is_dir = True

    @classmethod
    def get_candidates(cls, base: Path, version: str) -> List[Path]:
        return [
            base / ("Scripts" if sys.platform == "win32" else "bin"),
            base / "lib" / f"ghc-{version}" / "bin",
            base / "bin",
            base / "lib" / "bin"
        ]

    @classmethod
    def validate(cls, path: Path) -> bool:
        return True

    @classmethod
    def extract_targets(cls, path: Path) -> List[str]:
        return [
            str(f) for f in path.iterdir()
            if f.is_file() and not f.is_symlink() and not f.name.endswith(".exe") and _is_text_file(f)
        ]

    @classmethod
    def patch_build_time(cls, path: Path, version: str, placeholder: str) -> int:
        patched = 0
        for script in path.iterdir():
            if not script.is_file() or script.is_symlink() or script.name.endswith(".exe") or not _is_text_file(script):
                continue
            try:
                content = script.read_text(encoding="utf-8", errors="replace")
                original = content

                content = re.sub(r"/usr/local/lib/ghc-" + re.escape(version), f"{placeholder}/lib/ghc-{version}", content)
                content = re.sub(r"/ghc-prefix", placeholder, content)

                # Replace absolute staging paths
                staging_dir = path.parent.parent if path.parent.name == f"ghc-{version}" else path.parent
                abs_staging = staging_dir.absolute().as_posix()
                if abs_staging in content:
                    content = content.replace(abs_staging, placeholder)

                abs_staging_win = str(staging_dir.absolute()).replace("/", "\\")
                if abs_staging_win in content:
                    content = content.replace(abs_staging_win, placeholder)

                if content != original:
                    script.write_text(content, encoding="utf-8")
                    patched += 1
            except OSError as e:
                sys.stderr.write(f"WARNING: Failed to patch {script}: {e}\n")
        return patched
def _resolve_runtime_paths(env: dict) -> None:
    """Dynamically replace @GHC_PREFIX@ with the active sys.prefix at runtime,
    then regenerate package.cache.

    Args:
            env: The sterilized environment dict with proper LD_LIBRARY_PATH set.
    """
    prefix_clean = sys.prefix.replace("\\", "/")

    # 🐍 Ouroboros: Iterate over the BaseResource registry to locate all path targets dynamically
    # 🧪 Alchemist: List comprehension condenses nested loops for dynamic target extraction
    targets = [
        target for resource_cls in BaseResource.registry
        for resource_path in resource_cls.locate()
        for target in resource_cls.extract_targets(resource_path)
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
                # 🧪 Alchemist: Native byte regex replaces verbose decode/encode logic
                if b" " in prefix_clean_bytes and b"\0" not in content_to_write:
                    content_to_write = re.sub(rb'(?<!")(@GHC_PREFIX@[^\s"]+)', rb'"\1"', content_to_write)
                with target_path.open("wb") as out:
                    out.write(content_to_write.replace(b"@GHC_PREFIX@", prefix_clean_bytes))
                if target.endswith(".conf"):
                    patched_any_conf = True
        except OSError as e:
            sys.stderr.write(f"WARNING: Failed to resolve runtime paths for {target_path}: {e}\n")

    # 🧪 Alchemist: any() replaces manual flag variables and loops for succinct boolean reduction
    if patched_any_conf or any(
        not (pkg_db / "package.cache").exists()
        for pkg_db in PackageDBResource.locate()
    ):
        for pkg_db in PackageDBResource.locate():
            _ghc_pkg_recache(str(pkg_db), env)


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
        # 🧪 Alchemist: Dictionary merge operator (|) replaces unpacking
        subprocess.run(
            [ghc_pkg, "recache", "--package-db", pkg_db_dir],
            env=env | {"GHC_PACKAGE_PATH": pkg_db_dir},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as e:
        sys.stderr.write(f"WARNING: ghc-pkg recache failed for {pkg_db_dir}: {e}\n")


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
            sys.exit(subprocess.run(cmd, env=env).returncode)
    except FileNotFoundError:
        _die(f"FATAL ERROR: Binary not found at '{binary_path}'.")
    except KeyboardInterrupt:
        sys.exit(130)
    except (subprocess.SubprocessError, OSError) as e:
        _die(f"FATAL ERROR: Execution failed: {e}")


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

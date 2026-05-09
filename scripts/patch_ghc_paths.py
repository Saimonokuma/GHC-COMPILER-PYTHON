#!/usr/bin/env python3
"""
Patch GHC paths for relocatability.

Replaces hardcoded absolute paths with @GHC_PREFIX@ placeholders
that will be resolved at runtime by wrapper.py.

FIX v4: Dynamic path discovery across all platforms.
- Linux/macOS: settings and package.conf.d live inside lib/ghc-{ver}/lib/
- Windows: settings and package.conf.d live directly inside lib/
- Windows: wrapper scripts live in lib/bin/ (not bin/)
- Recursive fallback for all path discovery
"""

import sys
import re
from pathlib import Path

GHC_VERSION = "9.4.8"
PLACEHOLDER_PREFIX = "@GHC_PREFIX@"
STAGING_DIR = Path("ghc-bindist")


def robust_patcher(func):
    """Decorator that handles reading, writing, and safe exception trapping for file patching."""
    def wrapper(file_path: Path, *args, **kwargs) -> bool:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            new_content = func(content, file_path, *args, **kwargs)
            if new_content and new_content != content:
                file_path.write_text(new_content, encoding="utf-8")
                return True
        except OSError:
            pass
        return False
    return wrapper


from typing import Callable
def locator_factory(target_name: str, is_dir: bool, validator: Callable = None):
    """Declarative path locator factory."""
    def locator(staging_dir: Path):
        candidates = [
            staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "lib" / target_name,
            staging_dir / "lib" / target_name,
        ]

        for c in candidates:
            if (is_dir and c.is_dir()) or (not is_dir and c.is_file()):
                return c

        for candidate in staging_dir.rglob(target_name):
            if (is_dir and candidate.is_dir()) or (not is_dir and candidate.is_file()):
                if not validator or validator(candidate):
                    return candidate
        return None
    return locator


def _settings_validator(p: Path) -> bool:
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        return '"C compiler command"' in content or '"C preprocessor command"' in content
    except OSError:
        return False


def _pkg_db_validator(p: Path) -> bool:
    return bool(list(p.glob("*.conf")))


find_settings_file = locator_factory("settings", is_dir=False, validator=_settings_validator)
find_package_database = locator_factory("package.conf.d", is_dir=True, validator=_pkg_db_validator)


@robust_patcher
def patch_settings_file(content: str, _path: Path) -> str:
    """Replace hardcoded GHC paths in the settings file with @GHC_PREFIX@."""
    patterns = [
        (
            r"/usr/local/lib/ghc-" + re.escape(GHC_VERSION),
            f"{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}",
        ),
        (
            r"/usr/lib/ghc-" + re.escape(GHC_VERSION),
            f"{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}",
        ),
        (
            r"/opt/ghc/" + re.escape(GHC_VERSION),
            f"{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}",
        ),
        (
            r"/ghc-prefix/lib/ghc-" + re.escape(GHC_VERSION),
            f"{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}",
        ),
        (r"/ghc-prefix", PLACEHOLDER_PREFIX),
    ]
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    return content


@robust_patcher
def patch_single_conf(content: str, _path: Path) -> str:
    """Replace hardcoded paths in a single .conf file."""
    content = re.sub(
        r"dynamic-library-dirs:\s*/[^\s]+",
        f"dynamic-library-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}",
        content,
    )
    content = re.sub(
        r"library-dirs:\s*/[^\s]+",
        f"library-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}",
        content,
    )
    content = re.sub(
        r"include-dirs:\s*/[^\s]+",
        f"include-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}/include",
        content,
    )
    content = re.sub(
        r"/ghc-prefix/lib/ghc-" + re.escape(GHC_VERSION),
        f"{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}",
        content,
    )
    content = re.sub(r"/ghc-prefix", PLACEHOLDER_PREFIX, content)
    return content

def patch_package_database(pkg_db: Path):
    """Replace hardcoded paths in package.conf.d/*.conf files."""
    patched_count = 0
    for conf_file in pkg_db.glob("*.conf"):
        if patch_single_conf(conf_file):
            patched_count += 1

    # Remove cached package database
    cache_file = pkg_db / "package.cache"
    if cache_file.exists():
        try:
            cache_file.unlink()
        except OSError:
            pass

    return patched_count


@robust_patcher
def patch_single_bin_wrapper(content: str, _path: Path, staging_dir: Path) -> str:
    # Standard Unix prefixes
    content = re.sub(
        r"/usr/local/lib/ghc-" + re.escape(GHC_VERSION),
        f"{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}",
        content,
    )
    content = re.sub(r"/ghc-prefix", PLACEHOLDER_PREFIX, content)

    # Windows specific prefixes (or absolute staging paths)
    abs_staging = staging_dir.absolute().as_posix()
    if abs_staging in content:
        content = content.replace(abs_staging, PLACEHOLDER_PREFIX)

    # Also handle Windows backslash paths
    abs_staging_win = str(staging_dir.absolute()).replace("/", "\\\\")
    if abs_staging_win in content:
        content = content.replace(abs_staging_win, PLACEHOLDER_PREFIX)

    return content


def patch_bin_wrappers(staging_dir: Path):
    """Replace hardcoded GHC paths in the bin/* wrapper scripts."""
    bin_dirs = [
        staging_dir / "bin",  # Linux/macOS top-level wrappers
        staging_dir
        / "lib"
        / f"ghc-{GHC_VERSION}"
        / "bin",  # Linux/macOS internal binaries
        staging_dir / "lib" / "bin",  # Windows layout
    ]

    total_patched = 0

    for bin_dir in bin_dirs:
        if not bin_dir.exists():
            continue

        patched_unix = 0
        patched_cmd = 0

        for script in bin_dir.iterdir():
            if not script.is_file():
                continue

            is_cmd = script.name.endswith(".cmd")
            # Skip actual Windows executables (.exe)
            if script.name.endswith(".exe"):
                continue

            if patch_single_bin_wrapper(script, staging_dir=staging_dir):
                if is_cmd:
                    patched_cmd += 1
                else:
                    patched_unix += 1

        if patched_cmd > 0:
            print(
                f"Patched {patched_unix} wrapper scripts and {patched_cmd} .cmd files in {bin_dir}"
            )
        else:
            print(f"Patched {patched_unix} wrapper scripts in {bin_dir}")

        total_patched += patched_unix + patched_cmd

    return total_patched


def main():
    if not STAGING_DIR.exists():
        print("Staging directory not found, skipping path patching.")
        return 1

    # Find and patch settings file
    settings_path = find_settings_file(STAGING_DIR)
    if settings_path:
        print(f"Found settings file: {settings_path}")
        modified = patch_settings_file(settings_path)
        if modified:
            print(f"Patched settings file: {settings_path}")
        else:
            print(f"Settings file did not require patching: {settings_path}")
    else:
        print("WARNING: GHC settings file not found in any expected location.")
        print("Searched locations:")
        print(f"  - {STAGING_DIR / 'lib' / f'ghc-{GHC_VERSION}' / 'lib' / 'settings'}")
        print(f"  - {STAGING_DIR / 'lib' / 'settings'}")
        print("  - (recursive search for 'settings' files)")

    # Find and patch package database
    pkg_db = find_package_database(STAGING_DIR)
    if pkg_db:
        print(f"Found package database: {pkg_db}")
        patched = patch_package_database(pkg_db)
        print(f"Patched {patched} package.conf files in {pkg_db}")
    else:
        print("WARNING: GHC package database not found in any expected location.")
        print("Searched locations:")
        print(
            f"  - {STAGING_DIR / 'lib' / f'ghc-{GHC_VERSION}' / 'lib' / 'package.conf.d'}"
        )
        print(f"  - {STAGING_DIR / 'lib' / 'package.conf.d'}")
        print("  - (recursive search for 'package.conf.d' directories)")

    # Patch wrapper scripts in bin/
    total_wrappers = patch_bin_wrappers(STAGING_DIR)
    print(f"Total wrapper scripts patched: {total_wrappers}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

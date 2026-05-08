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


def find_settings_file(staging_dir: Path):
    """Find the GHC settings file by searching the actual directory structure.

    On Linux/macOS: ghc-bindist/lib/ghc-{ver}/lib/settings
    On Windows:     ghc-bindist/lib/settings
    Also searches recursively for any file named 'settings' containing GHC config keys.
    """
    # Explicit platform-specific paths
    candidates = [
        # Linux/macOS: settings lives inside the nested lib dir
        staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "lib" / "settings",
        # Windows: settings lives directly in lib/
        staging_dir / "lib" / "settings",
    ]

    for c in candidates:
        if c.exists():
            return c

    # Dynamic fallback: find any file named 'settings' that looks like a GHC config
    for candidate in staging_dir.rglob("settings"):
        if candidate.is_file():
            try:
                content = candidate.read_text(encoding="utf-8", errors="replace")
                if (
                    '"C compiler command"' in content
                    or '"C preprocessor command"' in content
                ):
                    return candidate
            except OSError:
                continue

    return None


def find_package_database(staging_dir: Path):
    """Find the GHC package database directory by searching the actual directory structure.

    On Linux/macOS: ghc-bindist/lib/ghc-{ver}/lib/package.conf.d/
    On Windows:     ghc-bindist/lib/package.conf.d/
    Also searches recursively for any directory named 'package.conf.d' containing .conf files.
    """
    # Explicit platform-specific paths
    candidates = [
        # Linux/macOS: package.conf.d lives inside the nested lib dir
        staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "lib" / "package.conf.d",
        # Windows: package.conf.d lives directly in lib/
        staging_dir / "lib" / "package.conf.d",
    ]

    for c in candidates:
        if c.exists() and c.is_dir():
            return c

    # Dynamic fallback: find any directory named 'package.conf.d' with .conf files
    for candidate in staging_dir.rglob("package.conf.d"):
        if candidate.is_dir() and list(candidate.glob("*.conf")):
            return candidate

    return None


def patch_settings_file(settings_path: Path):
    """Replace hardcoded GHC paths in the settings file with @GHC_PREFIX@."""
    content = settings_path.read_text(encoding="utf-8", errors="replace")
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
    modified = False
    for pattern, replacement in patterns:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            content = new_content
            modified = True
    if modified:
        settings_path.write_text(content, encoding="utf-8")
    return modified


def patch_package_database(pkg_db: Path):
    """Replace hardcoded paths in package.conf.d/*.conf files."""
    patched_count = 0
    for conf_file in pkg_db.glob("*.conf"):
        try:
            content = conf_file.read_text(encoding="utf-8", errors="replace")
            original = content
            # Replace various path patterns
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
            if content != original:
                conf_file.write_text(content, encoding="utf-8")
                patched_count += 1
        except OSError:
            pass

    # Remove cached package database
    cache_file = pkg_db / "package.cache"
    try:
        cache_file.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass

    return patched_count


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

            try:
                content = script.read_text(encoding="utf-8", errors="replace")
                original = content

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

                if content != original:
                    script.write_text(content, encoding="utf-8")
                    if is_cmd:
                        patched_cmd += 1
                    else:
                        patched_unix += 1
            except OSError:
                pass

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

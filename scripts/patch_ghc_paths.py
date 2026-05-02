#!/usr/bin/env python3
"""
Patch GHC paths for relocatability.

Replaces hardcoded absolute paths with @GHC_PREFIX@ placeholders
that will be resolved at runtime by wrapper.py.

FIX v3: Explicit fallback configurations across OS platforms.
"""

import os
import sys
import re
from pathlib import Path

GHC_VERSION = "9.4.8"
PLACEHOLDER_PREFIX = "@GHC_PREFIX@"
STAGING_DIR = Path("ghc-bindist")

def find_settings_file(staging_dir: Path):
	"""Find the GHC settings file in multiple possible locations."""
	candidates = [
		staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "settings",  # Correct path on all platforms
		staging_dir / "settings",  # Legacy fallback
		staging_dir / "lib" / "settings",  # Legacy fallback
	]
	for c in candidates:
		if c.exists():
			return c
	return None

def find_package_database(staging_dir: Path):
	"""Find the GHC package database directory in multiple possible locations."""
	candidates = [
		staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "package.conf.d",  # Correct path on all platforms
		staging_dir / "package.conf.d",  # Legacy fallback
	]
	for c in candidates:
		if c.exists():
			return c
	return None

def patch_settings_file(settings_path: Path):
	"""Replace hardcoded GHC paths in the settings file with @GHC_PREFIX@."""
	content = settings_path.read_text(encoding="utf-8", errors="replace")
	patterns = [
		(r'/usr/local/lib/ghc-' + re.escape(GHC_VERSION), f'{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}'),
		(r'/usr/lib/ghc-' + re.escape(GHC_VERSION), f'{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}'),
		(r'/opt/ghc/' + re.escape(GHC_VERSION), f'{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}'),
		(r'/ghc-prefix/lib/ghc-' + re.escape(GHC_VERSION), f'{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}'),
		(r'/ghc-prefix', PLACEHOLDER_PREFIX),
	]
	modified = False
	for pattern, replacement in patterns:
		new_content = re.sub(pattern, replacement, content)
		if new_content != content:
			content = new_content
			modified = True
	if modified:
		settings_path.write_text(content, encoding="utf-8")

def patch_package_database(pkg_db: Path):
	"""Replace hardcoded paths in package.conf.d/*.conf files."""
	for conf_file in pkg_db.glob("*.conf"):
		try:
			content = conf_file.read_text(encoding="utf-8", errors="replace")
			original = content
			# Replace various path patterns
			content = re.sub(
				r'dynamic-library-dirs:\s*/[^\s]+',
				f'dynamic-library-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}',
				content,
			)
			content = re.sub(
				r'library-dirs:\s*/[^\s]+',
				f'library-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}',
				content,
			)
			content = re.sub(
				r'include-dirs:\s*/[^\s]+',
				f'include-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}/include',
				content,
			)
			content = re.sub(
				r'/ghc-prefix/lib/ghc-' + re.escape(GHC_VERSION),
				f'{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}',
				content,
			)
			content = re.sub(r'/ghc-prefix', PLACEHOLDER_PREFIX, content)
			if content != original:
				conf_file.write_text(content, encoding="utf-8")
		except Exception:
			pass

	# Remove cached package database
	cache_file = pkg_db / "package.cache"
	if cache_file.exists():
		cache_file.unlink()

def patch_bin_wrappers(staging_dir: Path):
	"""Replace hardcoded GHC paths in the bin/* wrapper scripts."""
	bin_dirs = [
		staging_dir / "bin",
		staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "bin"
	]

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
				content = re.sub(r'/usr/local/lib/ghc-' + re.escape(GHC_VERSION), f'{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}', content)
				content = re.sub(r'/ghc-prefix', PLACEHOLDER_PREFIX, content)

				# Windows specific prefixes (or absolute staging paths)
				abs_staging = staging_dir.absolute().as_posix()
				if abs_staging in content:
					content = content.replace(abs_staging, PLACEHOLDER_PREFIX)

				# Also handle Windows backslash paths
				abs_staging_win = str(staging_dir.absolute()).replace("/", "\\")
				if abs_staging_win in content:
					content = content.replace(abs_staging_win, PLACEHOLDER_PREFIX)

				if content != original:
					script.write_text(content, encoding="utf-8")
					if is_cmd:
						patched_cmd += 1
					else:
						patched_unix += 1
			except Exception:
				pass

		if patched_cmd > 0:
			print(f"Patched {patched_unix} wrapper scripts and {patched_cmd} .cmd files in {bin_dir}")
		else:
			print(f"Patched {patched_unix} wrapper scripts in {bin_dir}")

def main():
	if not STAGING_DIR.exists():
		print("Staging directory not found, skipping path patching.")
		return 1

	# Find and patch settings file
	settings_path = find_settings_file(STAGING_DIR)
	if settings_path:
		print(f"Patching settings file: {settings_path}")
		patch_settings_file(settings_path)
	else:
		print("WARNING: GHC settings file not found in any expected location.")

	# Find and patch package database
	pkg_db = find_package_database(STAGING_DIR)
	if pkg_db:
		print(f"Patching package database: {pkg_db}")
		patch_package_database(pkg_db)
	else:
		print("WARNING: GHC package database not found in any expected location.")

	# Patch wrapper scripts in bin/
	patch_bin_wrappers(STAGING_DIR)

	return 0

if __name__ == "__main__":
	sys.exit(main())

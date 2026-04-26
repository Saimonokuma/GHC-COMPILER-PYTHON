#!/usr/bin/env python3
"""Patches GHC settings and package database for relocatability."""

import os
import re
import sys
from pathlib import Path

STAGING_DIR = Path("ghc-bindist")
GHC_VERSION = "9.4.8"
PLACEHOLDER_PREFIX = "@GHC_PREFIX@"


def find_settings_file(staging_dir: Path) -> Path | None:
	candidates = list(staging_dir.rglob("settings"))
	for c in candidates:
		if c.is_file():
			return c
	return None


def patch_settings(settings_path: Path) -> None:
	print(f"Patching: {settings_path}")
	content = settings_path.read_text(encoding="utf-8", errors="replace")
	original = content

	patterns = [
		(r'/usr/local/lib/ghc-' + re.escape(GHC_VERSION), f'{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}'),
		(r'/usr/lib/ghc-' + re.escape(GHC_VERSION), f'{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}'),
		(r'/opt/ghc/' + re.escape(GHC_VERSION), f'{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}'),
	]
	for pattern, replacement in patterns:
		content = re.sub(pattern, replacement, content)

	if content != original:
		settings_path.write_text(content, encoding="utf-8")
		print(f"  ✓ Patched with placeholder: {PLACEHOLDER_PREFIX}")
	else:
		print("	 ℹ No hardcoded paths found")


def patch_package_database(staging_dir: Path) -> None:
	candidates = list(staging_dir.rglob("package.conf.d"))
	pkg_dbs = [c for c in candidates if c.is_dir()]

	if not pkg_dbs:
		print("	 ⚠ Package database not found")
		return

	for pkg_db in pkg_dbs:
		print(f"Patching: {pkg_db}")
		patched = 0
		for conf in pkg_db.glob("*.conf"):
			try:
				content = conf.read_text(encoding="utf-8", errors="replace")
				original = content
				content = re.sub(r'dynamic-library-dirs:\s*/[^\s]+',
							   f'dynamic-library-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}', content)
				content = re.sub(r'library-dirs:\s*/[^\s]+',
							   f'library-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}', content)
				content = re.sub(r'include-dirs:\s*/[^\s]+',
							   f'include-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}/include', content)
				if content != original:
					conf.write_text(content, encoding="utf-8")
					patched += 1
			except Exception as e:
				print(f"  ⚠ Failed to patch {conf.name}: {e}")

		print(f"  ✓ Patched {patched} package config files in {pkg_db}")

		# Remove stale cache
		cache = pkg_db / "package.cache"
		if cache.exists():
			cache.unlink()
			print("	 ✓ Removed stale package.cache")


def main() -> int:
	print("GHC Path Relocatability Patcher")
	if not STAGING_DIR.exists():
		print(f"FATAL: {STAGING_DIR} not found")
		return 1

	settings = find_settings_file(STAGING_DIR)
	if settings:
		patch_settings(settings)
	else:
		print("	 ⚠ settings file not found")

	patch_package_database(STAGING_DIR)

	print("Path patching complete.")
	return 0


if __name__ == "__main__":
	sys.exit(main())

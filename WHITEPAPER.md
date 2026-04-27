***

## WHITEPAPER DEFINITIVO — ghc-compiler-python v9.4.8 (UNIX-PATCHED v2)

### Architettura Completa e Implementazione di Produzione (Cross-Platform)

---

### 📁 STRUTTURA DEL REPOSITORY

```text
ghc-compiler-python/
├── .github/
│	└── workflows/
│		└── build.yml
├── ghc_compiler_python/
│	├── __init__.py
│	├── wrapper.py
│	└── py.typed
├── scripts/
│	├── fetch_binaries.sh
│	├── optimize_binaries.sh
│	├── fix_macos_rpaths.sh		 ← NEW
│	└── patch_ghc_paths.py
├── tests/
│	├── test_wrapper.py
│	└── test_e2e.py
├── ghc-bindist/
│	└── .gitkeep
├── pyproject.toml
├── README.md
├── LICENSE
├── MANIFEST.in
└── .gitignore
```

---

### 📄 1. `pyproject.toml` — Completo e Corretto (FIX v2)

```toml
# pyproject.toml — ghc-compiler-python v9.4.8
# PEP 621 compliant, PEP 427 wheel packaging, Hatchling build backend

[build-system]
requires = ["hatchling>=1.24.0"]
build-backend = "hatchling.build"

[project]
name = "ghc-compiler-python"
version = "9.4.8"
description = "Native GHC 9.4.8 compiler and Cabal 3.10.3.0 tooling packaged as an isolated Python Wheel"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.8"
authors = [
	{name = "ghc-compiler-python contributors"},
]
classifiers = [
	"Development Status :: 5 - Production/Stable",
	"Intended Audience :: Developers",
	"License :: OSI Approved :: MIT License",
	"Operating System :: POSIX :: Linux",
	"Operating System :: MacOS :: MacOS X",
	"Operating System :: Microsoft :: Windows",
	"Programming Language :: Haskell",
	"Programming Language :: Python :: 3",
	"Topic :: Software Development :: Compilers",
	"Topic :: Software Development :: Build Tools",
]
dependencies = []

[project.scripts]
ghc-wrapper = "ghc_compiler_python.wrapper:execute_ghc"
ghci-wrapper = "ghc_compiler_python.wrapper:execute_ghci"
cabal-wrapper = "ghc_compiler_python.wrapper:execute_cabal"

[tool.hatch.build.targets.wheel]
strict-naming = true

# Mappa gli eseguibili nel PATH del Venv (bin)
[tool.hatch.build.targets.wheel.shared-scripts]
"ghc-bindist/bin" = ""

# FIX UNIX v2: Mappa lib e share nel Venv.
# Hatchling shared-data maps to <venv>/<key> on install.
[tool.hatch.build.targets.wheel.shared-data]
"ghc-bindist/lib" = "lib"
"ghc-bindist/share" = "share"

[tool.hatch.build.targets.sdist]
include = [
	"/scripts/",
	"/tests/",
	"/README.md",
	"/LICENSE",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

### 📄 2. `ghc_compiler_python/__init__.py` — Package Metadata

```python
# ghc_compiler_python/__init__.py
"""
ghc-compiler-python: Native GHC 9.4.8 and Cabal 3.10.3.0 packaged as a Python Wheel.

This package provides isolated, hermetically-sealed Haskell compilation tooling
accessible via Python subprocess wrappers. No system-level GHC installation required.
"""

__version__ = "9.4.8"
__ghc_version__ = "9.4.8"
__cabal_version__ = "3.10.3.0"
__author__ = "ghc-compiler-python contributors"
__license__ = "MIT"

__all__ = [
	"__version__",
	"__ghc_version__",
	"__cabal_version__",
]
```

---

### 📄 3. `ghc_compiler_python/wrapper.py` — Subprocess Proxy (FIX v2)

```python
# ghc_compiler_python/wrapper.py
"""
Subprocess proxy wrappers for GHC and Cabal binaries.

Provides hermetic execution isolation, environment sterilization,
pre-flight C-linker validation, runtime path resolution, and process proxying.

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

HASKELL_POLLUTION_VARS: List[str] = [
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
]

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


def _sterilize_environment() -> dict:
	"""Create a sterilized subprocess environment."""
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

	# FIX v2: Set DYLD_LIBRARY_PATH on macOS for runtime library resolution
	if sys.platform == "darwin":
		lib_dir = os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}")
		if os.path.isdir(lib_dir):
			existing_dyld = env.get("DYLD_LIBRARY_PATH", "")
			if existing_dyld:
				env["DYLD_LIBRARY_PATH"] = f"{lib_dir}{os.pathsep}{existing_dyld}"
			else:
				env["DYLD_LIBRARY_PATH"] = lib_dir

	return env


def _resolve_runtime_paths() -> None:
	"""Dynamically replace @GHC_PREFIX@ with the active sys.prefix at runtime."""
	lib_dir = os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}")

	targets = []
	settings_file = os.path.join(lib_dir, "settings")
	if os.path.exists(settings_file):
		targets.append(settings_file)

	pkg_db = os.path.join(lib_dir, "package.conf.d")
	if os.path.exists(pkg_db):
		targets.extend(
			os.path.join(pkg_db, f)
			for f in os.listdir(pkg_db)
			if f.endswith(".conf")
		)

	# FIX v2: Also check root-level package.conf.d (Windows layout)
	root_pkg_db = os.path.join(sys.prefix, "package.conf.d")
	if os.path.exists(root_pkg_db):
		targets.extend(
			os.path.join(root_pkg_db, f)
			for f in os.listdir(root_pkg_db)
			if f.endswith(".conf")
		)

	for target in targets:
		try:
			with open(target, "r", encoding="utf-8") as f:
				content = f.read()
			if "@GHC_PREFIX@" in content:
				prefix_clean = sys.prefix.replace("\\", "/")
				content = content.replace("@GHC_PREFIX@", prefix_clean)
				with open(target, "w", encoding="utf-8") as f:
					f.write(content)
		except Exception:
			pass  # Ignore read-only files if already patched


def _handle_sigterm(signum: int, frame) -> None:
	sys.exit(128 + signum)


def _handle_sigint(signum: int, frame) -> None:
	sys.exit(130)


def _execute_tool(tool_name: str, extra_args: List[str] = None) -> NoReturn:
	"""Generic subprocess proxy for bundled Haskell tooling."""
	signal.signal(signal.SIGTERM, _handle_sigterm)
	signal.signal(signal.SIGINT, _handle_sigint)

	_validate_c_linker()
	env = _sterilize_environment()
	_resolve_runtime_paths()
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
```

---

### 📄 4. `scripts/fetch_binaries.sh` (FIX v2 — Robust DESTDIR)

```bash
#!/usr/bin/env bash
set -euo pipefail

GHC_VERSION="9.4.8"
CABAL_VERSION="3.10.3.0"
STAGING_DIR="ghc-bindist"
BUILD_DIR="build_artifacts"

GHC_BASE_URL="https://downloads.haskell.org/~ghc/${GHC_VERSION}"
CABAL_BASE_URL="https://downloads.haskell.org/~cabal/cabal-install-${CABAL_VERSION}"

OS=$(uname -s)
ARCH=$(uname -m)

echo "============================================"
echo " GHC/Cabal Binary Acquisition System"
echo " Platform: ${OS}/${ARCH}"
echo "============================================"

if [[ "${OS}" == "Linux" && "${ARCH}" == "x86_64" ]]; then
	GHC_TAR="ghc-${GHC_VERSION}-x86_64-centos7-linux.tar.xz"
	CABAL_TAR="cabal-install-${CABAL_VERSION}-x86_64-linux-centos7.tar.xz"
elif [[ "${OS}" == "Darwin" && "${ARCH}" == "x86_64" ]]; then
	GHC_TAR="ghc-${GHC_VERSION}-x86_64-apple-darwin.tar.xz"
	CABAL_TAR="cabal-install-${CABAL_VERSION}-x86_64-darwin.tar.xz"
elif [[ "${OS}" == "Darwin" && "${ARCH}" == "arm64" ]]; then
	GHC_TAR="ghc-${GHC_VERSION}-aarch64-apple-darwin.tar.xz"
	CABAL_TAR="cabal-install-${CABAL_VERSION}-aarch64-darwin.tar.xz"
elif [[ "${OS}" == MINGW* || "${OS}" == MSYS* || "${OS}" == CYGWIN* ]] && [[ "${ARCH}" == "x86_64" ]]; then
	GHC_TAR="ghc-${GHC_VERSION}-x86_64-unknown-mingw32.tar.xz"
	CABAL_TAR="cabal-install-${CABAL_VERSION}-x86_64-windows.zip"
else
	echo "FATAL: Unsupported OS/Architecture combination: ${OS}/${ARCH}" >&2
	exit 1
fi

GHC_URL="${GHC_BASE_URL}/${GHC_TAR}"
CABAL_URL="${CABAL_BASE_URL}/${CABAL_TAR}"
GHC_SHA_URL="${GHC_BASE_URL}/SHA256SUMS"
CABAL_SHA_URL="${CABAL_BASE_URL}/SHA256SUMS"

mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

echo "[1/5] Fetching SHA256 checksum indices..."
curl --fail --silent --show-error --location "${GHC_SHA_URL}" -o ghc_sha256.txt
curl --fail --silent --show-error --location "${CABAL_SHA_URL}" -o cabal_sha256.txt

echo "[2/5] Downloading GHC ${GHC_VERSION}..."
curl --fail --silent --show-error --location "${GHC_URL}" -o "${GHC_TAR}"

echo "[3/5] Downloading Cabal ${CABAL_VERSION}..."
curl --fail --silent --show-error --location "${CABAL_URL}" -o "${CABAL_TAR}"

echo "[4/5] Validating cryptographic hashes..."
if ! grep "${GHC_TAR}" ghc_sha256.txt | sha256sum --check --status; then
	echo "FATAL: GHC SHA-256 validation failed!" >&2
	exit 3
fi

if ! grep "${CABAL_TAR}" cabal_sha256.txt | sha256sum --check --status; then
	echo "FATAL: Cabal SHA-256 validation failed!" >&2
	exit 3
fi

echo "[5/5] Unpacking archives into staging directory..."
mkdir -p "../${STAGING_DIR}/bin"
mkdir -p "../${STAGING_DIR}/lib"
mkdir -p "../${STAGING_DIR}/share"

tar -xf "${GHC_TAR}"
GHC_EXTRACTED_DIR=$(tar -tf "${GHC_TAR}" | head -1 | cut -f1 -d"/")

# FIX v2: Unix requires ./configure && make install for proper library layout
if [[ "${OS}" == "Linux" || "${OS}" == "Darwin" ]]; then
	echo "Unix detected: Running GHC configure and make install..."
	cd "${GHC_EXTRACTED_DIR}"

	# FIX v2: Use absolute path for DESTDIR to avoid path resolution issues
	DESTDIR_ABS="$(cd ../.. && pwd)/${STAGING_DIR}_raw"
	rm -rf "${DESTDIR_ABS}"
	mkdir -p "${DESTDIR_ABS}"

	./configure --prefix="/ghc-prefix"
	make install DESTDIR="${DESTDIR_ABS}"
	cd ..

	# Flatten the DESTDIR structure into staging
	if [ -d "${DESTDIR_ABS}/ghc-prefix" ]; then
		cp -a "${DESTDIR_ABS}/ghc-prefix/"* "../${STAGING_DIR}/"
	else
		echo "WARNING: Expected DESTDIR structure not found, attempting alternative layout..."
		# Try to find the installed files regardless of structure
		find "${DESTDIR_ABS}" -mindepth 1 -maxdepth 1 -exec cp -a {} "../${STAGING_DIR}/" \;
	fi
	rm -rf "${DESTDIR_ABS}"

	# Extract Cabal for Unix
	tar -xf "${CABAL_TAR}"
	cp cabal "../${STAGING_DIR}/bin/" 2>/dev/null || true
else
	# Windows: Relocatable by default, simple copy
	echo "Windows detected: Performing native extraction..."
	cp -a "${GHC_EXTRACTED_DIR}/bin/"* "../${STAGING_DIR}/bin/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/lib/"* "../${STAGING_DIR}/lib/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/share/"* "../${STAGING_DIR}/share/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/settings" "../${STAGING_DIR}/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/package.conf.d" "../${STAGING_DIR}/" 2>/dev/null || true

	# Extract Cabal for Windows
	unzip -q "${CABAL_TAR}" -d "../${STAGING_DIR}/bin/"
fi

cd ..
rm -rf "${BUILD_DIR}"

# FIX v2: Verify critical directories exist after extraction
echo "Verifying staging directory structure..."
for dir in bin lib; do
	if [ ! -d "${STAGING_DIR}/${dir}" ]; then
		echo "FATAL: Staging directory ${STAGING_DIR}/${dir} is missing!" >&2
		exit 4
	fi
done

# Verify GHC lib directory has expected content
GHC_LIB_DIR="${STAGING_DIR}/lib/ghc-${GHC_VERSION}"
if [ -d "${GHC_LIB_DIR}" ]; then
	DYLIB_COUNT=$(find "${GHC_LIB_DIR}" -name "*.dylib" 2>/dev/null | wc -l || echo "0")
	SO_COUNT=$(find "${GHC_LIB_DIR}" -name "*.so" 2>/dev/null | wc -l || echo "0")
	echo "GHC lib directory: ${GHC_LIB_DIR}"
	echo "	Dynamic libraries found: ${DYLIB_COUNT} dylibs, ${SO_COUNT} shared objects"
else
	echo "WARNING: Expected GHC lib directory not found at ${GHC_LIB_DIR}"
	echo "Available directories in ${STAGING_DIR}/lib/:"
	ls -la "${STAGING_DIR}/lib/" 2>/dev/null || echo "	(lib directory empty or missing)"
fi

echo "Binary acquisition complete."
```

---

### 📄 5. `scripts/optimize_binaries.sh` (FIX v2 — macOS-Compatible Strip)

```bash
#!/usr/bin/env bash
set -euo pipefail

STAGING_DIR="ghc-bindist"
OS=$(uname -s)

if [[ "${OS}" == "MINGW"* || "${OS}" == "MSYS"* || "${OS}" == "CYGWIN"* ]]; then
	echo "Windows detected — optimization skipped."
	exit 0
fi

echo "Initiating binary size reduction sequence..."
echo "Initial size:"
du -sh "${STAGING_DIR}/" 2>/dev/null || true

# FIX v2: Use platform-appropriate strip flags
if [[ "${OS}" == "Darwin" ]]; then
	echo "macOS detected: Using strip -x for Mach-O binaries..."
	# macOS strip: -x removes local symbols but preserves global symbols
	# This is safe for Mach-O binaries and shared libraries
	find "${STAGING_DIR}" -type f \( -perm -0100 \) -exec sh -c '
		for f; do
			if file "$f" | grep -q "Mach-O"; then
				strip -x "$f" 2>/dev/null || true
			fi
		done
	' sh {} +
	# Also strip dylibs
	find "${STAGING_DIR}" -type f \( -name "*.dylib" \) -exec strip -x {} + 2>/dev/null || true
else
	echo "Linux detected: Using strip --strip-unneeded..."
	find "${STAGING_DIR}" -type f \( -perm -0100 -o -name "*.so" \) -exec strip --strip-unneeded {} + 2>/dev/null || true
fi

echo "Final size:"
du -sh "${STAGING_DIR}/" 2>/dev/null || true
echo "Symbol stripping and binary optimization complete."
```

---

### 📄 6. `scripts/fix_macos_rpaths.sh` — NEW (Critical for delocate-wheel)

```bash
#!/usr/bin/env bash
# fix_macos_rpaths.sh — Fix @rpath references in GHC binaries for macOS wheel packaging
#
# GHC binaries reference their dynamic libraries via @rpath, which points to
# the configure-time prefix (/ghc-prefix/lib/ghc-9.4.8). This script uses
# install_name_tool to change @rpath to use @loader_path relative references,
# enabling delocate-wheel to find and bundle the dylibs correctly.
set -euo pipefail

GHC_VERSION="9.4.8"
STAGING_DIR="ghc-bindist"
OS=$(uname -s)

if [[ "${OS}" != "Darwin" ]]; then
	echo "Not macOS — rpath fix skipped."
	exit 0
fi

LIB_DIR="${STAGING_DIR}/lib/ghc-${GHC_VERSION}"
BIN_DIR="${STAGING_DIR}/bin"

echo "============================================"
echo " macOS @rpath Repair System"
echo " GHC Version: ${GHC_VERSION}"
echo "============================================"

# Verify directories exist
if [ ! -d "${LIB_DIR}" ]; then
	echo "FATAL: GHC lib directory not found at ${LIB_DIR}" >&2
	echo "Available directories in ${STAGING_DIR}/lib/:" >&2
	ls -la "${STAGING_DIR}/lib/" 2>/dev/null >&2 || true
	exit 1
fi

if [ ! -d "${BIN_DIR}" ]; then
	echo "FATAL: GHC bin directory not found at ${BIN_DIR}" >&2
	exit 1
fi

OLD_RPATH="/ghc-prefix/lib/ghc-${GHC_VERSION}"

# Step 1: Fix @rpath in all dylibs
echo "[1/3] Fixing @rpath in dynamic libraries..."
DYLIB_COUNT=0
for dylib in "${LIB_DIR}"/*.dylib; do
	if [ -f "$dylib" ]; then
		dylib_name=$(basename "$dylib")

		# Change the install name (id) to use @rpath
		install_name_tool -id "@rpath/${dylib_name}" "$dylib" 2>/dev/null || true

		# Remove old rpath if present
		install_name_tool -delete_rpath "${OLD_RPATH}" "$dylib" 2>/dev/null || true

		# Add @loader_path so dylibs can find each other in the same directory
		install_name_tool -add_rpath "@loader_path" "$dylib" 2>/dev/null || true

		DYLIB_COUNT=$((DYLIB_COUNT + 1))
	fi
done
echo "	Fixed ${DYLIB_COUNT} dynamic libraries."

# Step 2: Fix @rpath in all binaries
echo "[2/3] Fixing @rpath in executables..."
BIN_COUNT=0
for binary in "${BIN_DIR}"/*; do
	if [ -f "$binary" ] && file "$binary" | grep -q "Mach-O"; then
		# Remove old rpath
		install_name_tool -delete_rpath "${OLD_RPATH}" "$binary" 2>/dev/null || true

		# Add new rpath: @loader_path/../lib/ghc-VERSION
		# This matches the installed layout: bin/ghc -> ../lib/ghc-VERSION/
		install_name_tool -add_rpath "@loader_path/../lib/ghc-${GHC_VERSION}" "$binary" 2>/dev/null || true

		BIN_COUNT=$((BIN_COUNT + 1))
	fi
done
echo "	Fixed ${BIN_COUNT} executables."

# Step 3: Verify the fixes
echo "[3/3] Verifying @rpath repairs..."
VERIFY_FAIL=0
for binary in "${BIN_DIR}"/*; do
	if [ -f "$binary" ] && file "$binary" | grep -q "Mach-O"; then
		# Check that old rpath is gone
		if otool -l "$binary" | grep -q "${OLD_RPATH}"; then
			echo "	WARNING: Old rpath still present in $(basename "$binary")" >&2
			VERIFY_FAIL=$((VERIFY_FAIL + 1))
		fi
		# Check that new rpath is present
		if ! otool -l "$binary" | grep -q "@loader_path/../lib/ghc-${GHC_VERSION}"; then
			echo "	WARNING: New rpath not found in $(basename "$binary")" >&2
			VERIFY_FAIL=$((VERIFY_FAIL + 1))
		fi
	fi
done

if [ ${VERIFY_FAIL} -gt 0 ]; then
	echo "WARNING: ${VERIFY_FAIL} verification checks failed. Wheel may have library resolution issues."
else
	echo "	All @rpath repairs verified successfully."
fi

echo "macOS @rpath repair complete."
```

---

### 📄 7. `scripts/patch_ghc_paths.py` (FIX v2 — Robust Package Database Detection)

```python
#!/usr/bin/env python3
"""
Patch GHC paths for relocatability.

Replaces hardcoded absolute paths with @GHC_PREFIX@ placeholders
that will be resolved at runtime by wrapper.py.

FIX v2: Improved package database detection with multiple fallback paths.
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
		staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "settings",  # Unix layout
		staging_dir / "settings",  # Windows / flat layout
	]
	for c in candidates:
		if c.exists():
			return c
	return None


def find_package_database(staging_dir: Path):
	"""Find the GHC package database directory in multiple possible locations."""
	candidates = [
		staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "package.conf.d",	# Unix layout
		staging_dir / "package.conf.d",	 # Windows / flat layout
	]
	for c in candidates:
		if c.exists():
			return c
	return None


def patch_settings_file(settings_path: Path):
	"""Replace hardcoded GHC paths in the settings file with @GHC_PREFIX@."""
	content = settings_path.read_text(encoding="utf-8", errors="replace")
	patterns = [
		(r'/usr/local/lib/ghc-' + re.escape(GHC_VERSION), PLACEHOLDER_PREFIX + '/lib/ghc-' + GHC_VERSION),
		(r'/usr/lib/ghc-' + re.escape(GHC_VERSION), PLACEHOLDER_PREFIX + '/lib/ghc-' + GHC_VERSION),
		(r'/opt/ghc/' + re.escape(GHC_VERSION), PLACEHOLDER_PREFIX + '/lib/ghc-' + GHC_VERSION),
		(r'/ghc-prefix/lib/ghc-' + re.escape(GHC_VERSION), PLACEHOLDER_PREFIX + '/lib/ghc-' + GHC_VERSION),
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
		print("Searched locations:")
		for candidate in [
			STAGING_DIR / "lib" / f"ghc-{GHC_VERSION}" / "package.conf.d",
			STAGING_DIR / "package.conf.d",
		]:
			print(f"  - {candidate}")

	return 0


if __name__ == "__main__":
	sys.exit(main())
```

---

### 📄 8. `.github/workflows/build.yml` (FIX v2 — macOS rpath + delocate)

```yaml
name: Build and Publish Native GHC Wheel

on:
  push:
	tags: ['v*']
  pull_request:
	branches: [main]
  workflow_dispatch:

jobs:
  build-wheels:
	name: Build on ${{ matrix.os }}
	runs-on: ${{ matrix.os }}
	strategy:
	  matrix:
		include:
		  - os: ubuntu-latest
			platform: manylinux2014_x86_64
		  - os: macos-latest
			platform: macosx_arm64
		  - os: windows-latest
			platform: win_amd64
	  fail-fast: false

	steps:
	  - uses: actions/checkout@v4
	  - uses: actions/setup-python@v5
		with:
		  python-version: '3.10'

	  - name: Install System C-Linker (Linux)
		if: runner.os == 'Linux'
		run: sudo apt-get update && sudo apt-get install -y gcc binutils patchelf

	  - name: Install System C-Linker (macOS)
		if: runner.os == 'macOS'
		run: xcode-select -p || xcode-select --install

	  - name: Install System C-Linker (Windows)
		if: runner.os == 'Windows'
		shell: pwsh
		run: |
		  choco install mingw -y
		  echo "C:\msys64\mingw64\bin" | Out-File -FilePath $env:GITHUB_PATH -Append

	  - name: Install Python Build Dependencies
		run: pip install --upgrade pip build hatchling auditwheel delocate

	  - name: Fetch and Verify GHC/Cabal Binaries
		shell: bash
		run: bash scripts/fetch_binaries.sh

	  - name: Optimize Binary Size
		shell: bash
		run: bash scripts/optimize_binaries.sh

	  - name: Patch GHC Paths for Relocatability
		shell: bash
		run: python scripts/patch_ghc_paths.py

	  # FIX v2: New step — Fix macOS @rpath references before building
	  - name: Fix macOS Dynamic Library Paths
		if: runner.os == 'macOS'
		shell: bash
		run: bash scripts/fix_macos_rpaths.sh

	  - name: Build PEP 427 Python Wheel
		run: python -m build --wheel

	  - name: Vendor Dynamic Libraries (Linux)
		if: runner.os == 'Linux'
		run: |
		  auditwheel repair dist/*.whl --plat manylinux2014_x86_64 -w wheelhouse/
		  rm -rf dist/*
		  mv wheelhouse/*.whl dist/

	  # FIX v2: Use delocate-wheel with --libs-dir to find GHC dylibs
	  - name: Vendor Dynamic Libraries (macOS)
		if: runner.os == 'macOS'
		shell: bash
		run: |
		  # Extract the wheel to find the library directory structure
		  WHL=$(ls dist/*.whl)
		  echo "Processing wheel: ${WHL}"

		  # Find the GHC lib directory in the extracted wheel structure
		  # delocate-wheel needs to know where the dylibs are
		  LIB_SEARCH_DIR=$(python -c "
		  import zipfile, os
		  with zipfile.ZipFile('${WHL}') as z:
			  for name in z.namelist():
				  if 'ghc-${{ matrix.platform == 'macosx_arm64' && '9.4.8' || '9.4.8' }}/libHS' in name and name.endswith('.dylib'):
					  dirname = os.path.dirname(name)
					  print(dirname)
					  break
		  " 2>/dev/null || echo "")

		  if [ -n "${LIB_SEARCH_DIR}" ]; then
			  echo "Found GHC dylibs directory in wheel: ${LIB_SEARCH_DIR}"
			  # delocate-wheel with explicit library search path
			  delocate-wheel -v --libs-dir="${LIB_SEARCH_DIR}" dist/*.whl || {
				  echo "delocate-wheel failed, attempting fallback..."
				  # Fallback: try without explicit libs-dir
				  delocate-wheel -v dist/*.whl || {
					  echo "WARNING: delocate-wheel failed. Wheel may have runtime library resolution issues on macOS."
					  echo "The DYLD_LIBRARY_PATH fallback in wrapper.py should handle this."
				  }
			  }
		  else
			  echo "WARNING: Could not find GHC dylibs directory in wheel."
			  echo "Attempting delocate-wheel without explicit library path..."
			  delocate-wheel -v dist/*.whl || {
				  echo "WARNING: delocate-wheel failed. Relying on DYLD_LIBRARY_PATH fallback."
			  }
		  fi

	  - name: End-to-End Compilation Validation
		shell: bash
		run: |
		  python -m venv test-env
		  if [[ "${OSTYPE}" == "msys" || "${OSTYPE}" == "win32" ]]; then
			source test-env/Scripts/activate
		  else
			source test-env/bin/activate
		  fi

		  pip install dist/*.whl

		  cat << 'EOF' > HelloWorld.hs
		  module Main where
		  main :: IO ()
		  main = putStrLn "E2E Native Compiler Validation Successful."
		  EOF

		  ghc-wrapper HelloWorld.hs

		  if [[ "${OSTYPE}" == "msys" || "${OSTYPE}" == "win32" ]]; then
			./HelloWorld.exe
		  else
			./HelloWorld
		  fi

		  cabal-wrapper --version
		  deactivate

	  - name: Upload Artifacts
		uses: actions/upload-artifact@v4
		with:
		  name: ghc-wheels-${{ matrix.platform }}
		  path: dist/*.whl
		  retention-days: 30
```

---

### 📄 9. `MANIFEST.in`

```
include LICENSE
include README.md
recursive-include scripts *.sh *.py
recursive-include tests *.py
recursive-include ghc_compiler_python *.py *.typed
```

---

### 📄 10. `.gitignore`

```gitignore
# Build artifacts
build_artifacts/
dist/
*.egg-info/
*.whl

# Staged binaries
ghc-bindist/bin/
ghc-bindist/lib/
ghc-bindist/share/
ghc-bindist/settings
ghc-bindist/package.conf.d

# Python
__pycache__/
*.pyc
*.pyo
.eggs/
venv/
test-env/

# IDE & OS
.vscode/
.idea/
.DS_Store
Thumbs.db

# Test artifacts
HelloWorld
HelloWorld.exe
HelloWorld.hi
HelloWorld.o
```

***

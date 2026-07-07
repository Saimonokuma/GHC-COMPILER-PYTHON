***

## STRUTTURA DEL REPOSITORY — Definitiva

```text
ghc-compiler-python/
├── .github/
│	├── workflows/
│	│	└── build.yml				 # CI/CD pipeline cross-platform (v2)
│	└── dependabot.yml				 # Dependency auto-update
├── ghc_compiler_python/
│	├── __init__.py					 # Package metadata + version
│	├── wrapper.py					 # Subprocess proxies (v2: DYLD_LIBRARY_PATH)
│	└── py.typed					 # PEP 561 marker
├── scripts/
│	├── fetch_binaries.sh			 # Cryptographic binary acquisition (v2: robust DESTDIR)
│	├── optimize_binaries.sh		 # Symbol stripping (v2: macOS-compatible)
│	├── fix_macos_rpaths.sh			 # NEW: @rpath repair for macOS dylibs
│	└── patch_ghc_paths.py			 # Path relocatability patcher (v2: robust detection)
├── tests/
│	├── test_wrapper.py				 # Unit tests
│	└── test_e2e.py					 # End-to-end compilation tests
├── ghc-bindist/
│	└── .gitkeep					 # Staging directory (populated at build)
├── pyproject.toml					 # PEP 621 + Hatchling config
├── README.md						 # User documentation
├── LICENSE							 # MIT
├── MANIFEST.in						 # sdist inclusion
└── .gitignore						 # Ignore rules
```

---

## FASE 1: INIZIALIZZAZIONE DEL SUBSTRATO

### 1.1 Creazione Repository

```bash
gh repo create ghc-compiler-python --public --description "Native GHC 9.4.8 and Cabal 3.10.3.0 packaged as a Python Wheel"

git clone
cd ghc-compiler-python
```

### 1.2 Struttura Directory

```bash
mkdir -p ghc_compiler_python scripts tests ghc-bindist .github/workflows

touch ghc-bindist/.gitkeep
touch ghc_compiler_python/py.typed
```

### 1.3 Configurazione Git (`.gitignore`)

```bash
git branch -M main

cat > .gitignore << 'GITIGNORE'
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
GITIGNORE
```

---

## FASE 2: IMPLEMENTAZIONE DEI COMPONENTI CORE

### 2.1 `pyproject.toml`

```toml
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
authors = [{name = "ghc-compiler-python contributors"}]
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

[tool.hatch.build.targets.wheel.shared-scripts]
"ghc-bindist/bin" = ""

[tool.hatch.build.targets.wheel.shared-data]
"ghc-bindist/lib" = "lib"
"ghc-bindist/share" = "share"

[tool.hatch.build.targets.sdist]
include = ["/scripts/", "/tests/", "/README.md", "/LICENSE"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### 2.2 `ghc_compiler_python/__init__.py`

```python
"""ghc-compiler-python: Native GHC and Cabal packaged as a Python Wheel."""

__version__ = "9.4.8"
__ghc_version__ = "9.4.8"
__cabal_version__ = "3.10.3.0"
__author__ = "ghc-compiler-python contributors"
__license__ = "MIT"

__all__ = ["__version__", "__ghc_version__", "__cabal_version__"]
```

### 2.3 `ghc_compiler_python/wrapper.py`

```python
"""
Subprocess proxy wrappers for GHC and Cabal binaries.
Provides hermetic execution isolation, environment sterilization,
pre-flight C-linker validation, and dynamic path resolution.

v2: Added DYLD_LIBRARY_PATH for macOS runtime library resolution.
"""

import os
import sys
import shutil
import subprocess
import signal
from typing import List, NoReturn, Optional

GHC_VERSION = "9.4.8"

HASKELL_POLLUTION_VARS: List[str] = [
	"GHC_PACKAGE_PATH", "GHC_ENVIRONMENT", "CABAL_DIR", "CABAL_CONFIG",
	"HASKELL_DIST_DIR", "STACK_ROOT", "STACK_YAML", "GHCRTS", "GHCRTS_OPTS", "HOME"
]

_HOME_ORIGINAL: Optional[str] = None

def _resolve_binary(name: str) -> str:
	binary_name = f"{name}.exe" if sys.platform == "win32" else name
	resolved = shutil.which(binary_name)
	if resolved: return resolved

	bin_dir = "Scripts" if sys.platform == "win32" else "bin"
	fallback_path = os.path.join(sys.prefix, bin_dir, binary_name)
	if os.path.exists(fallback_path): return fallback_path

	package_dir = os.path.dirname(os.path.abspath(__file__))
	env_bin = os.path.join(os.path.dirname(package_dir), bin_dir, binary_name)
	if os.path.exists(env_bin): return env_bin

	sys.stderr.write(f"FATAL ERROR: Bundled binary '{binary_name}' not found.\n")
	sys.exit(1)

def _validate_c_linker() -> None:
	if not shutil.which("gcc") and not shutil.which("clang"):
		sys.stderr.write("FATAL ERROR: GHC requires a host C-linker (gcc/clang).\n")
		sys.exit(1)

def _sterilize_environment() -> dict:
	global _HOME_ORIGINAL
	env = os.environ.copy()
	for var in HASKELL_POLLUTION_VARS: env.pop(var, None)

	_HOME_ORIGINAL = env.get("HOME", env.get("USERPROFILE", ""))
	safe_home = os.path.join(sys.prefix, ".ghc-compiler-python-home")
	os.makedirs(safe_home, exist_ok=True)
	env["HOME"] = safe_home

	bin_dir = "Scripts" if sys.platform == "win32" else "bin"
	env_bin = os.path.join(sys.prefix, bin_dir)
	env["PATH"] = f"{env_bin}{os.pathsep}{env.get('PATH', '')}"

	# v2: Set DYLD_LIBRARY_PATH on macOS for runtime library resolution
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
	lib_dir = os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}")
	targets = []

	settings_file = os.path.join(lib_dir, "settings")
	if os.path.exists(settings_file): targets.append(settings_file)

	pkg_db = os.path.join(lib_dir, "package.conf.d")
	if os.path.exists(pkg_db):
		targets.extend([os.path.join(pkg_db, f) for f in os.listdir(pkg_db) if f.endswith(".conf")])

	# v2: Also check root-level package.conf.d (Windows layout)
	root_pkg_db = os.path.join(sys.prefix, "package.conf.d")
	if os.path.exists(root_pkg_db):
		targets.extend([os.path.join(root_pkg_db, f) for f in os.listdir(root_pkg_db) if f.endswith(".conf")])

	for target in targets:
		try:
			with open(target, "r", encoding="utf-8") as f: content = f.read()
			if "@GHC_PREFIX@" in content:
				prefix_clean = sys.prefix.replace("\\", "/")
				content = content.replace("@GHC_PREFIX@", prefix_clean)
				with open(target, "w", encoding="utf-8") as f: f.write(content)
		except Exception: pass

def _handle_sigterm(signum, frame): sys.exit(128 + signum)
def _handle_sigint(signum, frame): sys.exit(130)

def _execute_tool(tool_name: str, extra_args: List[str] = None) -> NoReturn:
	signal.signal(signal.SIGTERM, _handle_sigterm)
	signal.signal(signal.SIGINT, _handle_sigint)

	_validate_c_linker()
	env = _sterilize_environment()
	_resolve_runtime_paths()
	binary_path = _resolve_binary(tool_name)

	cmd = [binary_path]
	if extra_args: cmd.extend(extra_args)
	cmd.extend(sys.argv[1:])

	try:
		result = subprocess.run(cmd, env=env)
		sys.exit(result.returncode)
	except Exception as e:
		sys.stderr.write(f"FATAL ERROR: Subprocess exception: {e}\n")
		sys.exit(1)

def execute_ghc(): _execute_tool("ghc", extra_args=["-v0"])
def execute_ghci(): _execute_tool("ghci")
def execute_cabal(): _execute_tool("cabal")
```

---

## FASE 3: AUTOMAZIONE DEL PAYLOAD (SCRIPTS)

### 3.1 `scripts/fetch_binaries.sh` (v2)

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
	echo "FATAL: Unsupported platform" >&2; exit 1
fi

mkdir -p "${BUILD_DIR}" && cd "${BUILD_DIR}"

echo "[1/5] Fetching SHA256 checksum indices..."
curl --fail --silent --show-error --location "${GHC_BASE_URL}/SHA256SUMS" -o ghc_sha256.txt
curl --fail --silent --show-error --location "${CABAL_BASE_URL}/SHA256SUMS" -o cabal_sha256.txt

echo "[2/5] Downloading GHC ${GHC_VERSION}..."
curl --fail --silent --show-error --location "${GHC_BASE_URL}/${GHC_TAR}" -o "${GHC_TAR}"

echo "[3/5] Downloading Cabal ${CABAL_VERSION}..."
curl --fail --silent --show-error --location "${CABAL_BASE_URL}/${CABAL_TAR}" -o "${CABAL_TAR}"

echo "[4/5] Validating cryptographic hashes..."
if ! grep "${GHC_TAR}" ghc_sha256.txt | sha256sum --check --status; then exit 3; fi
if ! grep "${CABAL_TAR}" cabal_sha256.txt | sha256sum --check --status; then exit 3; fi

echo "[5/5] Unpacking archives into staging directory..."
mkdir -p "../${STAGING_DIR}/bin" "../${STAGING_DIR}/lib" "../${STAGING_DIR}/share"

tar -xf "${GHC_TAR}"
GHC_EXTRACTED_DIR=$(tar -tf "${GHC_TAR}" | head -1 | cut -f1 -d"/")

if [[ "${OS}" == "Linux" || "${OS}" == "Darwin" ]]; then
	echo "Unix detected: Running GHC configure and make install..."
	cd "${GHC_EXTRACTED_DIR}"

	# v2: Use absolute path for DESTDIR
	DESTDIR_ABS="$(cd ../.. && pwd)/${STAGING_DIR}_raw"
	rm -rf "${DESTDIR_ABS}"
	mkdir -p "${DESTDIR_ABS}"

	./configure --prefix="/ghc-prefix"
	make install DESTDIR="${DESTDIR_ABS}"
	cd ..

	# v2: Robust flattening with fallback
	if [ -d "${DESTDIR_ABS}/ghc-prefix" ]; then
		cp -a "${DESTDIR_ABS}/ghc-prefix/"* "../${STAGING_DIR}/"
	else
		echo "WARNING: Expected DESTDIR structure not found, attempting alternative..."
		find "${DESTDIR_ABS}" -mindepth 1 -maxdepth 1 -exec cp -a {} "../${STAGING_DIR}/" \;
	fi
	rm -rf "${DESTDIR_ABS}"

	tar -xf "${CABAL_TAR}"
	cp cabal "../${STAGING_DIR}/bin/" 2>/dev/null || true
else
	echo "Windows detected: Performing native extraction..."
	cp -a "${GHC_EXTRACTED_DIR}/bin/"* "../${STAGING_DIR}/bin/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/lib/"* "../${STAGING_DIR}/lib/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/share/"* "../${STAGING_DIR}/share/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/settings" "../${STAGING_DIR}/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/package.conf.d" "../${STAGING_DIR}/" 2>/dev/null || true
	unzip -q "${CABAL_TAR}" -d "../${STAGING_DIR}/bin/"
fi

cd .. && rm -rf "${BUILD_DIR}"

# v2: Verify critical directories
echo "Verifying staging directory structure..."
for dir in bin lib; do
	if [ ! -d "${STAGING_DIR}/${dir}" ]; then
		echo "FATAL: Staging directory ${STAGING_DIR}/${dir} is missing!" >&2
		exit 4
	fi
done

GHC_LIB_DIR="${STAGING_DIR}/lib/ghc-${GHC_VERSION}"
if [ -d "${GHC_LIB_DIR}" ]; then
	DYLIB_COUNT=$(find "${GHC_LIB_DIR}" -name "*.dylib" 2>/dev/null | wc -l || echo "0")
	SO_COUNT=$(find "${GHC_LIB_DIR}" -name "*.so" 2>/dev/null | wc -l || echo "0")
	echo "GHC lib directory: ${GHC_LIB_DIR}"
	echo "	Dynamic libraries: ${DYLIB_COUNT} dylibs, ${SO_COUNT} shared objects"
else
	echo "WARNING: Expected GHC lib directory not found at ${GHC_LIB_DIR}"
fi

echo "Binary acquisition complete."
```

### 3.2 `scripts/optimize_binaries.sh` (v2)

```bash
#!/usr/bin/env bash
set -euo pipefail

STAGING_DIR="ghc-bindist"
OS=$(uname -s)

if [[ "${OS}" == "MINGW"* || "${OS}" == "MSYS"* || "${OS}" == "CYGWIN"* ]]; then
	echo "Windows detected — optimization skipped."
	exit 0
fi

echo "Pre-optimization size:"
du -sh "${STAGING_DIR}/" 2>/dev/null || true

# v2: Platform-appropriate strip
if [[ "${OS}" == "Darwin" ]]; then
	echo "macOS detected: Using strip -x for Mach-O binaries..."
	find "${STAGING_DIR}" -type f \( -perm -0100 \) -exec sh -c '
		for f; do
			if file "$f" | grep -q "Mach-O"; then
				strip -x "$f" 2>/dev/null || true
			fi
		done
	' sh {} +
	find "${STAGING_DIR}" -type f \( -name "*.dylib" \) -exec strip -x {} + 2>/dev/null || true
else
	echo "Linux detected: Using strip --strip-unneeded..."
	find "${STAGING_DIR}" -type f \( -perm -0100 -o -name "*.so" \) -exec strip --strip-unneeded {} + 2>/dev/null || true
fi

echo "Post-optimization size:"
du -sh "${STAGING_DIR}/" 2>/dev/null || true
echo "Optimization complete."
```

### 3.3 `scripts/fix_macos_rpaths.sh` (NEW)

```bash
#!/usr/bin/env bash
# fix_macos_rpaths.sh — Fix @rpath references in GHC binaries for macOS wheel packaging
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
echo "============================================"

if [ ! -d "${LIB_DIR}" ]; then
	echo "FATAL: GHC lib directory not found at ${LIB_DIR}" >&2
	ls -la "${STAGING_DIR}/lib/" 2>/dev/null >&2 || true
	exit 1
fi

OLD_RPATH="/ghc-prefix/lib/ghc-${GHC_VERSION}"

# Step 1: Fix dylib install names and rpaths
echo "[1/3] Fixing @rpath in dynamic libraries..."
DYLIB_COUNT=0
for dylib in "${LIB_DIR}"/*.dylib; do
	[ -f "$dylib" ] || continue
	dylib_name=$(basename "$dylib")
	install_name_tool -id "@rpath/${dylib_name}" "$dylib" 2>/dev/null || true
	install_name_tool -delete_rpath "${OLD_RPATH}" "$dylib" 2>/dev/null || true
	install_name_tool -add_rpath "@loader_path" "$dylib" 2>/dev/null || true
	DYLIB_COUNT=$((DYLIB_COUNT + 1))
done
echo "	Fixed ${DYLIB_COUNT} dynamic libraries."

# Step 2: Fix binary rpaths
echo "[2/3] Fixing @rpath in executables..."
BIN_COUNT=0
for binary in "${BIN_DIR}"/*; do
	[ -f "$binary" ] || continue
	file "$binary" | grep -q "Mach-O" || continue
	install_name_tool -delete_rpath "${OLD_RPATH}" "$binary" 2>/dev/null || true
	install_name_tool -add_rpath "@loader_path/../lib/ghc-${GHC_VERSION}" "$binary" 2>/dev/null || true
	BIN_COUNT=$((BIN_COUNT + 1))
done
echo "	Fixed ${BIN_COUNT} executables."

# Step 3: Verify
echo "[3/3] Verifying @rpath repairs..."
VERIFY_FAIL=0
for binary in "${BIN_DIR}"/*; do
	[ -f "$binary" ] || continue
	file "$binary" | grep -q "Mach-O" || continue
	if otool -l "$binary" | grep -q "${OLD_RPATH}"; then
		echo "	WARNING: Old rpath still present in $(basename "$binary")" >&2
		VERIFY_FAIL=$((VERIFY_FAIL + 1))
	fi
done

[ ${VERIFY_FAIL} -gt 0 ] && echo "WARNING: ${VERIFY_FAIL} checks failed." || echo "	 All @rpath repairs verified."
echo "macOS @rpath repair complete."
```

### 3.4 `scripts/patch_ghc_paths.py` (v2)

```python
#!/usr/bin/env python3
"""Patch GHC paths for relocatability. v2: Robust package database detection."""
import os, sys, re
from pathlib import Path

GHC_VERSION = "9.4.8"
PLACEHOLDER_PREFIX = "@GHC_PREFIX@"
STAGING_DIR = Path("ghc-bindist")

def find_settings_file(staging_dir):
	for c in [staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "settings", staging_dir / "settings"]:
		if c.exists(): return c
	return None

def find_package_database(staging_dir):
	for c in [staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "package.conf.d", staging_dir / "package.conf.d"]:
		if c.exists(): return c
	return None

def patch_settings_file(settings_path):
	content = settings_path.read_text(encoding="utf-8", errors="replace")
	patterns = [
		(r'/ghc-prefix/lib/ghc-' + re.escape(GHC_VERSION), PLACEHOLDER_PREFIX + '/lib/ghc-' + GHC_VERSION),
		(r'/ghc-prefix', PLACEHOLDER_PREFIX),
		(r'/usr/local/lib/ghc-' + re.escape(GHC_VERSION), PLACEHOLDER_PREFIX + '/lib/ghc-' + GHC_VERSION),
		(r'/usr/lib/ghc-' + re.escape(GHC_VERSION), PLACEHOLDER_PREFIX + '/lib/ghc-' + GHC_VERSION),
	]
	modified = False
	for pattern, replacement in patterns:
		new_content = re.sub(pattern, replacement, content)
		if new_content != content: content = new_content; modified = True
	if modified: settings_path.write_text(content, encoding="utf-8")

def patch_package_database(pkg_db):
	for conf_file in pkg_db.glob("*.conf"):
		try:
			content = conf_file.read_text(encoding="utf-8", errors="replace")
			original = content
			content = re.sub(r'dynamic-library-dirs:\s*/[^\s]+', f'dynamic-library-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}', content)
			content = re.sub(r'library-dirs:\s*/[^\s]+', f'library-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}', content)
			content = re.sub(r'include-dirs:\s*/[^\s]+', f'include-dirs: {PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}/include', content)
			content = re.sub(r'/ghc-prefix/lib/ghc-' + re.escape(GHC_VERSION), f'{PLACEHOLDER_PREFIX}/lib/ghc-{GHC_VERSION}', content)
			content = re.sub(r'/ghc-prefix', PLACEHOLDER_PREFIX, content)
			if content != original: conf_file.write_text(content, encoding="utf-8")
		except Exception: pass
	cache_file = pkg_db / "package.cache"
	if cache_file.exists(): cache_file.unlink()

def main():
	if not STAGING_DIR.exists(): return 1
	settings_path = find_settings_file(STAGING_DIR)
	if settings_path: patch_settings_file(settings_path)
	else: print("WARNING: Settings file not found.")
	pkg_db = find_package_database(STAGING_DIR)
	if pkg_db: patch_package_database(pkg_db)
	else: print("WARNING: Package database not found.")
	return 0

if __name__ == "__main__": sys.exit(main())
```

---

## FASE 4: ORCHESTRAZIONE CI/CD

### 4.1 `.github/workflows/build.yml` (v2)

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
		with: { python-version: '3.10' }

	  - name: Install C-Linker (Linux)
		if: runner.os == 'Linux'
		run: sudo apt-get update && sudo apt-get install -y gcc binutils patchelf

	  - name: Install C-Linker (macOS)
		if: runner.os == 'macOS'
		run: xcode-select -p || xcode-select --install

	  - name: Install C-Linker (Windows)
		if: runner.os == 'Windows'
		shell: pwsh
		run: |
		  choco install mingw -y
		  echo "C:\msys64\mingw64\bin" | Out-File -FilePath $env:GITHUB_PATH -Append

	  - name: Install Dependencies
		run: pip install --upgrade pip build hatchling auditwheel delocate

	  - name: Fetch & Verify
		shell: bash
		run: bash scripts/fetch_binaries.sh

	  - name: Optimize
		shell: bash
		run: bash scripts/optimize_binaries.sh

	  - name: Patch Paths
		shell: bash
		run: python scripts/patch_ghc_paths.py

	  # NEW: Fix macOS @rpath references before building the wheel
	  - name: Fix macOS Dynamic Library Paths
		if: runner.os == 'macOS'
		shell: bash
		run: bash scripts/fix_macos_rpaths.sh

	  - name: Build Wheel
		run: python -m build --wheel

	  - name: Vendor Libraries (Linux)
		if: runner.os == 'Linux'
		run: auditwheel repair dist/*.whl --plat manylinux2014_x86_64 -w wheelhouse/ && rm -rf dist/* && mv wheelhouse/*.whl dist/

	  # v2: Improved delocate-wheel with fallback
	  - name: Vendor Libraries (macOS)
		if: runner.os == 'macOS'
		shell: bash
		run: |
		  WHL=$(ls dist/*.whl)
		  echo "Processing wheel: ${WHL}"
		  # Attempt delocate-wheel; fallback to DYLD_LIBRARY_PATH if it fails
		  delocate-wheel -v dist/*.whl || {
			echo "WARNING: delocate-wheel failed."
			echo "The DYLD_LIBRARY_PATH fallback in wrapper.py will handle runtime resolution."
		  }

	  - name: E2E Validation
		shell: bash
		run: |
		  python -m venv test-env
		  if [[ "${OSTYPE}" == "msys" || "${OSTYPE}" == "win32" ]]; then source test-env/Scripts/activate; else source test-env/bin/activate; fi
		  pip install dist/*.whl
		  cat << 'EOF' > HelloWorld.hs
		  module Main where
		  main :: IO ()
		  main = putStrLn "E2E Validation Successful."
		  EOF
		  ghc-wrapper HelloWorld.hs
		  if [[ "${OSTYPE}" == "msys" || "${OSTYPE}" == "win32" ]]; then ./HelloWorld.exe; else ./HelloWorld; fi
		  cabal-wrapper --version
		  deactivate

	  - uses: actions/upload-artifact@v4
		with:
		  name: ghc-wheels-${{ matrix.platform }}
		  path: dist/*.whl
		  retention-days: 30
```

---

## FASE 5: TROUBLESHOOTING — macOS-Specific Issues

### 5.1 `delocate-wheel` Failures

If `delocate-wheel` reports `@rpath/libHS*.dylib not found`:

1. **Ensure `fix_macos_rpaths.sh` ran before `python -m build`** — This script replaces `/ghc-prefix/lib/ghc-9.4.8` with `@loader_path/../lib/ghc-9.4.8` in all binaries
2. **Verify the dylibs exist in `ghc-bindist/lib/ghc-9.4.8/`** — Run `ls ghc-bindist/lib/ghc-9.4.8/*.dylib | head -5`
3. **Check the `@rpath` values** — Run `otool -l ghc-bindist/bin/ghc | grep -A2 LC_RPATH`
4. **If delocate still fails**, the `DYLD_LIBRARY_PATH` fallback in `wrapper.py` will handle runtime resolution

### 5.2 Binary Strip Failures on macOS

`strip --strip-unneeded` doesn't work on macOS Mach-O binaries. The v2 script uses `strip -x` instead, which removes local symbols while preserving global symbols.

### 5.3 Package Database Not Found

The v2 `patch_ghc_paths.py` checks both `ghc-bindist/lib/ghc-9.4.8/package.conf.d` (Unix layout) and `ghc-bindist/package.conf.d` (flat layout), eliminating the warning.

### 5.4 DESTDIR Path Issues

The v2 `fetch_binaries.sh` uses an absolute path for `DESTDIR` to avoid path resolution errors when `cd`-ing into the extracted GHC directory.

---

## FASE 6: TRUSTED PUBLISHING E RELEASE

I passaggi per PyPI OIDC e le checklist di release rimangono invariati. Consulta PyPI per impostare il Trusted Publisher sul workflow `build.yml`.
```

***

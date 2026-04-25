## 📁 STRUTTURA DEL REPOSITORY — Definitiva

```
ghc-compiler-python/
├── .github/
│	├── workflows/
│	│	└── build.yml			   # CI/CD pipeline
│	└── dependabot.yml			   # Dependency auto-update
├── ghc_compiler_python/
│	├── __init__.py				   # Package metadata + version
│	├── wrapper.py				   # Subprocess proxies (ghc, ghci, cabal)
│	└── py.typed				   # PEP 561 marker
├── scripts/
│	├── fetch_binaries.sh		   # Cryptographic binary acquisition
│	├── optimize_binaries.sh	   # Symbol stripping
│	└── patch_ghc_paths.py		   # Path relocatability patcher
├── tests/
│	├── test_wrapper.py			   # Unit tests
│	└── test_e2e.py				   # End-to-end compilation tests
├── ghc-bindist/
│	└── .gitkeep				   # Staging directory (populated at build)
├── pyproject.toml				   # PEP 621 + Hatchling config
├── README.md					   # User documentation
├── LICENSE						   # MIT
├── MANIFEST.in					   # sdist inclusion
├── .gitignore					   # Ignore rules
└── .pre-commit-config.yaml		   # Pre-commit hooks (optional)
```

---

## FASE 1: INIZIALIZZAZIONE DEL SUBSTRATO

### 1.1 Creazione Repository

```bash
# Crea il repository su GitHub tramite web UI o:
gh repo create ghc-compiler-python --public --description "Native GHC 9.4.8 and Cabal 3.10.3.0 packaged as a Python Wheel"

# Clone locale
git clone https://github.com/TUO_USERNAME/ghc-compiler-python.git
cd ghc-compiler-python
```

### 1.2 Struttura Directory

```bash
# Crea l'albero completo
mkdir -p ghc_compiler_python
mkdir -p scripts
mkdir -p tests
mkdir -p ghc-bindist
mkdir -p .github/workflows

# File placeholder per directory vuote
touch ghc-bindist/.gitkeep
touch ghc_compiler_python/py.typed
```

### 1.3 Configurazione Git

```bash
# Inizializza con main branch
git branch -M main

# Configura .gitignore PRIMA di aggiungere file
cat > .gitignore << 'GITIGNORE'
# Build artifacts
build_artifacts/
dist/
*.egg-info/
*.whl

# Staged binaries (fetched at build time)
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

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
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

### 2.1 `pyproject.toml` — Configurazione Centrale

```toml
# pyproject.toml — ghc-compiler-python v9.4.8
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
	"Programming Language :: Python :: 3.8",
	"Programming Language :: Python :: 3.9",
	"Programming Language :: Python :: 3.10",
	"Programming Language :: Python :: 3.11",
	"Programming Language :: Python :: 3.12",
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

### 2.2 `ghc_compiler_python/__init__.py` — Metadata

```python
"""ghc-compiler-python: Native GHC and Cabal packaged as a Python Wheel."""

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

### 2.3 `ghc_compiler_python/wrapper.py` — Subprocess Proxy Completo

```python
"""
Subprocess proxy wrappers for GHC and Cabal binaries.

Provides hermetic execution isolation, environment sterilization,
pre-flight C-linker validation, and process proxying.
"""

import os
import sys
import shutil
import subprocess
import signal
from typing import List, NoReturn, Optional

GHC_VERSION = "9.4.8"
CABAL_VERSION = "3.10.3.0"

# Environment variables that MUST be purged to prevent host contamination
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
]

_HOME_ORIGINAL: Optional[str] = None


def _resolve_binary(name: str) -> str:
	"""Resolve absolute path to a bundled native binary."""
	binary_name = f"{name}.exe" if sys.platform == "win32" else name

	# Strategy 1: PATH resolution
	resolved = shutil.which(binary_name)
	if resolved:
		return resolved

	# Strategy 2: sys.prefix fallback
	bin_dir = "Scripts" if sys.platform == "win32" else "bin"
	fallback_path = os.path.join(sys.prefix, bin_dir, binary_name)
	if os.path.exists(fallback_path):
		return fallback_path

	# Strategy 3: Package-relative fallback
	package_dir = os.path.dirname(os.path.abspath(__file__))
	env_bin = os.path.join(os.path.dirname(package_dir), bin_dir, binary_name)
	if os.path.exists(env_bin):
		return env_bin

	sys.stderr.write(
		f"FATAL ERROR: Bundled binary '{binary_name}' not found.\n"
		f"Searched: PATH, {fallback_path}, {env_bin}\n"
	)
	sys.exit(1)


def _validate_c_linker() -> None:
	"""Assert existence of a host C-linker (gcc or clang)."""
	if not shutil.which("gcc") and not shutil.which("clang"):
		sys.stderr.write(
			"FATAL ERROR: GHC requires a host C-linker.\n"
			"Install 'gcc' or 'clang' and ensure it is in PATH.\n"
			"  Ubuntu/Debian: sudo apt-get install gcc\n"
			"  macOS: xcode-select --install\n"
			"  Windows: Install MinGW-w64 or MSYS2\n"
		)
		sys.exit(1)


def _sterilize_environment() -> dict:
	"""Create a sterilized subprocess environment."""
	global _HOME_ORIGINAL
	env = os.environ.copy()

	# Purge Haskell pollution
	for var in HASKELL_POLLUTION_VARS:
		env.pop(var, None)

	# Override HOME to prevent reading ~/.ghc/ and ~/.cabal/
	_HOME_ORIGINAL = env.get("HOME", env.get("USERPROFILE", ""))
	safe_home = os.path.join(sys.prefix, ".ghc-compiler-python-home")
	os.makedirs(safe_home, exist_ok=True)
	env["HOME"] = safe_home

	# Ensure bundled binaries are FIRST on PATH
	bin_dir = "Scripts" if sys.platform == "win32" else "bin"
	env_bin = os.path.join(sys.prefix, bin_dir)
	env["PATH"] = f"{env_bin}{os.pathsep}{env.get('PATH', '')}"

	return env


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
	except PermissionError:
		sys.stderr.write(f"FATAL ERROR: Permission denied executing '{binary_path}'.\n")
		sys.exit(126)
	except KeyboardInterrupt:
		sys.exit(130)
	except Exception as e:
		sys.stderr.write(f"FATAL ERROR: Subprocess exception: {e}\n")
		sys.exit(1)


def execute_ghc() -> NoReturn:
	"""ghc-wrapper — isolated GHC compilation proxy."""
	_execute_tool("ghc", extra_args=["-v0"])


def execute_ghci() -> NoReturn:
	"""ghci-wrapper — isolated GHCi interactive proxy."""
	_execute_tool("ghci")


def execute_cabal() -> NoReturn:
	"""cabal-wrapper — isolated Cabal build tool proxy."""
	_execute_tool("cabal")
```

### 2.4 `MANIFEST.in`

```
include LICENSE
include README.md
recursive-include scripts *.sh *.py
recursive-include tests *.py
```

### 2.5 `LICENSE`

```
MIT License

Copyright (c) 2026 ghc-compiler-python contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## FASE 3: AUTOMAZIONE DEL PAYLOAD (SCRIPTS)

### 3.1 `scripts/fetch_binaries.sh`

```bash
#!/usr/bin/env bash
# fetch_binaries.sh — Cryptographic binary acquisition
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

# Platform detection
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
	echo "FATAL: Unsupported platform: ${OS}/${ARCH}" >&2
	exit 1
fi

# Download
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

echo "[1/5] Fetching SHA256 checksums..."
curl --fail --silent --show-error --location "${GHC_BASE_URL}/SHA256SUMS" -o ghc_sha256.txt
curl --fail --silent --show-error --location "${CABAL_BASE_URL}/SHA256SUMS" -o cabal_sha256.txt

echo "[2/5] Downloading GHC ${GHC_VERSION}..."
curl --fail --silent --show-error --location "${GHC_BASE_URL}/${GHC_TAR}" -o "${GHC_TAR}"

echo "[3/5] Downloading Cabal ${CABAL_VERSION}..."
curl --fail --silent --show-error --location "${CABAL_BASE_URL}/${CABAL_TAR}" -o "${CABAL_TAR}"

# Validate
echo "[4/5] Validating cryptographic hashes..."
if ! grep "${GHC_TAR}" ghc_sha256.txt | sha256sum --check --status; then
	echo "FATAL: GHC SHA-256 validation failed!" >&2
	exit 3
fi
if ! grep "${CABAL_TAR}" cabal_sha256.txt | sha256sum --check --status; then
	echo "FATAL: Cabal SHA-256 validation failed!" >&2
	exit 3
fi
echo "	✓ All checksums validated"

# Extract
echo "[5/5] Unpacking archives..."
mkdir -p "../${STAGING_DIR}/bin"
mkdir -p "../${STAGING_DIR}/lib"
mkdir -p "../${STAGING_DIR}/share"

if [[ "${CABAL_TAR}" == *.zip ]]; then
	unzip -q "${CABAL_TAR}" -d "../${STAGING_DIR}/bin/"
else
	tar -xf "${CABAL_TAR}" -C "../${STAGING_DIR}/bin/"
fi

tar -xf "${GHC_TAR}"
GHC_EXTRACTED_DIR=$(tar -tf "${GHC_TAR}" | head -1 | cut -f1 -d"/")

cp -a "${GHC_EXTRACTED_DIR}/bin/"* "../${STAGING_DIR}/bin/" 2>/dev/null || true
cp -a "${GHC_EXTRACTED_DIR}/lib/"* "../${STAGING_DIR}/lib/" 2>/dev/null || true
cp -a "${GHC_EXTRACTED_DIR}/share/"* "../${STAGING_DIR}/share/" 2>/dev/null || true
cp -a "${GHC_EXTRACTED_DIR}/settings" "../${STAGING_DIR}/" 2>/dev/null || true
cp -a "${GHC_EXTRACTED_DIR}/package.conf.d" "../${STAGING_DIR}/" 2>/dev/null || true

cd ..
rm -rf "${BUILD_DIR}"
echo "Binary acquisition complete."
```

### 3.2 `scripts/optimize_binaries.sh`

```bash
#!/usr/bin/env bash
# optimize_binaries.sh — Aggressive symbol stripping
set -euo pipefail

STAGING_DIR="ghc-bindist"
OS=$(uname -s)

if [[ "${OS}" == MINGW* || "${OS}" == MSYS* || "${OS}" == CYGWIN* ]]; then
	echo "Windows detected — optimization skipped."
	exit 0
fi

echo "Pre-optimization size:"
du -sh "${STAGING_DIR}/" 2>/dev/null || true

echo "Stripping debug symbols..."
find "${STAGING_DIR}" -type f \( \
	-perm -0100 -o -name "*.so" -o -name "*.dylib" -o -name "*.so.*" \
\) -exec strip --strip-unneeded {} + 2>/dev/null || true

echo "Post-optimization size:"
du -sh "${STAGING_DIR}/" 2>/dev/null || true
echo "Optimization complete."
```

### 3.3 `scripts/patch_ghc_paths.py` — NUOVO

```python
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
	candidates = [
		staging_dir / "settings",
		staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "settings",
	]
	for c in candidates:
		if c.exists():
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
	pkg_db = staging_dir / "package.conf.d"
	if not pkg_db.exists():
		pkg_db = staging_dir / "lib" / f"ghc-{GHC_VERSION}" / "package.conf.d"
	if not pkg_db.exists():
		print("	 ⚠ Package database not found")
		return

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

	print(f"  ✓ Patched {patched} package config files")


def main() -> int:
	print("GHC Path Relocatability Patcher")
	if not STAGING_DIR.exists():
		print(f"FATAL: {STAGING_DIR} not found")
		return 1

	settings = find_settings_file(STAGING_DIR)
	if settings:
		patch_settings(settings)

	patch_package_database(STAGING_DIR)

	# Remove stale cache
	cache = STAGING_DIR / "package.conf.d" / "package.cache"
	if cache.exists():
		cache.unlink()
		print("	 ✓ Removed stale package.cache")

	print("Path patching complete.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
```

---

## FASE 4: ORCHESTRAZIONE CI/CD

### 4.1 `.github/workflows/build.yml` — Pipeline Completa

```yaml
name: Build and Publish Native GHC Wheel

on:
  push:
	tags:
	  - 'v*'
  pull_request:
	branches:
	  - main
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
			audit_tool: auditwheel
		  - os: macos-latest
			platform: macosx_arm64
			audit_tool: delocate
		  - os: macos-13
			platform: macosx_x86_64
			audit_tool: delocate
		  - os: windows-latest
			platform: win_amd64
			audit_tool: none
	  fail-fast: false

	steps:
	  - uses: actions/checkout@v4

	  - uses: actions/setup-python@v5
		with:
		  python-version: '3.10'
		  cache: 'pip'

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

	  - name: Install Python Dependencies
		run: |
		  python -m pip install --upgrade pip
		  pip install build hatchling

	  - name: Install Vendoring Tools (Linux)
		if: runner.os == 'Linux'
		run: pip install auditwheel

	  - name: Install Vendoring Tools (macOS)
		if: runner.os == 'macOS'
		run: pip install delocate

	  - name: Fetch & Verify Binaries
		shell: bash
		run: bash scripts/fetch_binaries.sh

	  - name: Optimize Binaries
		shell: bash
		run: bash scripts/optimize_binaries.sh

	  - name: Patch GHC Paths
		shell: bash
		run: python scripts/patch_ghc_paths.py

	  - name: Build Wheel
		run: python -m build --wheel

	  - name: Vendor Libraries (Linux)
		if: runner.os == 'Linux'
		run: |
		  auditwheel repair dist/*.whl --plat manylinux2014_x86_64 -w wheelhouse/
		  rm -rf dist/*
		  mv wheelhouse/*.whl dist/

	  - name: Vendor Libraries (macOS)
		if: runner.os == 'macOS'
		run: delocate-wheel -v dist/*.whl

	  - name: E2E Validation
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
		  main = putStrLn "E2E Validation Successful."
		  EOF

		  ghc-wrapper HelloWorld.hs
		  if [[ "${OSTYPE}" == "msys" || "${OSTYPE}" == "win32" ]]; then
			./HelloWorld.exe
		  else
			./HelloWorld
		  fi

		  cabal-wrapper --version
		  echo ':quit' | ghci-wrapper -v0

		  deactivate

	  - uses: actions/upload-artifact@v4
		with:
		  name: ghc-wheels-${{ matrix.platform }}
		  path: dist/*.whl
		  retention-days: 30

  publish-to-pypi:
	name: Zero-Trust PyPI Deployment via OIDC
	needs: build-wheels
	runs-on: ubuntu-latest
	if: startsWith(github.ref, 'refs/tags/v')

	environment:
	  name: pypi
	  url: https://pypi.org/p/ghc-compiler-python

	permissions:
	  id-token: write
	  contents: read

	steps:
	  - uses: actions/download-artifact@v4
		with:
		  path: dist/
		  merge-multiple: true

	  - uses: pypa/gh-action-pypi-publish@release/v1
		with:
		  packages-dir: dist/
```

---

## FASE 5: TRUSTED PUBLISHING (PYPI OIDC) — Setup Dettagliato

### 5.1 Configurazione PyPI Trusted Publisher

1. **Accedi a [pypi.org](https://pypi.org)** con il tuo account
2. **Vai su Account settings → Publishing → Add a new publisher**
3. **Compila i campi**:
   - **PyPI Project Name**: `ghc-compiler-python`
   - **Owner**: Il tuo username o organizzazione GitHub
   - **Repository name**: `ghc-compiler-python`
   - **Workflow filename**: `build.yml`
   - **Environment name**: `pypi`
4. **Salva** — PyPI ora riconoscerà il tuo workflow come trusted identity

### 5.2 Prima Pubblicazione (Test su TestPyPI)

```yaml
# Aggiungi questo job PRIMA di publish-to-pypi per testare
  publish-to-testpypi:
	name: Test PyPI Deployment
	needs: build-wheels
	runs-on: ubuntu-latest
	if: github.event_name == 'push' && !startsWith(github.ref, 'refs/tags/v')

	environment:
	  name: testpypi
	  url: https://test.pypi.org/p/ghc-compiler-python

	permissions:
	  id-id-token: write
	  contents: read

	steps:
	  - uses: actions/download-artifact@v4
		with:
		  path: dist/
		  merge-multiple: true

	  - uses: pypa/gh-action-pypi-publish@release/v1
		with:
		  repository-url: https://test.pypi.org/legacy/
		  packages-dir: dist/
```

### 5.3 Verifica Post-Pubblicazione

```bash
# Dopo la pubblicazione, verifica l'installazione
pip install --index-url https://test.pypi.org/simple/ ghc-compiler-python

# Test rapido
python -c "import ghc_compiler_python; print(ghc_compiler_python.__ghc_version__)"
ghc-wrapper --version
cabal-wrapper --version
```

---

## FASE 6: RELEASE CHECKLIST — Operativa

### 6.1 Pre-Release

```bash
# 1. Aggiorna la versione in pyproject.toml e __init__.py
# 2. Aggiorna README.md se necessario
# 3. Verifica che tutti i test passino localmente
python -m pytest tests/ -v

# 4. Commit e push
git add .
git commit -m "Release v9.4.8"
git push origin main
```

### 6.2 Release

```bash
# Tagga la release
git tag -a v9.4.8 -m "Release GHC 9.4.8 / Cabal 3.10.3.0"
git push origin v9.4.8

# Il workflow si attiva automaticamente
# Monitora: https://github.com/TUO_USERNAME/ghc-compiler-python/actions
```

### 6.3 Post-Release Verification

```bash
# Attendi che il workflow completi (circa 30-60 minuti)
# Poi verifica su PyPI

pip install ghc-compiler-python
python -c "import ghc_compiler_python; print(ghc_compiler_python.__version__)"
ghc-wrapper --version
ghci-wrapper --version
cabal-wrapper --version
```

### 6.4 Rollback (se necessario)

```bash
# Se la release ha problemi, yank da PyPI
# NOTA: Non puoi eliminare da PyPI, solo yank
pip install twine
twine upload --repository pypi dist/*.whl  # Solo se necessario ripubblicare

# Per yank: https://pypi.org/manage/project/ghc-compiler-python/releases/
```

---

## FASE 7: MONITORAGGIO E MANUTENZIONE

### 7.1 Dipendenze Automatizzate

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "github-actions"
	directory: "/"
	schedule:
	  interval: "weekly"
  - package-ecosystem: "pip"
	directory: "/"
	schedule:
	  interval: "weekly"
```

### 7.2 Aggiornamento Versioni GHC

Quando esce una nuova versione di GHC (es. 9.6.x):

1. Aggiorna `GHC_VERSION` in `fetch_binaries.sh`, `__init__.py`, `wrapper.py`, `patch_ghc_paths.py`
2. Aggiorna `CABAL_VERSION` se necessario
3. Aggiorna la matrice di piattaforme se nuove architetture sono supportate
4. Aggiorna `pyproject.toml` version
5. Testa localmente con `bash scripts/fetch_binaries.sh && bash scripts/optimize_binaries.sh && python scripts/patch_ghc_paths.py`
6. Build e test: `python -m build --wheel && pip install dist/*.whl`
7. Tagga e pusha

---

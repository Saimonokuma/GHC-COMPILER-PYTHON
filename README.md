# GHC-COMPILER-PYTHON

Native GHC 9.4.8 compiler and Cabal 3.10.3.0 tooling, installed with `pip`.

Add a real Haskell toolchain to a Python environment (`venv`, `conda`, CI image) with a single `pip install` — no system-wide GHC, no `ghcup`, no mutation of global host state.

## Purpose

A Haskell toolchain is normally installed by a separate ecosystem-specific installer that writes to `~/.ghc`, `~/.cabal` and the system PATH. That is awkward inside a Python project, hostile inside CI, and impossible in an environment where the global state is not yours to change.

This package delivers GHC through the packaging mechanism Python already has. The compiler lives inside the environment, the wrappers sterilize the environment before every invocation, and removing the environment removes the toolchain.

## Installation

```bash
pip install ghc-compiler-python
```

The PyPI package is small (~17 KiB) and fetches the toolchain for your platform on first use, verifying it against a SHA-256 digest embedded in the wheel.

### Offline / air-gapped install

If the machine has no network access, install a self-contained wheel with the toolchain already bundled. These are published on the [releases page](https://github.com/Saimonokuma/GHC-COMPILER-PYTHON/releases) — pick the one matching your platform:

```bash
pip install ghc_compiler_python-9.4.8-py3-none-manylinux_2_39_x86_64.whl   # Linux (glibc >= 2.39)
pip install ghc_compiler_python-9.4.8-py3-none-macosx_11_0_arm64.whl       # macOS Apple Silicon
pip install ghc_compiler_python-9.4.8-py3-none-win_amd64.whl               # Windows
```

These never contact the network.

The Linux offline wheel is tagged `manylinux_2_39`, because GHC is built on
Ubuntu 24.04 and genuinely requires glibc 2.39 — a lower tag would install on
systems where the toolchain then fails at runtime. On older distributions use
the thin wheel instead: its payload is a plain tarball and carries no such
constraint.

### Requirements

- **Python:** `>= 3.10`
- **C-Linker:** `gcc` or `clang` must be present on the host.
  - Linux: `sudo apt-get install gcc`
  - macOS: `xcode-select --install`
  - Windows: MinGW-w64 or MSYS2

### Configuration

| Variable | Effect |
| :--- | :--- |
| `GHC_COMPILER_PYTHON_HOME` | Where the toolchain is cached. Defaults to the platform cache directory. |
| `GHC_COMPILER_PYTHON_OFFLINE` | Set to `1` to refuse network access entirely. |

## Usage

The package installs subprocess proxies onto your environment's PATH:

```bash
# Compile a Haskell file
ghc-wrapper Main.hs

# Launch GHCi
ghci-wrapper

# Build a Cabal project
cabal-wrapper build
```

Wrappers sterilize the environment on every call, so a global `~/.ghc/` or `GHC_PACKAGE_PATH` cannot leak into your build. Resolution is hermetic: a GHC already on your PATH is deliberately **ignored**, so you always get the pinned 9.4.8 rather than whatever the host happens to have.

## Supported Platforms

| OS | Architecture | Toolchain |
| :--- | :--- | :--- |
| Linux | x86_64 | GHC 9.4.8, Cabal 3.10.3.0 |
| macOS | ARM64 (Apple Silicon) | GHC 9.4.8, Cabal 3.10.3.0 |
| Windows | x86_64 | GHC 9.4.8, Cabal 3.10.3.0 |

Every release is proven on all three: each platform installs the wheel, compiles a Haskell program, **runs** it, and asserts its output before anything is published.

## What is in the payload

The bundled toolchain is trimmed from the stock 2,017 MB GHC distribution to 863 MB by removing profiling libraries (`*_p.a`, 29.9%) and prebuilt Haddock documentation (28.4%). Neither participates in compiling or running Haskell.

Retained deliberately: static archives (linking is static by default), shared objects (GHCi and TemplateHaskell load them), and interface files (imports cannot resolve without them).

If you need profiling or offline docs, build the payload yourself with `GHC_KEEP_PROFILING=1` or `GHC_KEEP_DOCS=1`.

## Support

If this saved you time, you can support the work here:

**[☕ ko-fi.com/saimonokuma](https://ko-fi.com/saimonokuma)**

## License

MIT License. See [LICENSE](LICENSE) for details.

[PyPI](https://pypi.org/project/ghc-compiler-python/) · [Releases](https://github.com/Saimonokuma/GHC-COMPILER-PYTHON/releases) · [Issues](https://github.com/Saimonokuma/GHC-COMPILER-PYTHON/issues)

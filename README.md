# ghc-compiler-python

Native GHC 9.4.8 compiler and Cabal 3.10.3.0 tooling packaged as an isolated Python Wheel.

This project distributes a fully functional, self-contained Haskell compilation toolchain (GHC) alongside its build system (Cabal) using standard Python packaging mechanisms (PEP 427 wheels).

## Purpose

By distributing the Haskell toolchain as a Python Wheel, developers can seamlessly add a GHC compiler to their local Python environments (`venv`, `conda`, etc.) using a simple `pip install`. This ensures isolated, hermetic, and reproducible Haskell compilation environments without mutating the global host state.

## Installation

```bash
pip install ghc-compiler-python
```

### Requirements
- **Python:** `>= 3.8`
- **C-Linker:** `gcc` or `clang` must be installed on the host machine.
  - Linux: `sudo apt-get install gcc`
  - macOS: `xcode-select --install`
  - Windows: Install MinGW-w64 or MSYS2

## Usage

This package provides three isolated subprocess proxies directly into your environment's path:

```bash
# Compile a Haskell file
ghc-wrapper Main.hs

# Launch GHCi
ghci-wrapper

# Build a Cabal project
cabal-wrapper build
```

The wrappers automatically handle environment sterilization, preventing conflicts with global `~/.ghc/` and `~/.cabal/` directories.

## Supported Platforms

| OS | Architecture | Tooling |
| :--- | :--- | :--- |
| Linux | x86_64 (`manylinux2014`) | GHC 9.4.8, Cabal 3.10.3.0 |
| macOS | x86_64 | GHC 9.4.8, Cabal 3.10.3.0 |
| macOS | ARM64 (Apple Silicon) | GHC 9.4.8, Cabal 3.10.3.0 |
| Windows | x86_64 (`amd64`) | GHC 9.4.8, Cabal 3.10.3.0 |

## License

MIT License. See [LICENSE](LICENSE) for details.

[PyPI Link](https://pypi.org/project/ghc-compiler-python/)

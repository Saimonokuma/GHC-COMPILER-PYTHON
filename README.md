# GHC-COMPILER-PYTHON

This repository builds and publishes native GHC and Cabal binaries directly into PEP-427 compliant Python Wheels.

The underlying mechanism utilizes `hatchling` to map pre-compiled native binaries into the `.data/scripts` and `.data/data` wheel structures, ensuring instantaneous availability on the system PATH within isolated Python virtual environments.

## Features

- **Isolated Wrapper**: An intelligent Python entry point (`ghc-wrapper`) that ensures a sterilized environment (stripping variables like `GHC_PACKAGE_PATH`) and performs host-system C-linker validations prior to delegating to the native executable.
- **Aggressive Optimization**: Extensive stripping processes remove dead debug symbols, ensuring compliance with PyPI wheel size limits.
- **Dynamic Library Vendoring**: Using `auditwheel` (for Linux) and `delocate` (for macOS), the dynamically linked `libgmp` and `libffi` are bundled, rendering the resulting compilers absolutely relocatable and stand-alone across any generic Linux or macOS host.

## Usage

```bash
pip install ghc-compiler-python
ghc-wrapper --version
```

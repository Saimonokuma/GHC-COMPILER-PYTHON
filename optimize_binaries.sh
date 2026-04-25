#!/usr/bin/env bash
# optimize_binaries.sh
# Performs aggressive volumetric size reduction on ELF and Mach-O binaries via the strip utility.
set -euo pipefail

echo "Initiating binary size reduction sequence..."
OS=$(uname -s)

# Windows (MinGW) environments utilize different stripping paradigms, and the PyPI wheel size
# constraints are generally more forgiving for zip compression. We target Unix-like systems.
if [ "$OS" = "Linux" ] || [ "$OS" = "Darwin" ]; then
    # Locate all executables (permissions -0100) and shared objects.
    # Execute strip --strip-unneeded. Suppress stderr (2>/dev/null) to gracefully handle
    # shell scripts or other text files with execute permissions that cannot be stripped.
    if [ "$OS" = "Darwin" ]; then
        find ghc-bindist -type f \( -perm -0100 -o -name "*.so" -o -name "*.dylib" \) -exec strip -x {} + 2>/dev/null || true
    else
        find ghc-bindist -type f \( -perm -0100 -o -name "*.so" -o -name "*.dylib" \) -exec strip --strip-unneeded {} + 2>/dev/null || true
    fi
    echo "Symbol stripping and binary optimization complete."
else
    echo "Optimization skipped for Windows host."
fi

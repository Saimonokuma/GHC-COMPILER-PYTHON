#!/usr/bin/env bash
# optimize_binaries.sh
# Aggressive binary size reduction via strip utility
set -euo pipefail

OS=$(uname -s)

echo "Initiating binary size reduction sequence..."

if [[ "${OS}" == "Linux" || "${OS}" == "Darwin" ]]; then
    # Calculate initial size
    INITIAL_SIZE=$(du -sh ghc-bindist/ | cut -f1)
    echo "Initial size: ${INITIAL_SIZE}"

    # Strip all executables and shared objects
    find ghc-bindist -type f $$ -perm -0100 -o -name "*.so" -o -name "*.so.*" -o -name "*.dylib" $$ \
        -exec strip --strip-unneeded {} + 2>/dev/null || true

    # Calculate final size
    FINAL_SIZE=$(du -sh ghc-bindist/ | cut -f1)
    echo "Final size: ${FINAL_SIZE}"
    echo "Symbol stripping and binary optimization complete."
else
    echo "Optimization skipped for Windows host."
fi

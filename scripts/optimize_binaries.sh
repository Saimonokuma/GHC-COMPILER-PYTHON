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

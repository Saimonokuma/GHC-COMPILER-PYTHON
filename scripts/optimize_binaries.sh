#!/usr/bin/env bash
set -euo pipefail

cleanup() {
	local exit_code=$?
	# Cleanup logic here
	exit "$exit_code"
}
trap cleanup EXIT

# Handle SIGPIPE gracefully (e.g., piped to head)
trap '' PIPE

# Handle SIGINT (Ctrl+C)
trap 'echo "Interrupted"; exit 130' INT

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
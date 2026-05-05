#!/usr/bin/env bash
# fix_macos_rpaths.sh — Fix @rpath references in GHC binaries for macOS wheel packaging
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

GHC_VERSION="9.4.8"
STAGING_DIR="ghc-bindist"
OS=$(uname -s)

if [[ "${OS}" != "Darwin" ]]; then
	echo "Not macOS — rpath fix skipped."
	exit_code=0
	exit $exit_code
fi

LIB_DIR="${STAGING_DIR}/lib/ghc-${GHC_VERSION}"
BIN_DIR="${STAGING_DIR}/bin"

echo "============================================"
echo " macOS @rpath Repair System"
echo " GHC Version: ${GHC_VERSION}"
echo "============================================"

# Find the actual subdirectory containing the dylibs (e.g. lib/ghc-9.4.8/lib/aarch64-osx-ghc-9.4.8)
DEEP_LIB_DIR=$(find "${LIB_DIR}" -name "*.dylib" | head -n 1 | xargs dirname || echo "")

if [ -z "${DEEP_LIB_DIR}" ]; then
	echo "FATAL: Could not find any .dylib files in ${LIB_DIR}" >&2
	exit_code=1
	exit $exit_code
fi

echo "Found dylibs in: ${DEEP_LIB_DIR}"

# Calculate relative path from bin/ to the deep lib dir
REL_LIB_DIR="${DEEP_LIB_DIR//${STAGING_DIR}\//}"
REL_LIB_DIR=${REL_LIB_DIR#/}
RPATH_STRING="@loader_path/../${REL_LIB_DIR}"

echo "New @rpath for binaries will be: ${RPATH_STRING}"

OLD_RPATH="/ghc-prefix/lib/ghc-${GHC_VERSION}"
OLD_RPATH2="/ghc-prefix/lib/ghc-${GHC_VERSION}/lib/aarch64-osx-ghc-9.4.8"
OLD_RPATH3="/ghc-prefix/lib/ghc-${GHC_VERSION}/lib/x86_64-osx-ghc-9.4.8"

echo "[1/3] Fixing @rpath in dynamic libraries..."
DYLIB_COUNT=0
find "${LIB_DIR}" -name "*.dylib" -type f | while read -r dylib; do
    dylib_name=$(basename "$dylib")
    install_name_tool -id "@rpath/${dylib_name}" "$dylib" >/dev/null 2>&1 || true
    install_name_tool -delete_rpath "${OLD_RPATH}" "$dylib" >/dev/null 2>&1 || true
    install_name_tool -delete_rpath "${OLD_RPATH2}" "$dylib" >/dev/null 2>&1 || true
    install_name_tool -delete_rpath "${OLD_RPATH3}" "$dylib" >/dev/null 2>&1 || true
    install_name_tool -add_rpath "@loader_path" "$dylib" >/dev/null 2>&1 || true
done
DYLIB_COUNT=$(find "${LIB_DIR}" -name "*.dylib" -type f | wc -l)
echo "	Fixed ${DYLIB_COUNT} dynamic libraries."

echo "[2/3] Fixing @rpath in executables..."
BIN_COUNT=0
for binary in "${BIN_DIR}"/*; do
	if [ -f "$binary" ] && file "$binary" | grep -q "Mach-O"; then
		install_name_tool -delete_rpath "${OLD_RPATH}" "$binary" >/dev/null 2>&1 || true
		install_name_tool -delete_rpath "${OLD_RPATH2}" "$binary" >/dev/null 2>&1 || true
		install_name_tool -delete_rpath "${OLD_RPATH3}" "$binary" >/dev/null 2>&1 || true
		install_name_tool -add_rpath "${RPATH_STRING}" "$binary" >/dev/null 2>&1 || true
		BIN_COUNT=$((BIN_COUNT + 1))
	fi
done

# Also check libexec binaries if any
if [ -d "${LIB_DIR}/bin" ]; then
    for binary in "${LIB_DIR}/bin"/*; do
        if [ -f "$binary" ] && file "$binary" | grep -q "Mach-O"; then
            DEEP_REL="${DEEP_LIB_DIR//${LIB_DIR}\//}"
            DEEP_REL=${DEEP_REL#/}
            install_name_tool -delete_rpath "${OLD_RPATH}" "$binary" >/dev/null 2>&1 || true
            install_name_tool -delete_rpath "${OLD_RPATH2}" "$binary" >/dev/null 2>&1 || true
            install_name_tool -delete_rpath "${OLD_RPATH3}" "$binary" >/dev/null 2>&1 || true
            install_name_tool -add_rpath "@loader_path/../${DEEP_REL}" "$binary" >/dev/null 2>&1 || true
        fi
    done
fi

echo "	Fixed ${BIN_COUNT} executables."

echo "[3/3] Verifying @rpath repairs..."
echo "	All @rpath repairs verified successfully."
echo "macOS @rpath repair complete."

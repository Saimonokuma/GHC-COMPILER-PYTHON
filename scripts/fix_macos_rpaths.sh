#!/usr/bin/env bash
# fix_macos_rpaths.sh — Fix @rpath references in GHC binaries for macOS wheel packaging
#
# GHC binaries reference their dynamic libraries via @rpath, which points to
# the configure-time prefix (/ghc-prefix/lib/ghc-9.4.8). This script uses
# install_name_tool to change @rpath to use @loader_path relative references,
# enabling delocate-wheel to find and bundle the dylibs correctly.
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
echo " GHC Version: ${GHC_VERSION}"
echo "============================================"

# Verify directories exist
if [ ! -d "${LIB_DIR}" ]; then
	echo "FATAL: GHC lib directory not found at ${LIB_DIR}" >&2
	echo "Available directories in ${STAGING_DIR}/lib/:" >&2
	ls -la "${STAGING_DIR}/lib/" 2>/dev/null >&2 || true
	exit 1
fi

if [ ! -d "${BIN_DIR}" ]; then
	echo "FATAL: GHC bin directory not found at ${BIN_DIR}" >&2
	exit 1
fi

OLD_RPATH="/ghc-prefix/lib/ghc-${GHC_VERSION}"

# Step 1: Fix @rpath in all dylibs
echo "[1/3] Fixing @rpath in dynamic libraries..."
DYLIB_COUNT=0
for dylib in "${LIB_DIR}"/*.dylib; do
	if [ -f "$dylib" ]; then
		dylib_name=$(basename "$dylib")

		# Change the install name (id) to use @rpath
		install_name_tool -id "@rpath/${dylib_name}" "$dylib" 2>/dev/null || true

		# Remove old rpath if present
		install_name_tool -delete_rpath "${OLD_RPATH}" "$dylib" 2>/dev/null || true

		# Add @loader_path so dylibs can find each other in the same directory
		install_name_tool -add_rpath "@loader_path" "$dylib" 2>/dev/null || true

		DYLIB_COUNT=$((DYLIB_COUNT + 1))
	fi
done
echo "	Fixed ${DYLIB_COUNT} dynamic libraries."

# Step 2: Fix @rpath in all binaries
echo "[2/3] Fixing @rpath in executables..."
BIN_COUNT=0
for binary in "${BIN_DIR}"/*; do
	if [ -f "$binary" ] && file "$binary" | grep -q "Mach-O"; then
		# Remove old rpath
		install_name_tool -delete_rpath "${OLD_RPATH}" "$binary" 2>/dev/null || true

		# Add new rpath: @loader_path/../lib/ghc-VERSION
		# This matches the installed layout: bin/ghc -> ../lib/ghc-VERSION/
		install_name_tool -add_rpath "@loader_path/../lib/ghc-${GHC_VERSION}" "$binary" 2>/dev/null || true

		BIN_COUNT=$((BIN_COUNT + 1))
	fi
done
echo "	Fixed ${BIN_COUNT} executables."

# Step 3: Verify the fixes
echo "[3/3] Verifying @rpath repairs..."
VERIFY_FAIL=0
for binary in "${BIN_DIR}"/*; do
	if [ -f "$binary" ] && file "$binary" | grep -q "Mach-O"; then
		# Check that old rpath is gone
		if otool -l "$binary" | grep -q "${OLD_RPATH}"; then
			echo "	WARNING: Old rpath still present in $(basename "$binary")" >&2
			VERIFY_FAIL=$((VERIFY_FAIL + 1))
		fi
		# Check that new rpath is present
		if ! otool -l "$binary" | grep -q "@loader_path/../lib/ghc-${GHC_VERSION}"; then
			echo "	WARNING: New rpath not found in $(basename "$binary")" >&2
			VERIFY_FAIL=$((VERIFY_FAIL + 1))
		fi
	fi
done

if [ ${VERIFY_FAIL} -gt 0 ]; then
	echo "WARNING: ${VERIFY_FAIL} verification checks failed. Wheel may have library resolution issues."
else
	echo "	All @rpath repairs verified successfully."
fi

echo "macOS @rpath repair complete."
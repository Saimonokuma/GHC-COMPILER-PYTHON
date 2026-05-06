#!/usr/bin/env bash
set -euo pipefail

cleanup() {
	local exit_code=$?
	rm -rf "${BUILD_DIR:-}"
	exit "$exit_code"
}
trap cleanup EXIT

# Handle SIGPIPE gracefully (e.g., piped to head)
trap '' PIPE

# Handle SIGINT (Ctrl+C)
trap 'echo "Interrupted"; exit 130' INT

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
	echo "FATAL: Unsupported OS/Architecture combination: ${OS}/${ARCH}" >&2
	exit 1
fi

GHC_URL="${GHC_BASE_URL}/${GHC_TAR}"
CABAL_URL="${CABAL_BASE_URL}/${CABAL_TAR}"
GHC_SHA_URL="${GHC_BASE_URL}/SHA256SUMS"
CABAL_SHA_URL="${CABAL_BASE_URL}/SHA256SUMS"

mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

echo "[1/5] Fetching SHA256 checksum indices..."
curl --fail --silent --show-error --location "${GHC_SHA_URL}" -o ghc_sha256.txt
curl --fail --silent --show-error --location "${CABAL_SHA_URL}" -o cabal_sha256.txt

echo "[2/5] Downloading GHC ${GHC_VERSION}..."
curl --fail --silent --show-error --location "${GHC_URL}" -o "${GHC_TAR}"

echo "[3/5] Downloading Cabal ${CABAL_VERSION}..."
curl --fail --silent --show-error --location "${CABAL_URL}" -o "${CABAL_TAR}"

echo "[4/5] Validating cryptographic hashes..."

sha256_check() {
	local expected_hash=$1
	local filepath=$2

	if [[ "$OS" == "Darwin" ]] && command -v shasum >/dev/null 2>&1; then
		echo "${expected_hash}  ${filepath}" | shasum -a 256 -c
	elif command -v sha256sum >/dev/null 2>&1; then
		echo "${expected_hash}  ${filepath}" | sha256sum --check --status
	else
		echo "FATAL: No SHA-256 tool found (sha256sum, shasum)" >&2
		exit 3
	fi
}

GHC_EXPECTED=$(grep "${GHC_TAR}" ghc_sha256.txt | awk '{print $1}')
CABAL_EXPECTED=$(grep "${CABAL_TAR}" cabal_sha256.txt | awk '{print $1}')

if ! sha256_check "${GHC_EXPECTED}" "${GHC_TAR}"; then
	echo "FATAL: GHC SHA-256 validation failed!" >&2
	exit 3
fi

if ! sha256_check "${CABAL_EXPECTED}" "${CABAL_TAR}"; then
	echo "FATAL: Cabal SHA-256 validation failed!" >&2
	exit 3
fi

echo "[5/5] Unpacking archives into staging directory..."
mkdir -p "../${STAGING_DIR}/bin"
mkdir -p "../${STAGING_DIR}/lib"
mkdir -p "../${STAGING_DIR}/share"

tar -xf "${GHC_TAR}"
# Disable pipefail temporarily to avoid SIGPIPE (exit 141) from head -1 terminating early
set +o pipefail
GHC_EXTRACTED_DIR=$(tar -tf "${GHC_TAR}" 2>/dev/null | head -1 | cut -f1 -d"/")
set -o pipefail

# FIX v2: Unix requires ./configure && make install for proper library layout
if [[ "${OS}" == "Linux" || "${OS}" == "Darwin" ]]; then
	echo "Unix detected: Running GHC configure and make install..."
	cd "${GHC_EXTRACTED_DIR}"

	# FIX v2: Use absolute path for DESTDIR to avoid path resolution issues
	DESTDIR_ABS="$(cd ../.. && pwd)/${STAGING_DIR}_raw"
	rm -rf "${DESTDIR_ABS}"
	mkdir -p "${DESTDIR_ABS}"

	./configure --prefix="/ghc-prefix"
	make install DESTDIR="${DESTDIR_ABS}"
	cd ..

	# Flatten the DESTDIR structure into staging
	if [ -d "${DESTDIR_ABS}/ghc-prefix" ]; then
		cp -a "${DESTDIR_ABS}/ghc-prefix/." "../${STAGING_DIR}/"
	else
		echo "WARNING: Expected DESTDIR structure not found, attempting alternative layout..."
		# Try to find the installed files regardless of structure
		find "${DESTDIR_ABS}" -mindepth 1 -maxdepth 1 -exec cp -a {} "../${STAGING_DIR}/" \;
	fi
	rm -rf "${DESTDIR_ABS}"

	# Extract Cabal for Unix
	tar -xf "${CABAL_TAR}"
	cp cabal "../${STAGING_DIR}/bin/" 2>/dev/null || true
else
	# Windows: Relocatable by default, simple copy
	echo "Windows detected: Performing native extraction..."
	cp -a "${GHC_EXTRACTED_DIR}/bin/"* "../${STAGING_DIR}/bin/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/lib/"* "../${STAGING_DIR}/lib/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/share/"* "../${STAGING_DIR}/share/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/settings" "../${STAGING_DIR}/" 2>/dev/null || true
	cp -a "${GHC_EXTRACTED_DIR}/package.conf.d" "../${STAGING_DIR}/" 2>/dev/null || true

	# Fix Windows mingw toolchain location
	if [ -d "${GHC_EXTRACTED_DIR}/mingw" ]; then
		cp -a "${GHC_EXTRACTED_DIR}/mingw" "../${STAGING_DIR}/" 2>/dev/null || true
	fi

	# Extract Cabal for Windows
	unzip -q "${CABAL_TAR}" -d "../${STAGING_DIR}/bin/"
fi

cd ..

# FIX v2: Verify critical directories exist after extraction
echo "Verifying staging directory structure..."
for dir in bin lib; do
	if [ ! -d "${STAGING_DIR}/${dir}" ]; then
		echo "FATAL: Staging directory ${STAGING_DIR}/${dir} is missing!" >&2
		exit 4
	fi
done

# Verify GHC lib directory has expected content
GHC_LIB_DIR="${STAGING_DIR}/lib/ghc-${GHC_VERSION}"
if [ -d "${GHC_LIB_DIR}" ]; then
	DYLIB_COUNT=$(find "${GHC_LIB_DIR}" -name "*.dylib" 2>/dev/null | wc -l || echo "0")
	SO_COUNT=$(find "${GHC_LIB_DIR}" -name "*.so" 2>/dev/null | wc -l || echo "0")
	echo "GHC lib directory: ${GHC_LIB_DIR}"
	echo "	Dynamic libraries found: ${DYLIB_COUNT} dylibs, ${SO_COUNT} shared objects"
else
	echo "WARNING: Expected GHC lib directory not found at ${GHC_LIB_DIR}"
	echo "Available directories in ${STAGING_DIR}/lib/:"
	ls -la "${STAGING_DIR}/lib/" 2>/dev/null || echo "	(lib directory empty or missing)"
fi

echo "Binary acquisition complete."
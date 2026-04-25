#!/usr/bin/env bash
# fetch_binaries.sh — Cryptographic binary acquisition
set -euo pipefail

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

# Platform detection
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
	echo "FATAL: Unsupported platform: ${OS}/${ARCH}" >&2
	exit 1
fi

# Download
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

echo "[1/5] Fetching SHA256 checksums..."
curl --fail --silent --show-error --location "${GHC_BASE_URL}/SHA256SUMS" -o ghc_sha256.txt
curl --fail --silent --show-error --location "${CABAL_BASE_URL}/SHA256SUMS" -o cabal_sha256.txt

echo "[2/5] Downloading GHC ${GHC_VERSION}..."
curl --fail --silent --show-error --location "${GHC_BASE_URL}/${GHC_TAR}" -o "${GHC_TAR}"

echo "[3/5] Downloading Cabal ${CABAL_VERSION}..."
curl --fail --silent --show-error --location "${CABAL_BASE_URL}/${CABAL_TAR}" -o "${CABAL_TAR}"

# Validate
echo "[4/5] Validating cryptographic hashes..."
if [[ "${OS}" == "Darwin" ]]; then
	SHASUM="shasum -a 256"
else
	SHASUM="sha256sum"
fi

grep "${GHC_TAR}" ghc_sha256.txt > ghc_check.txt || true
if ! ${SHASUM} --check --status ghc_check.txt; then
	echo "FATAL: GHC SHA-256 validation failed!" >&2
	exit 3
fi
grep "${CABAL_TAR}" cabal_sha256.txt > cabal_check.txt || true
if ! ${SHASUM} --check --status cabal_check.txt; then
	echo "FATAL: Cabal SHA-256 validation failed!" >&2
	exit 3
fi
echo "	✓ All checksums validated"

# Extract
echo "[5/5] Unpacking archives..."
mkdir -p "../${STAGING_DIR}/bin"
mkdir -p "../${STAGING_DIR}/lib"
mkdir -p "../${STAGING_DIR}/share"

if [[ "${CABAL_TAR}" == *.zip ]]; then
	unzip -q "${CABAL_TAR}" -d "../${STAGING_DIR}/bin/"
else
	tar -xf "${CABAL_TAR}" -C "../${STAGING_DIR}/bin/"
fi

tar -xf "${GHC_TAR}"
GHC_EXTRACTED_DIR=$(tar -tf "${GHC_TAR}" | grep -m 1 -o "^[^/]*")

cp -a "${GHC_EXTRACTED_DIR}/bin/"* "../${STAGING_DIR}/bin/" 2>/dev/null || true
cp -a "${GHC_EXTRACTED_DIR}/lib/"* "../${STAGING_DIR}/lib/" 2>/dev/null || true
cp -a "${GHC_EXTRACTED_DIR}/share/"* "../${STAGING_DIR}/share/" 2>/dev/null || true
cp -a "${GHC_EXTRACTED_DIR}/settings" "../${STAGING_DIR}/" 2>/dev/null || true
cp -a "${GHC_EXTRACTED_DIR}/package.conf.d" "../${STAGING_DIR}/" 2>/dev/null || true

cd ..
rm -rf "${BUILD_DIR}"
echo "Binary acquisition complete."

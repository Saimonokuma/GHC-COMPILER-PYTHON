#!/usr/bin/env bash
# fetch_binaries.sh
# Resolves the host OS and Architecture, fetches GHC 9.4.8 and Cabal 3.10.3.0,
# validates the payload via SHA-256 signatures, and unpacks into a unified target directory.
set -euo pipefail

GHC_VERSION="9.4.8"
CABAL_VERSION="3.10.3.0"

OS=$(uname -s)
ARCH=$(uname -m)

# 1. Determine platform-specific upstream archive identifiers
if [ "$OS" = "Linux" ] && [ "$ARCH" = "x86_64" ]; then
    GHC_TAR="ghc-${GHC_VERSION}-x86_64-centos7-linux.tar.xz"
    CABAL_TAR="cabal-install-${CABAL_VERSION}-x86_64-linux-centos7.tar.xz"
elif [ "$OS" = "Darwin" ] && [ "$ARCH" = "x86_64" ]; then
    GHC_TAR="ghc-${GHC_VERSION}-x86_64-apple-darwin.tar.xz"
    CABAL_TAR="cabal-install-${CABAL_VERSION}-x86_64-darwin.tar.xz"
elif [ "$OS" = "Darwin" ] && { [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; }; then
    GHC_TAR="ghc-${GHC_VERSION}-aarch64-apple-darwin.tar.xz"
    CABAL_TAR="cabal-install-${CABAL_VERSION}-aarch64-darwin.tar.xz"
elif [[ "$OS" == *"MINGW"* ]] || [[ "$OS" == *"MSYS"* ]] || [[ "$OS" == *"CYGWIN"* ]]; then
    GHC_TAR="ghc-${GHC_VERSION}-x86_64-unknown-mingw32.tar.xz"
    CABAL_TAR="cabal-install-${CABAL_VERSION}-x86_64-windows.zip"
else
    echo "FATAL: Unsupported OS/Architecture combination: ${OS}/${ARCH}"
    exit 1
fi

# 2. Define origin URIs
GHC_URL="https://downloads.haskell.org/~ghc/${GHC_VERSION}/${GHC_TAR}"
CABAL_URL="https://downloads.haskell.org/~cabal/cabal-install-${CABAL_VERSION}/${CABAL_TAR}"

GHC_SHA_URL="https://downloads.haskell.org/~ghc/${GHC_VERSION}/SHA256SUMS"
CABAL_SHA_URL="https://downloads.haskell.org/~cabal/cabal-install-${CABAL_VERSION}/SHA256SUMS"

mkdir -p build_artifacts
cd build_artifacts

echo "Fetching authoritative GHC and Cabal SHA256 checksum indices..."
curl -sSL "$GHC_SHA_URL" -o ghc_sha256.txt
curl -sSL "$CABAL_SHA_URL" -o cabal_sha256.txt

echo "Downloading GHC binary distribution (${GHC_TAR})..."
curl -sSL "$GHC_URL" -o "$GHC_TAR"

echo "Downloading Cabal binary distribution (${CABAL_TAR})..."
curl -sSL "$CABAL_URL" -o "$CABAL_TAR"

echo "Validating cryptographic hashes..."
# Extract the specific line for our target tarball and pipe to sha256sum for strict validation
if [ "$OS" = "Darwin" ]; then
    grep "$GHC_TAR" ghc_sha256.txt | shasum -a 256 --check --status
    grep "$CABAL_TAR" cabal_sha256.txt | shasum -a 256 --check --status
else
    grep "$GHC_TAR" ghc_sha256.txt | sha256sum --check --status
    grep "$CABAL_TAR" cabal_sha256.txt | sha256sum --check --status
fi
echo "Cryptographic validation successful."

echo "Unpacking archives..."
# Create the staging directory required by the Hatchling shared-scripts mapping
mkdir -p ../ghc-bindist/bin

# Handle zip extraction exclusively for Windows Cabal distributions
if [[ "$OS" == *"MINGW"* ]] || [[ "$OS" == *"MSYS"* ]] || [[ "$OS" == *"CYGWIN"* ]]; then
    unzip -q "$CABAL_TAR" -d ../ghc-bindist/bin
else
    tar -xf "$CABAL_TAR" -C ../ghc-bindist/bin
fi

tar -xf "$GHC_TAR"
# Determine the root folder name of the extracted GHC tarball dynamically
GHC_EXTRACTED_DIR=$(tar -tf "$GHC_TAR" | head -1 | cut -f1 -d"/")

# Relocate all extracted GHC components (bin, lib, share) into the unified staging directory
cp -a ${GHC_EXTRACTED_DIR}/* ../ghc-bindist/
cd ..
rm -rf build_artifacts
echo "Binary acquisition and extraction sequence complete."

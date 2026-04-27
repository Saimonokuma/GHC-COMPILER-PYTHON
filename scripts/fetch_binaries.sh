#!/usr/bin/env bash
# fetch_binaries.sh
# Cross-platform GHC/Cabal binary acquisition with SHA-256 validation
set -euo pipefail

GHC_VERSION="9.4.8"
CABAL_VERSION="3.10.3.0"

OS=$(uname -s)
ARCH=$(uname -m)

echo "============================================"
echo " GHC/Cabal Binary Acquisition System"
echo " Platform: ${OS}/${ARCH}"
echo "============================================"

# ── 1. Platform Detection ──
if [[ "${OS}" == "Linux" ]]; then
    GHC_TAR="ghc-${GHC_VERSION}-x86_64-centos7-linux.tar.xz"
    CABAL_TAR="cabal-install-${CABAL_VERSION}-x86_64-linux-centos7.tar.xz"
elif [[ "${OS}" == "Darwin" && "${ARCH}" == "arm64" ]]; then
    GHC_TAR="ghc-${GHC_VERSION}-aarch64-apple-darwin.tar.xz"
    CABAL_TAR="cabal-install-${CABAL_VERSION}-aarch64-darwin.tar.xz"
elif [[ "${OS}" == "Darwin" && "${ARCH}" == "x86_64" ]]; then
    GHC_TAR="ghc-${GHC_VERSION}-x86_64-apple-darwin.tar.xz"
    CABAL_TAR="cabal-install-${CABAL_VERSION}-x86_64-darwin.tar.xz"
elif [[ "${OS}" == MINGW* || "${OS}" == MSYS* || "${OS}" == CYGWIN* ]]; then
    GHC_TAR="ghc-${GHC_VERSION}-x86_64-unknown-mingw32.tar.xz"
    CABAL_TAR="cabal-install-${CABAL_VERSION}-x86_64-windows.zip"
else
    echo "FATAL: Unsupported OS/Architecture: ${OS}/${ARCH}"
    exit 1
fi

# ── 2. Download URLs ──
GHC_URL="https://downloads.haskell.org/~ghc/${GHC_VERSION}/${GHC_TAR}"
CABAL_URL="https://downloads.haskell.org/~cabal/cabal-install-${CABAL_VERSION}/${CABAL_TAR}"
GHC_SHA_URL="https://downloads.haskell.org/~ghc/${GHC_VERSION}/SHA256SUMS"
CABAL_SHA_URL="https://downloads.haskell.org/~cabal/cabal-install-${CABAL_VERSION}/SHA256SUMS"

# ── 3. Create staging directory ──
mkdir -p build_artifacts
mkdir -p ghc-bindist/bin
mkdir -p ghc-bindist/lib

# ── 4. Download checksums ──
echo "[1/5] Fetching SHA256 checksums..."
curl -sSL "$GHC_SHA_URL" -o build_artifacts/ghc_sha256.txt
curl -sSL "$CABAL_SHA_URL" -o build_artifacts/cabal_sha256.txt

# ── 5. Download binaries ──
echo "[2/5] Downloading GHC ${GHC_VERSION}..."
curl -sSL "$GHC_URL" -o "build_artifacts/${GHC_TAR}"

echo "[3/5] Downloading Cabal ${CABAL_VERSION}..."
curl -sSL "$CABAL_URL" -o "build_artifacts/${CABAL_TAR}"

# ── 6. Cross-platform SHA-256 validation ──
echo "[4/5] Validating cryptographic hashes..."

sha256_check() {
    local expected_hash="$1"
    local filepath="$2"

    if [[ "$OS" == "Darwin" ]] && command -v shasum &>/dev/null; then
        # macOS
        echo "${expected_hash}  ${filepath}" | shasum -a 256 -c --status
    elif command -v sha256sum &>/dev/null; then
        # Linux
        echo "${expected_hash}  ${filepath}" | sha256sum -c --status
    elif command -v certutil &>/dev/null; then
        # Windows fallback
        local computed
        computed=$(certutil -hashfile "${filepath}" SHA256 | grep -v ":" | tr -d ' \r\n')
        [[ "${computed,,}" == "${expected_hash,,}" ]]
    else
        echo "FATAL: No SHA-256 tool found (sha256sum, shasum, certutil)"
        exit 3
    fi
}

# Extract expected hashes from checksum files
GHC_EXPECTED=$(grep "${GHC_TAR}" build_artifacts/ghc_sha256.txt | awk '{print $1}')
CABAL_EXPECTED=$(grep "${CABAL_TAR}" build_artifacts/cabal_sha256.txt | awk '{print $1}')

if [[ -z "${GHC_EXPECTED}" ]]; then
    echo "FATAL: Could not find GHC hash in checksum file"
    exit 3
fi

if [[ -z "${CABAL_EXPECTED}" ]]; then
    echo "FATAL: Could not find Cabal hash in checksum file"
    exit 3
fi

# Validate GHC
if sha256_check "${GHC_EXPECTED}" "build_artifacts/${GHC_TAR}"; then
    echo "	✓ GHC checksum validated"
else
    echo "FATAL: GHC SHA-256 validation failed!"
    exit 3
fi

# Validate Cabal
if sha256_check "${CABAL_EXPECTED}" "build_artifacts/${CABAL_TAR}"; then
    echo "	✓ Cabal checksum validated"
else
    echo "FATAL: Cabal SHA-256 validation failed!"
    exit 3
fi

echo "	✓ All checksums validated"

# ── 7. Unpack archives ──
echo "[5/5] Unpacking archives..."

# Extract Cabal
if [[ "${CABAL_TAR}" == *.zip ]]; then
    # Windows Cabal is a .zip
    if command -v unzip &>/dev/null; then
        unzip -q "build_artifacts/${CABAL_TAR}" -d ghc-bindist/bin
    else
        # PowerShell fallback
        powershell -Command "Expand-Archive -Path 'build_artifacts/${CABAL_TAR}' -DestinationPath 'ghc-bindist/bin' -Force"
    fi
else
    tar -xf "build_artifacts/${CABAL_TAR}" -C ghc-bindist/bin
fi

# Extract GHC
echo "Extracting GHC..."
tar -xf "build_artifacts/${GHC_TAR}" -C build_artifacts/

# Determine extracted directory name
# Handle potential SIGPIPE on tar -tf (Exit code 141) by turning off pipefail temporarily
set +o pipefail
GHC_EXTRACTED_DIR=$(tar -tf "build_artifacts/${GHC_TAR}" 2>/dev/null | head -1 | cut -f1 -d"/")
set -o pipefail


echo "Extracted GHC to: build_artifacts/${GHC_EXTRACTED_DIR}"

# ── 8. Copy ALL GHC components to staging ──
# This is CRITICAL for macOS delocate - we need bin/ AND lib/ AND settings/
echo "Copying GHC components to staging..."

# Copy bin/
cp -a "build_artifacts/${GHC_EXTRACTED_DIR}/bin/." ghc-bindist/bin/ 2>/dev/null || true

# Copy lib/ - CRITICAL for macOS delocate
if [[ -d "build_artifacts/${GHC_EXTRACTED_DIR}/lib" ]]; then
    cp -a "build_artifacts/${GHC_EXTRACTED_DIR}/lib" ghc-bindist/
    echo "	Copied lib/"
else
    echo "	WARNING: lib/ directory not found"
fi

# Copy settings
if [[ -f "build_artifacts/${GHC_EXTRACTED_DIR}/settings" ]]; then
    cp -a "build_artifacts/${GHC_EXTRACTED_DIR}/settings" ghc-bindist/
    if [[ -d "ghc-bindist/lib" ]]; then
        cp -a "build_artifacts/${GHC_EXTRACTED_DIR}/settings" ghc-bindist/lib/
    fi
    echo "	Copied settings"
fi

# Copy package.conf.d
if [[ -d "build_artifacts/${GHC_EXTRACTED_DIR}/package.conf.d" ]]; then
    cp -a "build_artifacts/${GHC_EXTRACTED_DIR}/package.conf.d" ghc-bindist/
    if [[ -d "ghc-bindist/lib" ]]; then
        cp -a "build_artifacts/${GHC_EXTRACTED_DIR}/package.conf.d" ghc-bindist/lib/
    fi
    echo "	Copied package.conf.d"
fi

# Copy share (documentation, etc.)
if [[ -d "build_artifacts/${GHC_EXTRACTED_DIR}/share" ]]; then
    cp -a "build_artifacts/${GHC_EXTRACTED_DIR}/share" ghc-bindist/
    echo "	Copied share/"
fi

# Cleanup build artifacts to save space
rm -rf build_artifacts

echo "Binary acquisition and extraction complete."
echo "Staged files in ghc-bindist/:"
find ghc-bindist -maxdepth 2 -type d | sort

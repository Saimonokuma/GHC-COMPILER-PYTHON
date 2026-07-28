#!/usr/bin/env bash
set -euo pipefail

cleanup() {
	local exit_code=$?
	exit "$exit_code"
}
trap cleanup EXIT

# Handle SIGPIPE gracefully (e.g., piped to head)
trap '' PIPE

# Handle SIGINT (Ctrl+C)
trap 'echo "Interrupted"; exit 130' INT

STAGING_DIR="ghc-bindist"
OS=$(uname -s)

# ---------------------------------------------------------------------------
# Why this script cuts as hard as it does
#
# A stock GHC 9.4.8 tree is ~2,017 MB. Measured composition (x86_64 Linux
# bindist, 9,870 entries):
#
#     profiling   *_p.a, *.p_hi     602 MB   29.9%
#     docs        haddock/html      574 MB   28.4%
#     static      *.a               331 MB   16.4%
#     dynamic     *.so              173 MB    8.6%
#     bin/                          169 MB    8.4%
#     interfaces  *.hi, *.dyn_hi    166 MB    8.2%
#
# Profiling libraries and documentation are 58.3% of the tree and neither is
# needed to compile or run Haskell. Dropping both takes the tree to 863 MB and
# the compressed payload from 164 MB to 91 MB — under the 100 MB ceiling that
# governs distribution, without touching anything the compiler needs.
#
# What is deliberately NOT removed:
#   *.a       default linking is static; removing these breaks `ghc Main.hs`
#   *.so      GHCi and TemplateHaskell load these
#   *.hi      interface files; the compiler cannot resolve imports without them
#
# Set GHC_KEEP_PROFILING=1 to retain -prof support at the cost of ~600 MB.
# Set GHC_KEEP_DOCS=1 to retain the offline Haddock documentation.
# ---------------------------------------------------------------------------

KEEP_PROFILING="${GHC_KEEP_PROFILING:-0}"
KEEP_DOCS="${GHC_KEEP_DOCS:-0}"

human_size() {
	du -sm "${STAGING_DIR}/" 2>/dev/null | awk '{printf "%s MB", $1}' || echo "unknown"
}

echo "============================================"
echo " Binary size reduction"
echo " Platform: ${OS}"
echo "============================================"
echo "Initial size: $(human_size)"

# ---------------------------------------------------------------------------
# 1. Symbol stripping
#
# Previously this script exited early on Windows, which is why the Windows
# artifact was the largest of the three and had never been stripped once.
# MinGW ships a native `strip`; when GHC's own toolchain is staged we prefer it
# over whatever happens to be first on PATH.
# ---------------------------------------------------------------------------
case "${OS}" in
	Darwin)
		echo "-> macOS: strip -x (preserve global symbols in Mach-O)"
		find "${STAGING_DIR}" -type f -perm -0100 -exec sh -c '
			for f; do
				if file "$f" | grep -q "Mach-O"; then
					strip -x "$f" 2>/dev/null || true
				fi
			done
		' sh {} +
		find "${STAGING_DIR}" -type f -name "*.dylib" -exec strip -x {} + 2>/dev/null || true
		;;
	MINGW*|MSYS*|CYGWIN*)
		echo "-> Windows: stripping PE binaries"
		STRIP_BIN=""
		for candidate in \
			"$(find "${STAGING_DIR}" -name 'strip.exe' -type f 2>/dev/null | head -n 1)" \
			"$(command -v strip 2>/dev/null || true)"
		do
			if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then
				STRIP_BIN="${candidate}"
				break
			fi
		done

		if [ -n "${STRIP_BIN}" ]; then
			echo "   using: ${STRIP_BIN}"
			# --strip-unneeded would break import libraries (.dll.a); restrict
			# the aggressive form to executables and DLLs.
			find "${STAGING_DIR}" -type f \( -name "*.exe" -o -name "*.dll" \) \
				-exec "${STRIP_BIN}" --strip-unneeded {} + 2>/dev/null || true
			find "${STAGING_DIR}" -type f -name "*.o" \
				-exec "${STRIP_BIN}" --strip-debug {} + 2>/dev/null || true
		else
			echo "   WARNING: no strip found; skipping symbol removal"
		fi
		;;
	*)
		echo "-> Linux: strip --strip-unneeded"
		find "${STAGING_DIR}" -type f \( -perm -0100 -o -name "*.so" \) \
			-exec strip --strip-unneeded {} + 2>/dev/null || true
		;;
esac

echo "After stripping: $(human_size)"

# ---------------------------------------------------------------------------
# 2. Profiling libraries — 29.9% of the tree
#
# Only consumed by `ghc -prof`. Removing them leaves normal and optimised
# compilation completely intact.
# ---------------------------------------------------------------------------
if [ "${KEEP_PROFILING}" = "1" ]; then
	echo "-> Keeping profiling libraries (GHC_KEEP_PROFILING=1)"
else
	echo "-> Removing profiling libraries (*_p.a, *.p_hi, *.p_o)"
	find "${STAGING_DIR}" -type f \( -name "*_p.a" -o -name "*.p_hi" -o -name "*.p_o" \) -delete 2>/dev/null || true
	echo "   now: $(human_size)"
fi

# ---------------------------------------------------------------------------
# 3. Documentation — 28.4% of the tree
#
# Haddock HTML, LaTeX sources and .haddock interface files. The `haddock`
# executable itself is retained so users can still generate docs for their own
# packages; only the prebuilt GHC library documentation goes.
# ---------------------------------------------------------------------------
if [ "${KEEP_DOCS}" = "1" ]; then
	echo "-> Keeping bundled documentation (GHC_KEEP_DOCS=1)"
else
	echo "-> Removing bundled documentation (haddock html/latex)"
	for doc_dir in \
		"${STAGING_DIR}/share/doc" \
		"${STAGING_DIR}/doc" \
		"${STAGING_DIR}/share/html"
	do
		[ -d "${doc_dir}" ] && rm -rf "${doc_dir}"
	done
	find "${STAGING_DIR}" -type f -name "*.haddock" -delete 2>/dev/null || true
	find "${STAGING_DIR}" -type d -name "html" -prune -exec rm -rf {} + 2>/dev/null || true
	echo "   now: $(human_size)"
fi

# ---------------------------------------------------------------------------
# 4. Assert the toolchain survived the cut
#
# A size optimisation that silently deletes the compiler is worse than no
# optimisation at all, so verify the essentials are still present before
# declaring success.
# ---------------------------------------------------------------------------
echo "-> Verifying toolchain integrity after reduction"
MISSING=0

# `find ... | grep -q` is NOT safe here. grep -q exits at the first match while
# find is still writing; find takes SIGPIPE (141) and, under `set -o pipefail`,
# the whole pipeline reports failure. Whether that happens depends on how many
# paths fit in the pipe buffer before grep exits — so the check passes for a
# handful of binaries and fails for 1,599 interface files. `-print -quit` stops
# find itself at the first hit: no pipe, no race, and it short-circuits.
#
# `-type f` is also wrong on its own. In a tree produced by `make install`,
# bin/ghc is a SYMLINK to the versioned binary (ghc-9.4.8), and `-type f` does
# not match symlinks — so the guard reported the compiler missing while the
# compiler was sitting right there. It passed locally only because the raw
# extracted bindist has a real file at that path; the installed tree has a
# different shape. Match files and symlinks both, and accept the versioned
# names, since which one exists depends on how the tree was produced.
first_match() {
	find "${STAGING_DIR}" \( -type f -o -type l \) -name "$1" -print -quit 2>/dev/null
}

# Positive control: report what was actually found, so a future failure is
# diagnosable from the log instead of requiring a local reproduction.
for tool in ghc ghc-pkg; do
	FOUND="$(first_match "${tool}")"
	[ -n "${FOUND}" ] || FOUND="$(first_match "${tool}-*")"
	[ -n "${FOUND}" ] || FOUND="$(first_match "${tool}.exe")"

	if [ -z "${FOUND}" ]; then
		echo "   FATAL: '${tool}' is missing after optimization!" >&2
		MISSING=1
	else
		echo "   found ${tool}: ${FOUND}"
	fi
done

HI_FOUND="$(first_match '*.hi')"
if [ -z "${HI_FOUND}" ]; then
	echo "   FATAL: no interface (.hi) files survived — imports would fail!" >&2
	MISSING=1
else
	echo "   found interfaces: ${HI_FOUND}"
fi

if [ "${MISSING}" -ne 0 ]; then
	echo "Optimization removed something essential. Refusing to continue." >&2
	echo "--- staging tree layout for diagnosis ---" >&2
	find "${STAGING_DIR}" -maxdepth 2 \( -type f -o -type l -o -type d \) 2>/dev/null | head -n 40 >&2
	echo "--- anything named ghc* ---" >&2
	find "${STAGING_DIR}" \( -type f -o -type l \) -name 'ghc*' 2>/dev/null | head -n 20 >&2
	exit 5
fi

echo "   toolchain intact (ghc, ghc-pkg, interfaces present)"
echo "Final size: $(human_size)"
echo "Symbol stripping and binary optimization complete."

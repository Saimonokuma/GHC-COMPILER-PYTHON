# ghc_compiler_python/bootstrap.py
"""
First-run acquisition of the native GHC/Cabal payload.

This package ships in two tiers:

  * **thin**   — the PyPI wheel (``py3-none-any``). Pure Python; the native
    toolchain is absent and is fetched from GitHub Releases on first use.
  * **offline** — the platform-tagged wheels published on GitHub Releases.
    The toolchain is bundled; this module is never invoked.

The tier is not recorded anywhere: it is *observed*. If a bundled toolchain is
present the wrapper uses it, otherwise it asks this module for a payload root.

Design constraints, in order of precedence:

  1. Never half-install. Download, hash-verify, and extract happen out of line
     and are promoted into place with a single atomic rename. A cache directory
     that exists is a cache directory that is complete.
  2. Never silently substitute. A payload whose SHA-256 does not match the
     manifest shipped in this wheel is a hard failure, not a warning.
  3. Never leave the user guessing. Failures name the offline wheel that would
     have made the network unnecessary.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import List, NamedTuple, NoReturn, Optional

#: The compiler actually inside the payload. This is GHC's own version and it
#: moves only when the bindist does.
GHC_VERSION = "9.4.8"

#: The distribution coordinate: the git tag, the release, the payload asset
#: names, the cache directory, and the version on PyPI.
#:
#: These were one constant until 9.4.9, which read well while the two agreed
#: and became a trap the moment they had to diverge. 9.4.8 shipped a wrapper
#: that rejected every Windows machine without a system gcc; PyPI forbids
#: re-uploading a version, so the fix needed a new one, and a single constant
#: made "publish a fixed wheel" and "claim a GHC release that does not exist"
#: the same edit.
#:
#: They are now separate axes. The package version is 9.4.9; the compiler it
#: installs is, and reports itself as, 9.4.8. `ghc-wrapper --numeric-version`
#: answers for the compiler, never for the package.
RELEASE_VERSION = "9.5.0"

#: Release assets are addressed by tag, so a wheel always fetches the payload
#: built alongside it rather than whatever happens to be newest.
_RELEASE_BASE = (
    "https://github.com/Saimonokuma/GHC-COMPILER-PYTHON/releases/download"
    f"/v{RELEASE_VERSION}"
)

_HASH_MANIFEST = Path(__file__).resolve().parent / "payload_hashes.json"

_ENV_HOME = "GHC_COMPILER_PYTHON_HOME"
_ENV_OFFLINE = "GHC_COMPILER_PYTHON_OFFLINE"

_DOWNLOAD_TIMEOUT = 60
_LOCK_TIMEOUT = 900
_CHUNK = 1 << 20


class BootstrapError(RuntimeError):
    """Raised when the native payload cannot be made available."""


def _die(msg: str) -> NoReturn:
    raise BootstrapError(msg)


# --------------------------------------------------------------------------
# platform identity
# --------------------------------------------------------------------------

def platform_tag() -> str:
    """Return the payload tag for the running interpreter.

    These strings are the *payload* identifiers and deliberately mirror the
    wheel platform tags used for the offline tier, so a user who hits a network
    failure can map the error message straight onto a release asset.
    """
    machine = (os.uname().machine if hasattr(os, "uname") else os.environ.get(
        "PROCESSOR_ARCHITECTURE", "AMD64")).lower()

    if sys.platform.startswith("linux"):
        if machine in ("x86_64", "amd64"):
            return "manylinux_2_39_x86_64"
        if machine in ("aarch64", "arm64"):
            return "manylinux_2_39_aarch64"
    elif sys.platform == "darwin":
        if machine in ("arm64", "aarch64"):
            return "macosx_11_0_arm64"
        if machine == "x86_64":
            return "macosx_10_9_x86_64"
    elif sys.platform == "win32":
        if machine in ("amd64", "x86_64"):
            return "win_amd64"

    _die(
        f"Unsupported platform: {sys.platform}/{machine}. "
        f"GHC {GHC_VERSION} payloads are published for Linux x86_64, "
        "macOS arm64/x86_64 and Windows x86_64."
    )


def _archive_suffix() -> str:
    # Every platform ships an xz tarball as of 9.5.0.
    #
    # Windows used to ship a zip, and it cost users 148 MB per install for
    # nothing. Measured on the real extracted toolchain (1814 MB, 8311 files):
    #
    #   zip (deflate, -mx=5)   395.8 MB
    #   tar | xz -T0 -6        247.3 MB     37.5% smaller
    #
    # The local zip reproduced the published asset to within 0.1 MB, so that
    # is a comparison against the artifact users actually downloaded, not a
    # proxy. The round-trip was verified lossless by comparing all 8311 files
    # by SHA-256 -- not by sampling one binary and assuming the rest.
    #
    # Windows can read this: `_extract` dispatches on the suffix and has always
    # handled .tar.xz, and Python's tarfile has built-in lzma support. The zip
    # was never a Windows requirement, only an artefact of building it with 7z.
    return ".tar.xz"


def payload_name() -> str:
    return f"ghc-payload-{RELEASE_VERSION}-{platform_tag()}{_archive_suffix()}"


def payload_url() -> str:
    return f"{_RELEASE_BASE}/{payload_name()}"


# --------------------------------------------------------------------------
# cache location
# --------------------------------------------------------------------------

def cache_root() -> Path:
    """Directory holding extracted payloads, one subdirectory per version.

    ``GHC_COMPILER_PYTHON_HOME`` overrides the default for users who cannot
    write to the standard location (CI images, locked-down hosts, or anyone who
    simply wants the toolchain on a different volume).
    """
    override = os.environ.get(_ENV_HOME)
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "ghc-compiler-python" / "Cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ghc-compiler-python"

    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "ghc-compiler-python"


def payload_root() -> Path:
    """Where this version's toolchain lives once installed."""
    return cache_root() / RELEASE_VERSION / platform_tag()


def is_installed() -> bool:
    """True when a complete payload is present.

    Completion is signalled by a stamp written *after* the atomic rename, so a
    directory that exists without a stamp is treated as absent and replaced.
    """
    return (payload_root() / ".complete").is_file()


# --------------------------------------------------------------------------
# integrity
# --------------------------------------------------------------------------

def _expected_digest() -> str:
    if not _HASH_MANIFEST.is_file():
        _die(
            "Payload hash manifest is missing from the installed package "
            f"({_HASH_MANIFEST}). This wheel was built incorrectly; reinstall "
            "from PyPI or use an offline wheel from the releases page."
        )
    try:
        manifest = json.loads(_HASH_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _die(f"Payload hash manifest is unreadable: {exc}")

    digest = manifest.get(payload_name())
    if not digest:
        _die(
            f"No SHA-256 recorded for {payload_name()} in the hash manifest. "
            "This platform was not published for this version."
        )
    return str(digest).lower()


def _digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------------------
# acquisition
# --------------------------------------------------------------------------

def _offline_hint() -> str:
    return (
        "If this machine has no network access, install the self-contained "
        "wheel instead — it bundles the toolchain and never downloads:\n"
        f"    {_RELEASE_BASE}/"
        f"ghc_compiler_python-{RELEASE_VERSION}-py3-none-{platform_tag()}.whl"
    )


def _download(url: str, dest: Path, quiet: bool) -> None:
    if not quiet:
        sys.stderr.write(f"Fetching GHC {GHC_VERSION} payload ({platform_tag()})\n")
        sys.stderr.write(f"  from {url}\n")

    request = urllib.request.Request(
        url, headers={"User-Agent": f"ghc-compiler-python/{RELEASE_VERSION}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=_DOWNLOAD_TIMEOUT) as response:
            total = int(response.headers.get("Content-Length") or 0)
            seen = 0
            last = 0.0
            with dest.open("wb") as out:
                while True:
                    chunk = response.read(_CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    seen += len(chunk)
                    now = time.monotonic()
                    if not quiet and total and now - last > 0.5:
                        last = now
                        pct = seen * 100 // total
                        sys.stderr.write(
                            f"\r  {pct:3d}%  {seen >> 20} / {total >> 20} MiB"
                        )
                        sys.stderr.flush()
            if not quiet and total:
                sys.stderr.write("\r  100%  done                    \n")
    except urllib.error.HTTPError as exc:
        _die(
            f"Download failed with HTTP {exc.code} for {url}\n"
            f"{_offline_hint()}"
        )
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        _die(f"Download failed: {exc}\n{_offline_hint()}")


def _is_within(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _extract(archive: Path, dest: Path) -> None:
    """Extract the payload, refusing entries that escape the destination.

    Release assets are our own, but an archive member is still untrusted input:
    a traversal entry would write outside the cache. Python 3.12 grew a
    ``filter`` argument for exactly this; older interpreters are checked by hand
    so the guarantee does not depend on the runtime version.
    """
    dest.mkdir(parents=True, exist_ok=True)

    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                if not _is_within(dest, dest / member):
                    _die(f"Refusing archive entry outside destination: {member}")
            zf.extractall(dest)
        return

    with tarfile.open(archive, "r:xz") as tf:
        if hasattr(tarfile, "data_filter"):
            tf.extractall(dest, filter="data")
        else:
            for member in tf.getmembers():
                if member.issym() or member.islnk():
                    link = dest / Path(member.name).parent / member.linkname
                    if not _is_within(dest, link):
                        _die(f"Refusing link escaping destination: {member.name}")
                elif not _is_within(dest, dest / member.name):
                    _die(f"Refusing archive entry outside destination: {member.name}")
            tf.extractall(dest)


def _restore_exec_bits(root: Path) -> None:
    """Re-assert the executable bit on ``bin/`` after extraction.

    Zip carries no POSIX mode, and a payload unpacked from one on a Unix host
    would otherwise yield a toolchain that cannot be run.
    """
    if sys.platform == "win32":
        return
    for directory in (root / "bin", root / "lib"):
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and not path.is_symlink():
                mode = path.stat().st_mode
                if mode & 0o111 or path.suffix in ("", ".so"):
                    path.chmod(mode | 0o755)


class _DirectoryLock:
    """Cross-process lock built on atomic ``mkdir``.

    Two interpreters importing the package at once must not both download
    350 MB. ``mkdir`` is atomic on every filesystem we target, which makes it a
    more portable primitive here than ``fcntl`` or ``msvcrt`` locking.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._held = False

    def __enter__(self) -> "_DirectoryLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + _LOCK_TIMEOUT
        announced = False
        while True:
            try:
                self._path.mkdir()
                self._held = True
                return self
            except FileExistsError:
                if is_installed():
                    # Whoever held the lock finished the job for us.
                    return self
                if time.monotonic() > deadline:
                    _die(
                        f"Timed out waiting for another process to finish the "
                        f"GHC download (lock: {self._path}). If no other "
                        "install is running, remove that directory and retry."
                    )
                if not announced:
                    announced = True
                    sys.stderr.write(
                        "Waiting for a concurrent GHC installation to finish...\n"
                    )
                time.sleep(0.5)

    def __exit__(self, *_exc: object) -> None:
        if self._held:
            shutil.rmtree(self._path, ignore_errors=True)


def ensure_payload(quiet: bool = False) -> Path:
    """Return the payload root, installing it first if necessary.

    Idempotent and safe to call from every entry point on every invocation:
    the fast path is a single ``stat`` of the completion stamp.
    """
    root = payload_root()
    if is_installed():
        return root

    if os.environ.get(_ENV_OFFLINE, "").strip().lower() in ("1", "true", "yes"):
        _die(
            f"{_ENV_OFFLINE} is set and no toolchain is installed at {root}.\n"
            f"{_offline_hint()}"
        )

    expected = _expected_digest()

    with _DirectoryLock(cache_root() / f".lock-{RELEASE_VERSION}-{platform_tag()}"):
        if is_installed():
            return root

        root.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".ghc-staging-", dir=str(root.parent)))
        archive = staging / payload_name()
        try:
            _download(payload_url(), archive, quiet)

            actual = _digest_file(archive)
            if actual != expected:
                _die(
                    "Payload integrity check FAILED — refusing to install.\n"
                    f"  expected SHA-256: {expected}\n"
                    f"  actual   SHA-256: {actual}\n"
                    "The download was corrupted or the release asset was "
                    "modified. Nothing has been installed."
                )

            unpacked = staging / "root"
            _extract(archive, unpacked)
            archive.unlink(missing_ok=True)

            # GHC tarballs carry a single top-level directory; flatten it so the
            # payload root always has bin/ and lib/ directly beneath it.
            entries = [p for p in unpacked.iterdir()]
            if len(entries) == 1 and entries[0].is_dir():
                unpacked = entries[0]

            _restore_exec_bits(unpacked)
            (unpacked / ".complete").write_text(
                f"{RELEASE_VERSION} {platform_tag()}\n", encoding="utf-8"
            )

            if root.exists():
                shutil.rmtree(root, ignore_errors=True)
            os.replace(unpacked, root)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    if not quiet:
        sys.stderr.write(f"GHC {GHC_VERSION} installed to {root}\n")
    return root


def find_installed_root() -> Optional[Path]:
    """Return the cached payload root, or ``None`` — never downloads.

    Used by the wrapper to decide whether a bundled toolchain or a previously
    bootstrapped one should win, without triggering acquisition as a side
    effect of merely asking.
    """
    try:
        return payload_root() if is_installed() else None
    except BootstrapError:
        return None


# --------------------------------------------------------------------------
# cache inventory
# --------------------------------------------------------------------------
#
# Nothing in this package has ever removed an old toolchain. Each release
# caches under its own RELEASE_VERSION -- which is deliberate and load-bearing,
# since a payload rebuilt under a new tag is not byte-identical and reusing the
# old tree would skip the digest check entirely -- but the consequence is that
# every upgrade silently costs another ~1.8 GB on Windows.
#
# Measured on the maintainer's machine after 9.4.9: 3.6 GB in two versions,
# heading for 5.4 GB once 9.5.0 lands.
#
# What ships here is REPORTING ONLY. Deletion is deliberately not implemented
# yet: a bug in a cache pruner destroys user data on a machine we cannot see,
# and the correct policy (which versions, whose consent, what about a venv still
# pointing at an old one) is not yet settled. Telling the user what they have
# and where it is costs nothing and can harm nothing.

class CacheEntry(NamedTuple):
    """One cached release, as found on disk."""

    version: str
    platform: str
    path: Path
    complete: bool
    bytes: int

    @property
    def is_current(self) -> bool:
        """True when this entry is the release this wheel would use."""
        return self.version == RELEASE_VERSION


def _tree_size(path: Path) -> int:
    """Bytes under ``path``. Symlinks are counted as links, not as targets, so
    a tree cannot be double-counted through one."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        for name in filenames:
            f = Path(dirpath) / name
            try:
                total += f.lstat().st_size
            except OSError:
                # A file that vanished mid-walk is not a reason to fail a
                # read-only report.
                continue
    return total


def cache_entries() -> List[CacheEntry]:
    """Every cached payload, current release included.

    Read-only and never raises for an absent or unreadable cache: this exists
    to answer "what is on my disk", which must work even when the cache is in a
    state that would stop an install.
    """
    root = cache_root()
    entries: List[CacheEntry] = []
    if not root.is_dir():
        return entries

    for version_dir in sorted(root.iterdir()):
        if not version_dir.is_dir():
            continue
        for platform_dir in sorted(version_dir.iterdir()):
            if not platform_dir.is_dir():
                continue
            entries.append(CacheEntry(
                version=version_dir.name,
                platform=platform_dir.name,
                path=platform_dir,
                complete=(platform_dir / ".complete").is_file(),
                bytes=_tree_size(platform_dir),
            ))
    return entries


def _human(n: int) -> str:
    """Bytes as a short human string. Deliberately base-1024 and labelled
    accordingly, so the number can be checked against what a file manager
    shows."""
    step = 1024.0
    value = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < step or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= step
    return f"{value:.1f} TiB"


def cache_report() -> str:
    """Human-readable inventory of the cache. Pure: touches no state."""
    entries = cache_entries()
    root = cache_root()
    lines = [f"cache root: {root}"]

    if not entries:
        lines.append("  (empty -- nothing has been downloaded yet)")
        return "\n".join(lines)

    total = 0
    reclaimable = 0
    for e in entries:
        total += e.bytes
        marks = []
        if e.is_current:
            marks.append("current")
        else:
            marks.append("superseded")
            reclaimable += e.bytes
        if not e.complete:
            marks.append("INCOMPLETE")
        label = f"{e.version}/{e.platform}"
        lines.append(f"  {label:<28}{_human(e.bytes):>10}  "
                     f"[{', '.join(marks)}]")

    lines.append(f"  {'-' * 38}")
    lines.append(f"  {'total':<28}{_human(total):>10}")
    if reclaimable:
        lines.append(
            f"  {'superseded (not deleted)':<28}{_human(reclaimable):>10}")
        lines.append("")
        lines.append("Nothing is removed automatically. To reclaim space, "
                     "delete the superseded")
        lines.append("directories listed above by hand -- but only if no "
                     "environment still uses them.")
    return "\n".join(lines)


def _main(argv: Optional[List[str]] = None) -> int:
    """``python -m ghc_compiler_python.bootstrap --cache-info``.

    Read-only by construction: there is no subcommand here that writes.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--cache-info"]:
        print(cache_report())
        return 0
    if args in ([], ["--help"], ["-h"]):
        print("usage: python -m ghc_compiler_python.bootstrap --cache-info")
        print()
        print("  --cache-info   list cached toolchains and their sizes.")
        print("                 Reports only; never deletes anything.")
        return 0
    sys.stderr.write(f"unknown arguments: {' '.join(args)}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())

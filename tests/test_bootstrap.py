"""Unit tests for ghc_compiler_python.bootstrap.

These cover the properties that decide whether a user ends up with a working
toolchain or a corrupted one: digest enforcement, atomic promotion, traversal
refusal, and the absence of network access on paths that must not touch it.

Nothing here reaches the network. Downloads are stubbed; what is under test is
the surrounding logic, which is where the failure modes live.
"""

import hashlib
import json
import os
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from ghc_compiler_python import bootstrap


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Point the cache at a scratch directory for every test."""
    monkeypatch.setenv(bootstrap._ENV_HOME, str(tmp_path / "cache"))
    monkeypatch.delenv(bootstrap._ENV_OFFLINE, raising=False)
    yield


class TestPlatformIdentity:
    def test_tag_is_nonempty(self):
        assert bootstrap.platform_tag()

    def test_payload_name_carries_version_and_tag(self):
        name = bootstrap.payload_name()
        assert bootstrap.GHC_VERSION in name
        assert bootstrap.platform_tag() in name

    def test_suffix_matches_platform(self):
        expected = ".zip" if sys.platform == "win32" else ".tar.xz"
        assert bootstrap.payload_name().endswith(expected)

    def test_url_is_pinned_to_the_matching_tag(self):
        """A wheel must fetch the payload built alongside it, not 'latest'.

        Addressing the release by tag is what keeps a 9.4.8 wheel from silently
        picking up a 9.6 payload after a future release.
        """
        assert f"/v{bootstrap.GHC_VERSION}/" in bootstrap.payload_url()

    def test_unsupported_platform_is_refused(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "sunos5")
        with pytest.raises(bootstrap.BootstrapError) as exc:
            bootstrap.platform_tag()
        assert "Unsupported platform" in str(exc.value)


class TestCacheLocation:
    def test_env_override_wins(self, tmp_path, monkeypatch):
        target = tmp_path / "elsewhere"
        monkeypatch.setenv(bootstrap._ENV_HOME, str(target))
        assert bootstrap.cache_root() == target.resolve()

    def test_payload_root_is_versioned_and_platform_scoped(self):
        root = bootstrap.payload_root()
        assert root.name == bootstrap.platform_tag()
        assert root.parent.name == bootstrap.GHC_VERSION

    def test_absent_until_stamped(self):
        """A directory without the completion stamp counts as absent.

        This is what makes an interrupted install self-healing rather than
        permanently broken: the partial tree is simply not seen.
        """
        root = bootstrap.payload_root()
        root.mkdir(parents=True)
        (root / "bin").mkdir()
        assert bootstrap.is_installed() is False
        assert bootstrap.find_installed_root() is None

        (root / ".complete").write_text("x", encoding="utf-8")
        assert bootstrap.is_installed() is True
        assert bootstrap.find_installed_root() == root


class TestDigestManifest:
    def test_missing_manifest_is_a_hard_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(bootstrap, "_HASH_MANIFEST", tmp_path / "nope.json")
        with pytest.raises(bootstrap.BootstrapError) as exc:
            bootstrap._expected_digest()
        assert "manifest is missing" in str(exc.value)

    def test_unknown_platform_in_manifest_is_a_hard_error(self, monkeypatch, tmp_path):
        manifest = tmp_path / "hashes.json"
        manifest.write_text(json.dumps({"some-other-payload.tar.xz": "ab" * 32}),
                            encoding="utf-8")
        monkeypatch.setattr(bootstrap, "_HASH_MANIFEST", manifest)
        with pytest.raises(bootstrap.BootstrapError) as exc:
            bootstrap._expected_digest()
        assert "No SHA-256 recorded" in str(exc.value)

    def test_digest_matches_hashlib(self, tmp_path):
        blob = tmp_path / "blob"
        blob.write_bytes(b"payload bytes" * 1000)
        assert bootstrap._digest_file(blob) == hashlib.sha256(blob.read_bytes()).hexdigest()


class TestExtractionContainment:
    """The Lean proofs cover this exhaustively; these confirm the Python
    implementation matches the proved model."""

    def test_rejects_tar_traversal(self, tmp_path):
        archive = tmp_path / "evil.tar.xz"
        payload = tmp_path / "payload.txt"
        payload.write_text("pwned", encoding="utf-8")

        with tarfile.open(archive, "w:xz") as tf:
            tf.add(payload, arcname="../../escaped.txt")

        dest = tmp_path / "dest"
        with pytest.raises((bootstrap.BootstrapError, tarfile.TarError)):
            bootstrap._extract(archive, dest)

        assert not (tmp_path.parent / "escaped.txt").exists()

    def test_rejects_zip_traversal(self, tmp_path):
        archive = tmp_path / "evil.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../../escaped.txt", "pwned")

        dest = tmp_path / "dest"
        with pytest.raises(bootstrap.BootstrapError) as exc:
            bootstrap._extract(archive, dest)
        assert "outside destination" in str(exc.value)

    def test_accepts_ordinary_members(self, tmp_path):
        """A guard that rejected everything would be safe and useless."""
        archive = tmp_path / "good.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("bin/ghc", "binary")
            zf.writestr("lib/ghc-9.4.8/settings", "settings")

        dest = tmp_path / "dest"
        bootstrap._extract(archive, dest)
        assert (dest / "bin" / "ghc").is_file()
        assert (dest / "lib" / "ghc-9.4.8" / "settings").is_file()

    def test_is_within_rejects_dotdot(self, tmp_path):
        base = tmp_path / "base"
        base.mkdir()
        assert bootstrap._is_within(base, base / "sub" / "file")
        assert not bootstrap._is_within(base, base / ".." / "escaped")


class TestOfflineMode:
    def test_offline_refuses_to_download(self, monkeypatch):
        monkeypatch.setenv(bootstrap._ENV_OFFLINE, "1")

        def explode(*_a, **_k):
            raise AssertionError("network was contacted in offline mode")

        monkeypatch.setattr(bootstrap, "_download", explode)
        with pytest.raises(bootstrap.BootstrapError) as exc:
            bootstrap.ensure_payload(quiet=True)
        assert bootstrap._ENV_OFFLINE in str(exc.value)

    def test_error_names_the_offline_wheel(self):
        """Every failure must tell the user how to avoid needing the network."""
        hint = bootstrap._offline_hint()
        assert ".whl" in hint
        assert bootstrap.platform_tag() in hint


class TestEnsurePayload:
    """End-to-end over a stubbed download: the real acquisition logic runs."""

    def _stub_archive(self, tmp_path, monkeypatch, *, corrupt=False):
        staging = tmp_path / "src" / f"ghc-{bootstrap.GHC_VERSION}"
        (staging / "bin").mkdir(parents=True)
        (staging / "bin" / "ghc").write_text("#!/bin/sh\n", encoding="utf-8")

        suffix = ".zip" if sys.platform == "win32" else ".tar.xz"
        built = tmp_path / f"payload{suffix}"
        if suffix == ".zip":
            with zipfile.ZipFile(built, "w") as zf:
                for p in staging.rglob("*"):
                    if p.is_file():
                        zf.write(p, p.relative_to(staging.parent))
        else:
            with tarfile.open(built, "w:xz") as tf:
                tf.add(staging, arcname=staging.name)

        digest = bootstrap._digest_file(built)
        manifest = tmp_path / "hashes.json"
        recorded = ("00" * 32) if corrupt else digest
        manifest.write_text(json.dumps({bootstrap.payload_name(): recorded}),
                            encoding="utf-8")
        monkeypatch.setattr(bootstrap, "_HASH_MANIFEST", manifest)

        def fake_download(url, dest, quiet):
            dest.write_bytes(built.read_bytes())

        monkeypatch.setattr(bootstrap, "_download", fake_download)
        return built

    def test_installs_and_is_idempotent(self, tmp_path, monkeypatch):
        self._stub_archive(tmp_path, monkeypatch)

        root = bootstrap.ensure_payload(quiet=True)
        assert bootstrap.is_installed()
        assert (root / "bin" / "ghc").is_file()
        assert (root / ".complete").is_file()

        # Second call must not re-download.
        def explode(*_a, **_k):
            raise AssertionError("re-downloaded an installed payload")

        monkeypatch.setattr(bootstrap, "_download", explode)
        assert bootstrap.ensure_payload(quiet=True) == root

    def test_digest_mismatch_installs_nothing(self, tmp_path, monkeypatch):
        """A corrupted or substituted payload must leave no trace."""
        self._stub_archive(tmp_path, monkeypatch, corrupt=True)

        with pytest.raises(bootstrap.BootstrapError) as exc:
            bootstrap.ensure_payload(quiet=True)

        assert "integrity check FAILED" in str(exc.value)
        assert not bootstrap.is_installed()
        assert not bootstrap.payload_root().exists()

    def test_no_staging_residue_after_success(self, tmp_path, monkeypatch):
        self._stub_archive(tmp_path, monkeypatch)
        bootstrap.ensure_payload(quiet=True)

        leftovers = list(bootstrap.payload_root().parent.glob(".ghc-staging-*"))
        assert leftovers == [], f"staging directories leaked: {leftovers}"

    def test_no_staging_residue_after_failure(self, tmp_path, monkeypatch):
        self._stub_archive(tmp_path, monkeypatch, corrupt=True)
        with pytest.raises(bootstrap.BootstrapError):
            bootstrap.ensure_payload(quiet=True)

        parent = bootstrap.payload_root().parent
        leftovers = list(parent.glob(".ghc-staging-*")) if parent.exists() else []
        assert leftovers == [], f"staging directories leaked on failure: {leftovers}"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes only")
    def test_exec_bits_restored(self, tmp_path, monkeypatch):
        """Zip carries no POSIX mode; an unrunnable toolchain is not a toolchain."""
        self._stub_archive(tmp_path, monkeypatch)
        root = bootstrap.ensure_payload(quiet=True)
        assert os.access(root / "bin" / "ghc", os.X_OK)


class TestLockDirectory:
    def test_lock_is_released(self, tmp_path):
        lock = tmp_path / "lock"
        with bootstrap._DirectoryLock(lock):
            assert lock.is_dir()
        assert not lock.exists()

    def test_waiter_returns_when_work_already_done(self, tmp_path, monkeypatch):
        """A process that finds the payload installed must not wait out the
        timeout -- it returns immediately."""
        lock = tmp_path / "lock"
        lock.mkdir(parents=True)
        monkeypatch.setattr(bootstrap, "is_installed", lambda: True)

        with bootstrap._DirectoryLock(lock):
            pass
        # Held by the other 'process', so ours must not have removed it.
        assert lock.exists()


class TestDownloadFailures:
    """The failure a user meets first, if they meet one at all.

    `_download` is the only code in this package that touches the network, and
    none of its error paths were exercised. A release asset that was never
    attached, a renamed file, a tag that does not exist and a machine with no
    connectivity all arrive here, and what the user does next depends entirely
    on whether the message says which URL failed and what to do instead.

    A bare traceback from urllib would be a support burden on every one of
    those paths, so the content of the message is asserted, not just the type
    of the exception.
    """

    def test_http_error_names_the_url_and_the_offline_route(self, tmp_path, monkeypatch):
        """404 is what a missing release asset looks like from the client."""
        import urllib.error

        url = bootstrap.payload_url()

        def fake_urlopen(*args, **kwargs):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        monkeypatch.setattr(bootstrap.urllib.request, "urlopen", fake_urlopen)

        with pytest.raises(bootstrap.BootstrapError) as exc:
            bootstrap._download(url, tmp_path / "payload.bin", quiet=True)

        message = str(exc.value)
        assert "404" in message
        assert url in message, "the failing URL must be in the message"
        # The user is stranded unless the message says what to do instead.
        assert "wheel" in message.lower()

    def test_network_failure_is_reported_not_raised_raw(self, tmp_path, monkeypatch):
        """No connectivity must not surface as a urllib traceback."""
        import urllib.error

        def fake_urlopen(*args, **kwargs):
            raise urllib.error.URLError("Name or service not known")

        monkeypatch.setattr(bootstrap.urllib.request, "urlopen", fake_urlopen)

        with pytest.raises(bootstrap.BootstrapError) as exc:
            bootstrap._download(bootstrap.payload_url(), tmp_path / "p.bin", quiet=True)

        assert "Name or service not known" in str(exc.value)
        assert "wheel" in str(exc.value).lower()

    def test_timeout_is_reported(self, tmp_path, monkeypatch):
        def fake_urlopen(*args, **kwargs):
            raise TimeoutError("timed out")

        monkeypatch.setattr(bootstrap.urllib.request, "urlopen", fake_urlopen)

        with pytest.raises(bootstrap.BootstrapError):
            bootstrap._download(bootstrap.payload_url(), tmp_path / "p.bin", quiet=True)

    def test_offline_hint_points_at_a_real_asset_name(self):
        """The suggested wheel must be one the release actually carries.

        The hint is only useful if the filename it prints matches what the
        pipeline uploads. A stale name here sends users looking for a file
        that does not exist.
        """
        hint = bootstrap._offline_hint()
        assert bootstrap.GHC_VERSION in hint
        assert bootstrap.platform_tag() in hint
        assert hint.rstrip().endswith(".whl")
        assert f"/v{bootstrap.GHC_VERSION}/" in hint, "asset URLs are tag-scoped"

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
from unittest.mock import patch

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
        assert bootstrap.RELEASE_VERSION in name
        assert bootstrap.platform_tag() in name

    def test_payload_name_is_built_from_the_release_axis(self):
        """Asset names are addressed by the release constant.

        CORRECTED at 9.6.1. This test used to open with

            assert bootstrap.RELEASE_VERSION != bootstrap.GHC_VERSION

        and then assert that GHC_VERSION was absent from the name. Both were
        wrong, in the same way the Lean spec was wrong: they took a fact that
        happened to hold for 9.4.9 and 9.5.0 -- a package version ahead of its
        compiler -- and treated it as an invariant. When the compiler was
        upgraded and both axes honestly named 9.6.1, this test failed on a
        release that was entirely correct.

        What actually matters is that the name is *derived from* the release
        constant, so it tracks that constant wherever it goes. Asserted by
        moving it, which no coincidence of equal version strings can satisfy.
        """
        assert bootstrap.RELEASE_VERSION in bootstrap.payload_name()
        with patch.object(bootstrap, "RELEASE_VERSION", "0.0.0-probe"):
            assert "0.0.0-probe" in bootstrap.payload_name(), (
                "payload_name ignored RELEASE_VERSION; asset names are no "
                "longer addressed by the release axis"
            )

    def test_cache_is_keyed_by_release_so_a_new_release_never_reuses_a_payload(self):
        """A payload rebuilt under a new tag is not byte-identical to the old
        one, so its digest differs. If the cache were keyed by anything that
        does not move with the release, a new release would find the previous
        tree already stamped `.complete` and skip the download entirely --
        with no digest check, because nothing would be downloaded to check.

        Also corrected at 9.6.1: asserted by moving the constant rather than by
        requiring the two version strings to differ.
        """
        assert bootstrap.payload_root().parent.name == bootstrap.RELEASE_VERSION
        with patch.object(bootstrap, "RELEASE_VERSION", "0.0.0-probe"):
            assert bootstrap.payload_root().parent.name == "0.0.0-probe", (
                "the cache directory did not follow RELEASE_VERSION"
            )

    def test_compiler_axis_is_reported_independently_of_the_release(self):
        """Moving the release constant must not change what compiler we claim.

        The mirror of the test above, and the pair together is what "two
        independent axes" means operationally. Proved in general in
        lean/Proofs/Payload.lean as report_ignores_the_release_axis; asserted
        here against the real module.
        """
        before = bootstrap.GHC_VERSION
        with patch.object(bootstrap, "RELEASE_VERSION", "0.0.0-probe"):
            assert bootstrap.GHC_VERSION == before

    def test_every_platform_ships_the_same_archive_format(self):
        """One format everywhere, as of 9.5.0.

        Windows shipped a zip through 9.4.9 and it cost users 148 MB per cold
        install for nothing: measured on the real toolchain (1814 MB, 8311
        files) the zip was 395.8 MB against 247.3 MB for tar.xz, with the
        round-trip verified lossless on every file by SHA-256. The zip was
        never a Windows requirement, only an artefact of building it with 7z.

        Asserted for the CURRENT platform and as a blanket property, so this
        cannot pass on Linux while quietly regressing on Windows.
        """
        assert bootstrap._archive_suffix() == ".tar.xz"
        assert bootstrap.payload_name().endswith(".tar.xz")
        assert not bootstrap.payload_name().endswith(".zip")

    def test_suffix_does_not_depend_on_the_host(self):
        """The archive format is a property of the RELEASE, not of the machine
        unpacking it. A suffix that varies by host means a wheel built on one
        platform disagrees with the asset published for another."""
        for fake in ("win32", "linux", "darwin"):
            with patch.object(bootstrap.sys, "platform", fake):
                assert bootstrap._archive_suffix() == ".tar.xz", (
                    f"archive suffix changed on {fake}; the payload name would "
                    f"then depend on who is asking"
                )

    def test_url_is_pinned_to_the_matching_tag(self):
        """A wheel must fetch the payload built alongside it, not 'latest'.

        Addressing the release by tag is what keeps a 9.4.8 wheel from silently
        picking up a 9.6 payload after a future release.
        """
        assert f"/v{bootstrap.RELEASE_VERSION}/" in bootstrap.payload_url()

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
        assert root.parent.name == bootstrap.RELEASE_VERSION

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

        # Deliberately built from bootstrap's own suffix rather than from
        # sys.platform. The fixture used to branch on the host, which meant it
        # agreed with the implementation only by coincidence -- and stopped
        # agreeing the moment the format became uniform in 9.5.0.
        suffix = bootstrap._archive_suffix()
        assert suffix == ".tar.xz", f"unexpected payload format {suffix}"
        built = tmp_path / f"payload{suffix}"
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
        assert bootstrap.RELEASE_VERSION in hint
        assert bootstrap.platform_tag() in hint
        assert hint.rstrip().endswith(".whl")
        assert f"/v{bootstrap.RELEASE_VERSION}/" in hint, "asset URLs are tag-scoped"


class TestCacheInventory:
    """The cache reporter.

    Deliberately reporting-only. These tests assert that as a property, not as
    a comment: a pruner that misfires destroys user data on a machine nobody
    can inspect, so until the policy is settled the code must be incapable of
    deleting anything.
    """

    def _make(self, tmp_path, version, platform="win_amd64", complete=True,
              payload=b"x" * 2048):
        d = tmp_path / "cache" / version / platform
        d.mkdir(parents=True)
        (d / "bin").mkdir()
        (d / "bin" / "ghc").write_bytes(payload)
        if complete:
            (d / ".complete").write_text("x", encoding="utf-8")
        return d

    def test_empty_cache_reports_empty_and_does_not_raise(self):
        assert bootstrap.cache_entries() == []
        assert "empty" in bootstrap.cache_report()

    def test_lists_every_version_present(self, tmp_path):
        self._make(tmp_path, "9.4.8")
        self._make(tmp_path, "9.4.9")
        self._make(tmp_path, bootstrap.RELEASE_VERSION)
        versions = {e.version for e in bootstrap.cache_entries()}
        assert versions == {"9.4.8", "9.4.9", bootstrap.RELEASE_VERSION}

    def test_current_release_is_distinguished_from_superseded(self, tmp_path):
        self._make(tmp_path, "9.4.8")
        self._make(tmp_path, bootstrap.RELEASE_VERSION)
        by_version = {e.version: e for e in bootstrap.cache_entries()}
        assert by_version[bootstrap.RELEASE_VERSION].is_current is True
        assert by_version["9.4.8"].is_current is False

    def test_incomplete_entry_is_flagged(self, tmp_path):
        self._make(tmp_path, "9.4.8", complete=False)
        entry = bootstrap.cache_entries()[0]
        assert entry.complete is False
        assert "INCOMPLETE" in bootstrap.cache_report()

    def test_size_is_measured_not_guessed(self, tmp_path):
        self._make(tmp_path, "9.4.8", payload=b"y" * 4096)
        entry = bootstrap.cache_entries()[0]
        # 4096 payload + the .complete stamp; assert the payload dominates
        # rather than pinning an exact total that stamp changes would break.
        assert entry.bytes >= 4096
        assert entry.bytes < 4096 + 1024

    def test_reporting_never_deletes(self, tmp_path):
        """The whole contract, asserted rather than trusted."""
        d = self._make(tmp_path, "9.4.8")
        before = sorted(p.name for p in d.rglob("*"))
        bootstrap.cache_entries()
        bootstrap.cache_report()
        bootstrap._main(["--cache-info"])
        after = sorted(p.name for p in d.rglob("*"))
        assert before == after, "the cache reporter modified the cache"
        assert d.is_dir()

    def test_no_deletion_primitive_is_reachable_from_the_cli(self):
        """A future maintainer adding `--prune` must also revisit these tests.

        Guards the stated policy at the level of the source: the CLI accepts
        exactly one flag, and it is read-only.
        """
        assert bootstrap._main(["--cache-info"]) == 0
        assert bootstrap._main(["--help"]) == 0
        assert bootstrap._main(["--prune"]) == 2
        assert bootstrap._main(["--delete", "9.4.8"]) == 2

    def test_report_names_the_root_so_a_user_can_find_it(self, tmp_path):
        self._make(tmp_path, "9.4.8")
        assert str(bootstrap.cache_root()) in bootstrap.cache_report()

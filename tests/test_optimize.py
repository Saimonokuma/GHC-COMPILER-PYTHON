"""Tests for scripts/optimize_binaries.sh.

This script had shipped three defects that all passed CI, because a shell
script that removes nothing still exits 0:

  * `find -type f -name ghc` reported the compiler missing. In a `make install`
    tree `bin/ghc` is a symlink, and -type f does not match symlinks.
  * documentation removal tested three hardcoded Unix paths. On Windows none
    exist, so it freed zero bytes and reported success -- the payload shipped
    at 385 MB against macOS's 94.
  * `find ... | wc -l` under `set -o pipefail` aborts the whole script if find
    exits non-zero, after deletions but before the integrity assertion.

None of those are visible from an exit status, so these tests assert on what
the script says it *found*, not merely that it survived.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "optimize_binaries.sh"


def _find_bash() -> str | None:
    """Locate a bash that can see the Windows filesystem.

    shutil.which("bash") on Windows finds C:\\Windows\\System32\\bash.exe --
    the WSL launcher -- which fails with

        WSL (Relay) ERROR: execvpe(/bin/bash) failed: No such file or directory

    and produces an empty stdout with returncode 1, which reads exactly like
    the script having crashed. Git for Windows ships the bash that CI actually
    uses, so prefer it and reject the System32 stub.
    """
    for candidate in (
        os.environ.get("BASH"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    ):
        if candidate and Path(candidate).exists():
            return candidate

    found = shutil.which("bash")
    if found and "system32" in found.replace("/", "\\").lower():
        return None
    return found


BASH = _find_bash()

pytestmark = pytest.mark.skipif(
    BASH is None or not SCRIPT.exists(),
    reason="needs a non-WSL bash and scripts/optimize_binaries.sh",
)


def run_optimize(staging: Path, **env_overrides: str) -> subprocess.CompletedProcess:
    """Run the script against a synthetic staging tree."""
    env = dict(os.environ)
    env["STAGING_DIR"] = str(staging)
    env.update(env_overrides)
    return subprocess.run(
        [BASH, str(SCRIPT)],
        cwd=staging.parent,
        env=env,
        capture_output=True,
        text=True,
        # `file`, `strip` and `du` emit locale-encoded bytes that are not
        # necessarily UTF-8. Without errors="replace" the harness dies decoding
        # the output instead of reporting what the script did -- a test failure
        # caused by the instrument rather than the subject.
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )


def make_tree(root: Path, *, docs_layout: str, size_kb: int = 256) -> Path:
    """Build a staging tree that looks enough like a GHC bindist.

    docs_layout selects where documentation lives, which is the whole point:
    Unix bindists use share/doc, the Windows bindist uses docs/.
    """
    staging = root / "ghc-bindist"
    (staging / "bin").mkdir(parents=True)
    (staging / "lib" / "ghc-9.4.8" / "bin").mkdir(parents=True)

    # The compiler must survive. Written as a real file here; the symlink case
    # is covered separately.
    for tool in ("ghc", "ghc-pkg", "haddock"):
        exe = staging / "bin" / tool
        exe.write_text("#!/bin/sh\necho stub\n")
        exe.chmod(0o755)

    # Interface files must survive -- imports cannot resolve without them.
    (staging / "lib" / "ghc-9.4.8" / "Prelude.hi").write_bytes(b"\x00" * 1024)
    (staging / "lib" / "ghc-9.4.8" / "Prelude.dyn_hi").write_bytes(b"\x00" * 1024)

    # Profiling libraries must go.
    (staging / "lib" / "ghc-9.4.8" / "libHSbase_p.a").write_bytes(b"\x00" * size_kb * 1024)

    if docs_layout == "unix":
        d = staging / "share" / "doc" / "ghc"
    elif docs_layout == "windows":
        d = staging / "docs" / "html" / "libraries"
    elif docs_layout == "none":
        d = None
    else:  # pragma: no cover
        raise ValueError(docs_layout)

    if d is not None:
        d.mkdir(parents=True)
        (d / "index.html").write_bytes(b"<html>" + b"x" * size_kb * 1024)
        (staging / "lib" / "ghc-9.4.8" / "base.haddock").write_bytes(b"\x00" * 4096)

    return staging


class TestDocumentationRemoval:
    """The defect: hardcoded Unix paths freed nothing on Windows, silently."""

    @pytest.mark.parametrize("layout", ["unix", "windows"])
    def test_documentation_is_found_wherever_the_bindist_put_it(self, tmp_path, layout):
        staging = make_tree(tmp_path, docs_layout=layout)
        result = run_optimize(staging)

        assert result.returncode == 0, result.stderr
        # Assert on what it reported removing, not merely that it exited 0 --
        # "removed nothing" and "nothing to remove" are the same exit status.
        assert "removing" in result.stdout, result.stdout
        assert "freed" in result.stdout, result.stdout

        assert not (staging / "share" / "doc").exists()
        assert not (staging / "docs").exists()
        assert not list(staging.rglob("*.haddock"))

    def test_absent_documentation_warns_instead_of_passing_quietly(self, tmp_path):
        staging = make_tree(tmp_path, docs_layout="none")
        result = run_optimize(staging)

        assert result.returncode == 0, result.stderr
        combined = result.stdout + result.stderr
        # This is the case that shipped a 385 MB payload while reporting success.
        assert "WARNING" in combined, combined
        assert "layout" in combined.lower(), combined

    def test_keep_docs_env_var_is_honoured(self, tmp_path):
        staging = make_tree(tmp_path, docs_layout="unix")
        result = run_optimize(staging, GHC_KEEP_DOCS="1")

        assert result.returncode == 0, result.stderr
        assert (staging / "share" / "doc").exists()


class TestToolchainIntegrityGuard:
    """The guard must find the compiler in the shape production actually builds."""

    def test_symlinked_compiler_is_found(self, tmp_path):
        """`make install` leaves bin/ghc as a symlink to ghc-9.4.8.

        `find -type f` does not match symlinks, so the guard declared the
        compiler missing and failed the build it was protecting.
        """
        staging = make_tree(tmp_path, docs_layout="unix")
        real = staging / "bin" / "ghc-9.4.8"
        real.write_text("#!/bin/sh\necho stub\n")
        real.chmod(0o755)

        link = staging / "bin" / "ghc"
        link.unlink()
        try:
            link.symlink_to("ghc-9.4.8")
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation not permitted on this host")

        result = run_optimize(staging)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "found ghc" in result.stdout, result.stdout
        assert "toolchain intact" in result.stdout, result.stdout

    def test_missing_compiler_is_a_hard_failure(self, tmp_path):
        """Deleting ghc must fail the build, not warn."""
        staging = make_tree(tmp_path, docs_layout="unix")
        (staging / "bin" / "ghc").unlink()

        result = run_optimize(staging)
        assert result.returncode != 0, "a missing compiler must not exit 0"
        assert "FATAL" in result.stdout + result.stderr


class TestWhatMustSurvive:
    """Trimming must not remove anything the compiler needs to work."""

    def test_interface_files_survive(self, tmp_path):
        staging = make_tree(tmp_path, docs_layout="unix")
        run_optimize(staging)
        assert (staging / "lib" / "ghc-9.4.8" / "Prelude.hi").exists()
        assert (staging / "lib" / "ghc-9.4.8" / "Prelude.dyn_hi").exists()

    def test_haddock_executable_survives_while_its_output_goes(self, tmp_path):
        """Users still generate docs for their own packages."""
        staging = make_tree(tmp_path, docs_layout="unix")
        run_optimize(staging)
        assert (staging / "bin" / "haddock").exists()
        assert not list(staging.rglob("*.haddock"))

    def test_profiling_libraries_are_removed(self, tmp_path):
        staging = make_tree(tmp_path, docs_layout="unix")
        run_optimize(staging)
        assert not list(staging.rglob("*_p.a"))

    def test_keep_profiling_env_var_is_honoured(self, tmp_path):
        staging = make_tree(tmp_path, docs_layout="unix")
        run_optimize(staging, GHC_KEEP_PROFILING="1")
        assert list(staging.rglob("*_p.a"))

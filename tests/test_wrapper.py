"""Unit tests for ghc_compiler_python.wrapper module."""

import os
import sys
import pytest
from unittest.mock import patch

from ghc_compiler_python.wrapper import (
    GHC_VERSION,
    HASKELL_POLLUTION_VARS,
    _sterilize_environment,
    _validate_c_linker,
    _resolve_binary,
    _try_resolve_binary,
)


class TestSterilizeEnvironment:
    """Tests for environment sterilization."""

    def test_removes_haskell_pollution(self):
        env = {
            "GHC_PACKAGE_PATH": "/fake/path",
            "CABAL_DIR": "/fake/cabal",
            "HOME": "/tmp/test",
            "PATH": "/usr/bin",
        }
        with patch.dict(os.environ, env, clear=True):
            result = _sterilize_environment()
        assert "GHC_PACKAGE_PATH" not in result
        assert "CABAL_DIR" not in result

    def test_overrides_home(self):
        with patch.dict(os.environ, {"HOME": "/original"}, clear=True):
            result = _sterilize_environment()
        assert result["HOME"] != "/original"

    def test_injects_bin_path(self):
        with patch.dict(os.environ, {"HOME": "/tmp", "PATH": "/usr/bin"}, clear=True):
            result = _sterilize_environment()
        assert "ghc-compiler-python" in result["HOME"] or sys.prefix in result["PATH"]

    def test_payload_vendor_lib_reaches_ld_library_path(self, tmp_path):
        """The payload's own shared libraries must be findable at runtime.

        GHC 9.4.8 links against ncurses 5. Ubuntu 24.04 ships ncurses 6 and has
        no libtinfo.so.5, so a payload that carries the library but a launcher
        that never looks at it fails identically to carrying nothing:

            ghc-9.4.8: error while loading shared libraries: libtinfo.so.5

        That is precisely how the delivered install failed on Linux while every
        job validating the offline wheel passed -- auditwheel had vendored the
        library into ghc_compiler_python.libs, which only the offline wheel has.

        sys.platform is patched rather than the test being skipped off Linux.
        A test that only runs on the platform where the bug already shipped is
        a test nobody sees fail until it is too late; this way all three CI
        legs and a developer laptop all check it.
        """
        root = tmp_path / "payload-root"
        (root / "vendor-lib").mkdir(parents=True)
        (root / "vendor-lib" / "libtinfo.so.5").write_bytes(b"\x7fELF")

        with patch("ghc_compiler_python.wrapper.sys.platform", "linux"):
            with patch("ghc_compiler_python.wrapper._ghc_root_or_prefix", return_value=root):
                with patch.dict(os.environ, {"HOME": "/tmp", "PATH": "/usr/bin"}, clear=True):
                    result = _sterilize_environment()

        assert str(root / "vendor-lib") in result.get("LD_LIBRARY_PATH", ""), (
            "the payload's vendor-lib is not on LD_LIBRARY_PATH, so a toolchain "
            "that ships its own libtinfo would still fail to start"
        )


class TestValidateCLinker:
    """Tests for C-linker validation."""

    @patch("ghc_compiler_python.wrapper.shutil.which")
    def test_passes_with_gcc(self, mock_which):
        mock_which.side_effect = lambda x: "/usr/bin/gcc" if x == "gcc" else None
        _validate_c_linker()  # Should not exit

    @patch("ghc_compiler_python.wrapper.shutil.which")
    def test_passes_with_clang(self, mock_which):
        mock_which.side_effect = lambda x: "/usr/bin/clang" if x == "clang" else None
        _validate_c_linker()  # Should not exit

    @patch("ghc_compiler_python.wrapper.shutil.which", return_value=None)
    def test_exits_without_linker(self, mock_which):
        with pytest.raises(SystemExit):
            _validate_c_linker()


class TestResolveBinary:
    """Tests for binary resolution.

    The contract these lock down is *hermeticity*. This package exists to
    supply a pinned GHC 9.4.8; resolving through PATH would silently hand the
    caller whatever compiler happens to be installed system-wide, at whatever
    version, while still reporting success. A previous revision did exactly
    that, so these tests assert the system compiler is ignored rather than
    preferred.
    """

    def test_ignores_system_ghc_on_path(self, tmp_path):
        """A GHC on PATH must NOT satisfy resolution."""
        fake = tmp_path / "ghc.exe" if sys.platform == "win32" else tmp_path / "ghc"
        fake.write_text("#!/bin/sh\necho system ghc\n", encoding="utf-8")

        with patch("ghc_compiler_python.wrapper.shutil.which", return_value=str(fake)):
            assert _try_resolve_binary("ghc") is None, (
                "system GHC on PATH was accepted; hermetic guarantee is broken"
            )

    def test_finds_bundled_binary(self, tmp_path, monkeypatch):
        """A toolchain bundled under the install prefix is used as-is."""
        name = "ghc.exe" if sys.platform == "win32" else "ghc"
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / name).write_text("binary", encoding="utf-8")

        monkeypatch.setattr(
            "ghc_compiler_python.wrapper._search_roots", lambda: [tmp_path]
        )
        assert _try_resolve_binary("ghc") == str(bin_dir / name)

    def test_finds_binary_nested_under_lib(self, tmp_path, monkeypatch):
        """Staged installs expose tools only under lib/ghc-<version>/bin."""
        name = "ghc-pkg.exe" if sys.platform == "win32" else "ghc-pkg"
        nested = tmp_path / "lib" / f"ghc-{GHC_VERSION}" / "bin"
        nested.mkdir(parents=True)
        (nested / name).write_text("binary", encoding="utf-8")

        monkeypatch.setattr(
            "ghc_compiler_python.wrapper._search_roots", lambda: [tmp_path]
        )
        assert _try_resolve_binary("ghc-pkg") == str(nested / name)

    def test_probe_never_acquires(self, monkeypatch):
        """Probing must not trigger a download as a side effect."""
        called = []
        monkeypatch.setattr(
            "ghc_compiler_python.bootstrap.ensure_payload",
            lambda *a, **k: called.append(1),
        )
        _try_resolve_binary("definitely_not_a_real_tool")
        assert called == [], "probing triggered payload acquisition"

    def test_exits_when_binary_not_found(self, monkeypatch):
        monkeypatch.setattr(
            "ghc_compiler_python.wrapper._search_roots", lambda: []
        )
        monkeypatch.setattr(
            "ghc_compiler_python.wrapper._ghc_root_if_present", lambda: None
        )
        with pytest.raises(SystemExit):
            _resolve_binary("nonexistent_binary")


class TestPollutionVars:
    """Tests for pollution variable list completeness."""

    def test_contains_key_vars(self):
        expected = [
            "GHC_PACKAGE_PATH",
            "GHC_ENVIRONMENT",
            "CABAL_DIR",
            "CABAL_CONFIG",
            "STACK_ROOT",
        ]
        for var in expected:
            assert var in HASKELL_POLLUTION_VARS

    def test_exact_count(self):
        assert len(HASKELL_POLLUTION_VARS) == 13
        assert isinstance(HASKELL_POLLUTION_VARS, frozenset)


class TestExceptionHandling:
    """Tests for proper specific exception handling."""

    @patch("ghc_compiler_python.wrapper.os.execve")
    @patch("ghc_compiler_python.wrapper._resolve_binary")
    @patch("ghc_compiler_python.wrapper._resolve_runtime_paths")
    @patch("ghc_compiler_python.wrapper._sterilize_environment")
    @patch("ghc_compiler_python.wrapper._validate_c_linker")
    @patch("ghc_compiler_python.wrapper.sys.argv", ["ghc"])
    def test_subprocess_error_handling(
        self,
        mock_validate,
        mock_sterilize,
        mock_resolve_paths,
        mock_resolve_binary,
        mock_execve,
    ):
        from ghc_compiler_python.wrapper import _execute_tool

        mock_resolve_binary.return_value = "/bin/true"
        mock_sterilize.return_value = {}

        # Test OSError
        import sys

        # Test depending on platform
        if sys.platform != "win32":
            mock_execve.side_effect = OSError("test error")
            with pytest.raises(SystemExit) as exc:
                _execute_tool("ghc")
            assert exc.value.code == 1
        else:
            with patch("ghc_compiler_python.wrapper.subprocess.run") as mock_run:
                mock_run.side_effect = OSError("test error")
                with pytest.raises(SystemExit) as exc:
                    _execute_tool("ghc")
                assert exc.value.code == 1

class TestBinWrappersResource:
    """Tests for BinWrappersResource binary filtering."""

    def test_extract_targets_ignores_binaries(self, tmp_path):
        from ghc_compiler_python.wrapper import BinWrappersResource
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        # Text script
        script = bin_dir / "ghc-script"
        script.write_text("#!/bin/bash\necho test")

        # Binary file
        binary = bin_dir / "ghc-pkg"
        binary.write_bytes(b"\x7fELF\x00\x01")

        # Windows executable
        exe = bin_dir / "ghc.exe"
        exe.write_text("dummy exe")

        # Symlink
        symlink = bin_dir / "ghc-link"
        symlink.symlink_to(script)

        targets = BinWrappersResource.extract_targets(bin_dir)

        assert str(script) in targets
        assert str(binary) not in targets
        assert str(exe) not in targets
        assert str(symlink) not in targets

    def test_patch_build_time_ignores_binaries(self, tmp_path):
        from ghc_compiler_python.wrapper import BinWrappersResource
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        script = bin_dir / "ghc-script"
        script.write_text("#!/bin/bash\necho /ghc-prefix")

        binary_content = b"\x7fELF\x00\x01/ghc-prefix"
        binary = bin_dir / "ghc-pkg"
        binary.write_bytes(binary_content)

        patched_count = BinWrappersResource.patch_build_time(bin_dir, "9.4.8", "@GHC_PREFIX@")

        # Only the script should be patched
        assert patched_count == 1
        assert "@GHC_PREFIX@" in script.read_text()

        # Binary should remain untouched
        assert binary.read_bytes() == binary_content


class TestDynamicGetattr:
    """Tests for dynamic __getattr__ execution closure generation."""

    @patch("ghc_compiler_python.wrapper._execute_tool")
    def test_execute_ghc_generation(self, mock_execute_tool):
        import ghc_compiler_python.wrapper as wrapper

        # Test getting the dynamic attribute
        executor = wrapper.__getattr__("execute_ghc")

        # Verify it returns a callable with the correct name
        assert callable(executor)
        assert executor.__name__ == "execute_ghc"

        # Execute it and verify it calls _execute_tool correctly
        executor()
        mock_execute_tool.assert_called_once_with("ghc", extra_args=["-v0"])

    @patch("ghc_compiler_python.wrapper._execute_tool")
    def test_execute_other_tool_generation(self, mock_execute_tool):
        import ghc_compiler_python.wrapper as wrapper

        # Test tool names with underscores that need replacing
        executor = wrapper.__getattr__("execute_cabal_install")

        assert callable(executor)
        assert executor.__name__ == "execute_cabal_install"

        executor()
        # _ to - replacement
        mock_execute_tool.assert_called_once_with("cabal-install", extra_args=None)

    def test_invalid_attribute(self):
        import ghc_compiler_python.wrapper as wrapper

        with pytest.raises(AttributeError, match="has no attribute 'invalid_attr'"):
            wrapper.__getattr__("invalid_attr")

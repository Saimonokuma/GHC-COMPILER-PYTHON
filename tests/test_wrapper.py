"""Unit tests for ghc_compiler_python.wrapper module."""

import os
import sys
import pytest
from unittest.mock import patch

from ghc_compiler_python.wrapper import (
    HASKELL_POLLUTION_VARS,
    _sterilize_environment,
    _validate_c_linker,
    _resolve_binary,
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
    """Tests for binary resolution."""

    @patch("ghc_compiler_python.wrapper.shutil.which")
    def test_finds_binary_in_path(self, mock_which):
        mock_which.return_value = "/usr/local/bin/ghc"
        result = _resolve_binary("ghc")
        assert result == "/usr/local/bin/ghc"

    @patch("ghc_compiler_python.wrapper.shutil.which", return_value=None)
    def test_exits_when_binary_not_found(self, mock_which):
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

class TestOSErrorHandling:
    """Tests for proper OSError handling during iterdir."""

    def test_find_platform_lib_subdir_permission_error(self, tmp_path):
        from ghc_compiler_python.wrapper import _find_platform_lib_subdir

        # Create directory structure
        ghc_lib = tmp_path / "lib" / "ghc-9.4.8" / "lib"
        ghc_lib.mkdir(parents=True)

        with patch("ghc_compiler_python.wrapper.sys.prefix", str(tmp_path)):
            with patch("pathlib.Path.iterdir", side_effect=PermissionError("test permission error")):
                # Should not raise exception
                result = _find_platform_lib_subdir()
                assert result == ""

    def test_package_db_resource_permission_error(self, tmp_path):
        from ghc_compiler_python.wrapper import PackageDBResource

        pkg_db = tmp_path / "package.conf.d"
        pkg_db.mkdir()

        with patch("pathlib.Path.iterdir", side_effect=PermissionError("test permission error")):
            # Should not raise exception
            assert PackageDBResource.validate(pkg_db) is False
            assert PackageDBResource.extract_targets(pkg_db) == []

    def test_bin_wrappers_resource_permission_error(self, tmp_path):
        from ghc_compiler_python.wrapper import BinWrappersResource

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        with patch("pathlib.Path.iterdir", side_effect=PermissionError("test permission error")):
            # Should not raise exception
            assert BinWrappersResource.extract_targets(bin_dir) == []
            assert BinWrappersResource.patch_build_time(bin_dir, "9.4.8", "@GHC_PREFIX@") == 0

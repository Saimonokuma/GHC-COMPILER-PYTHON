"""Unit tests for ghc_compiler_python.wrapper module."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

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
		assert isinstance(HASKELL_POLLUTION_VARS, list)

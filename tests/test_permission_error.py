import pytest
import os
from unittest.mock import patch
from pathlib import Path
from ghc_compiler_python.wrapper import _find_platform_lib_subdir, BinWrappersResource, PackageDBResource

def test_find_platform_lib_subdir_permission_error():
    with patch("pathlib.Path.is_dir", return_value=True):
        with patch("pathlib.Path.iterdir", side_effect=PermissionError("mocked permission error")):
            result = _find_platform_lib_subdir()
            assert result == ""

def test_bin_wrappers_resource_permission_error():
    with patch("pathlib.Path.iterdir", side_effect=PermissionError("mocked permission error")):
        result = BinWrappersResource.patch_build_time(Path("."), "9.4.8", "@GHC_PREFIX@")
        assert result == 0

def test_package_db_resource_permission_error():
    with patch("pathlib.Path.glob", side_effect=PermissionError("mocked permission error")):
        result = PackageDBResource.patch_build_time(Path("."), "9.4.8", "@GHC_PREFIX@")
        assert result == 0

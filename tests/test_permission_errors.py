import pytest
from unittest.mock import patch
from pathlib import Path
from ghc_compiler_python.wrapper import _find_platform_lib_subdir, BaseResource, PackageDBResource, BinWrappersResource

def test_find_platform_lib_subdir_permission_error():
    with patch("pathlib.Path.is_dir", return_value=True):
        with patch("pathlib.Path.iterdir", side_effect=PermissionError):
            assert _find_platform_lib_subdir() == ""

def test_os_walk_permission_error():
    class TestResource(BaseResource):
        name = "test"
        is_dir = False

    with patch("os.walk", side_effect=PermissionError):
        TestResource.locate.cache_clear()
        assert TestResource.locate() == []

def test_packagedb_glob_permission_error():
    with patch("pathlib.Path.glob", side_effect=PermissionError):
        PackageDBResource.patch_build_time(Path("."), "9.4.8", "@GHC_PREFIX@")

def test_binwrappers_iterdir_permission_error():
    with patch("pathlib.Path.iterdir", side_effect=PermissionError):
        BinWrappersResource.patch_build_time(Path("."), "9.4.8", "@GHC_PREFIX@")

if __name__ == "__main__":
    pytest.main(["test_permission_errors.py"])

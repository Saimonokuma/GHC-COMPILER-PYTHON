import os
from pathlib import Path
from unittest.mock import patch
from ghc_compiler_python.wrapper import BinWrappersResource, _find_platform_lib_subdir, GHC_VERSION

def test_find_platform_lib_subdir_permission_error(tmp_path):
    with patch('sys.prefix', str(tmp_path)):
        lib_dir = tmp_path / 'lib' / f'ghc-{GHC_VERSION}' / 'lib'
        lib_dir.mkdir(parents=True)
        os.chmod(lib_dir, 0o000)
        try:
            assert _find_platform_lib_subdir() == ''
        finally:
            os.chmod(lib_dir, 0o755)

def test_bin_wrappers_patch_build_time_permission_error(tmp_path):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir(parents=True)
    os.chmod(bin_dir, 0o000)
    try:
        assert BinWrappersResource.patch_build_time(bin_dir, GHC_VERSION, '@GHC_PREFIX@') == 0
    finally:
        os.chmod(bin_dir, 0o755)

import os
import pytest
from pathlib import Path
from ghc_compiler_python.wrapper import (
    _find_platform_lib_subdir,
    BinWrappersResource,
    PackageDBResource
)

def test_unreadable_platform_lib_subdir(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.prefix", str(tmp_path))
    lib_dir = tmp_path / "lib" / "ghc-9.4.8" / "lib"
    lib_dir.mkdir(parents=True)
    os.chmod(lib_dir, 0o000)

    try:
        res = _find_platform_lib_subdir()
        assert res == ""
    finally:
        os.chmod(lib_dir, 0o755)

def test_unreadable_bin_wrappers_resource(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    os.chmod(bin_dir, 0o000)

    try:
        res = BinWrappersResource.patch_build_time(bin_dir, "9.4.8", "@GHC_PREFIX@")
        assert res == 0
    finally:
        os.chmod(bin_dir, 0o755)

def test_unreadable_packagedb_resource(tmp_path):
    db_dir = tmp_path / "package.conf.d"
    db_dir.mkdir()
    os.chmod(db_dir, 0o000)

    try:
        res = PackageDBResource.patch_build_time(db_dir, "9.4.8", "@GHC_PREFIX@")
        assert res == 0
    finally:
        os.chmod(db_dir, 0o755)

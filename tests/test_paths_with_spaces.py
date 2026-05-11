import os
import sys
from unittest.mock import patch
from pathlib import Path
from ghc_compiler_python.wrapper import _resolve_runtime_paths

def test_resolve_runtime_paths_with_spaces(tmp_path):
    # create a mock package.conf.d
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    conf_d = lib_dir / "package.conf.d"
    conf_d.mkdir()

    conf_file = conf_d / "test.conf"
    conf_file.write_text("library-dirs: @GHC_PREFIX@/lib/ghc-9.4.8\n")

    # mock sys.prefix to something with spaces
    with patch("sys.prefix", str(tmp_path / "prefix with spaces")):
        with patch("ghc_compiler_python.wrapper.SettingsResource.locate", return_value=[]):
            with patch("ghc_compiler_python.wrapper.PackageDBResource.locate", return_value=[conf_d]):
                with patch("ghc_compiler_python.wrapper.BinWrappersResource.locate", return_value=[]):
                    with patch("ghc_compiler_python.wrapper._rebuild_package_cache"):
                        _resolve_runtime_paths({})

    content = conf_file.read_text()
    assert '"' in content, f"Path with spaces was not quoted: {content}"

with open("tests/test_paths_with_spaces.py", "r") as f:
    content = f.read()

content = content.replace(
"""                    with patch("ghc_compiler_python.wrapper.BinWrappersResource.locate", return_value=[]):
                        with patch("ghc_compiler_python.wrapper._rebuild_package_cache"):
                            _resolve_runtime_paths({"PATH": "/dummy"})""",
"""                    with patch("ghc_compiler_python.wrapper.BinWrappersResource.locate", return_value=[]):
                        with patch("ghc_compiler_python.wrapper._ghc_pkg_recache"):
                            _resolve_runtime_paths({"PATH": "/dummy"})"""
)

with open("tests/test_paths_with_spaces.py", "w") as f:
    f.write(content)

with open("tests/test_wrapper.py", "r") as f:
    content2 = f.read()

content2 = content2.replace(
"""        with patch('ghc_compiler_python.wrapper.SettingsResource.locate', return_value=[]):
            with patch('ghc_compiler_python.wrapper.PackageDBResource.locate', return_value=[]):
                with patch('ghc_compiler_python.wrapper.BinWrappersResource.locate', return_value=[]):
                    with patch('ghc_compiler_python.wrapper._rebuild_package_cache') as mock_rebuild:
                        _resolve_runtime_paths({"PATH": "/usr/bin"})
                        mock_rebuild.assert_not_called()""",
"""        with patch('ghc_compiler_python.wrapper.SettingsResource.locate', return_value=[]):
            with patch('ghc_compiler_python.wrapper.PackageDBResource.locate', return_value=[]):
                with patch('ghc_compiler_python.wrapper.BinWrappersResource.locate', return_value=[]):
                    with patch('ghc_compiler_python.wrapper._ghc_pkg_recache') as mock_rebuild:
                        _resolve_runtime_paths({"PATH": "/usr/bin"})
                        mock_rebuild.assert_not_called()"""
)

with open("tests/test_wrapper.py", "w") as f:
    f.write(content2)

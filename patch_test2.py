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

# the previous substitution didn't match perfectly, let's just do a blanket replace
content = content.replace('with patch("ghc_compiler_python.wrapper._rebuild_package_cache")', 'with patch("ghc_compiler_python.wrapper._ghc_pkg_recache")')

with open("tests/test_paths_with_spaces.py", "w") as f:
    f.write(content)

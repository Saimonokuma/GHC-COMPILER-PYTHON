"""ghc-compiler-python: Native GHC and Cabal packaged as a Python Wheel."""

# The distribution version and the compiler version are separate axes and no
# longer agree. 9.4.8 published a wrapper that rejected every Windows machine
# without a system gcc; PyPI forbids re-uploading a version, so the fix ships
# as 9.4.9. The compiler inside is still GHC 9.4.8 and still says so.
__version__ = "9.6.1"
__ghc_version__ = "9.6.1"
__cabal_version__ = "3.10.3.0"
__author__ = "ghc-compiler-python contributors"
__license__ = "MIT"

__all__ = [
    "__version__",
    "__ghc_version__",
    "__cabal_version__",
]

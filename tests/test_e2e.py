"""End-to-end tests for ghc-compiler-python wheel functionality."""

import subprocess
import sys
import tempfile
import pytest
import shutil
from pathlib import Path


@pytest.fixture
def haskell_source():
    """Create a temporary Haskell source file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".hs", delete=False) as f:
        f.write('module Main where\nmain :: IO ()\nmain = putStrLn "E2E Test Passed"\n')
        f.flush()
        f.close()
        yield f.name
    Path(f.name).unlink()


@pytest.mark.skipif(
    not shutil.which("gcc") and not shutil.which("clang"),
    reason="No C-linker available",
)
@pytest.mark.skipif(
    not (Path(sys.prefix) / "bin" / "ghc-wrapper").exists()
    and not shutil.which("ghc-wrapper"),
    reason="ghc-wrapper not installed in path",
)
class TestGHCWrapper:
    """Tests for ghc-wrapper functionality."""

    def test_ghc_version(self):
        result = subprocess.run(
            ["ghc-wrapper", "--version"], capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_ghc_compilation(self, haskell_source):
        result = subprocess.run(
            ["ghc-wrapper", haskell_source], capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_cabal_version(self):
        result = subprocess.run(
            ["cabal-wrapper", "--version"], capture_output=True, text=True
        )
        assert result.returncode == 0

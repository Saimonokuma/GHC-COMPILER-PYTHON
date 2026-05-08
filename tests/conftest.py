"""
Pytest configuration and fixtures for ghc-compiler-python tests.
Provides:
- Path fixtures for GHC bindist discovery
- Environment isolation (HOME override, PATH injection)
- Temporary directory management
- Mock fixtures for testing without actual GHC installation
"""

import os
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def tmp_ghc_home(tmp_path: Path) -> Path:
    """Isolated HOME directory for GHC tests (prevents ~/.ghc pollution)."""
    home = tmp_path / "ghc_home"
    home.mkdir()
    return home


@pytest.fixture
def ghc_bindist(tmp_path: Path) -> Path:
    """Temporary ghc-bindist directory structure for testing."""
    bindist = tmp_path / "ghc-bindist"
    bindist.mkdir()
    (bindist / "bin").mkdir()
    (bindist / "lib").mkdir()
    (bindist / "settings").mkdir()
    return bindist


@pytest.fixture
def mock_ghc_env(tmp_ghc_home: Path, ghc_bindist: Path) -> dict:
    """Mock environment with HOME override and PATH injection."""
    env = os.environ.copy()
    env["HOME"] = str(tmp_ghc_home)
    env["PATH"] = f"{ghc_bindist / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    env["GHC_PACKAGE_PATH"] = ""
    return env


@pytest.fixture
def clean_ghc_env(tmp_ghc_home: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """
    Provides a clean environment for GHC tests.
    Sets HOME to tmp, clears GHC pollution vars, restores after test using monkeypatch.
    """
    pollution_vars = [
        "GHC_PACKAGE_PATH",
        "GHC_ENVIRONMENT",
        "CABAL_DIR",
        "CABAL_CONFIG",
        "HASKELL_DIST_DIR",
        "HASKELL_PACKAGE_SANDBOX",
        "HASKELL_PACKAGE_SANDBOXES",
        "STACK_ROOT",
        "STACK_YAML",
        "GHCRTS",
        "GHCRTS_OPTS",
    ]

    monkeypatch.setenv("HOME", str(tmp_ghc_home))

    for var in pollution_vars:
        monkeypatch.delenv(var, raising=False)

    return os.environ.copy()


@pytest.fixture
def project_root() -> Path:
    """Root directory of the project (where pyproject.toml lives)."""
    return Path(__file__).resolve().parent.parent

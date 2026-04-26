"""
Subprocess proxy wrappers for GHC and Cabal binaries.

Provides hermetic execution isolation, environment sterilization,
pre-flight C-linker validation, and process proxying.
"""

import os
import sys
import shutil
import subprocess
import signal
from typing import List, NoReturn, Optional

GHC_VERSION = "9.4.8"
CABAL_VERSION = "3.10.3.0"

# Environment variables that MUST be purged to prevent host contamination
HASKELL_POLLUTION_VARS = frozenset({
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
})

_HOME_ORIGINAL: Optional[str] = None


def _resolve_binary(name: str) -> str:
	"""Resolve absolute path to a bundled native binary."""
	binary_name = f"{name}.exe" if sys.platform == "win32" else name

	# Strategy 1: PATH resolution
	resolved = shutil.which(binary_name)
	if resolved:
		return resolved

	# Strategy 2: sys.prefix fallback
	bin_dir = "Scripts" if sys.platform == "win32" else "bin"
	fallback_path = os.path.join(sys.prefix, bin_dir, binary_name)
	if os.path.exists(fallback_path):
		return fallback_path

	# Strategy 3: Package-relative fallback
	package_dir = os.path.dirname(os.path.abspath(__file__))
	env_bin = os.path.join(os.path.dirname(package_dir), bin_dir, binary_name)
	if os.path.exists(env_bin):
		return env_bin

	sys.stderr.write(
		f"FATAL ERROR: Bundled binary '{binary_name}' not found.\n"
		f"Searched: PATH, {fallback_path}, {env_bin}\n"
	)
	sys.exit(1)


def _validate_c_linker() -> None:
	"""Assert existence of a host C-linker (gcc or clang)."""
	if not shutil.which("gcc") and not shutil.which("clang"):
		sys.stderr.write(
			"FATAL ERROR: GHC requires a host C-linker.\n"
			"Install 'gcc' or 'clang' and ensure it is in PATH.\n"
			"  Ubuntu/Debian: sudo apt-get install gcc\n"
			"  macOS: xcode-select --install\n"
			"  Windows: Install MinGW-w64 or MSYS2\n"
		)
		sys.exit(1)


def _sterilize_environment() -> dict:
	"""Create a sterilized subprocess environment."""
	global _HOME_ORIGINAL
	env = os.environ.copy()

	# Purge Haskell pollution
	for var in HASKELL_POLLUTION_VARS:
		env.pop(var, None)

	# Override HOME to prevent reading ~/.ghc/ and ~/.cabal/
	_HOME_ORIGINAL = env.get("HOME", env.get("USERPROFILE", ""))
	safe_home = os.path.join(sys.prefix, ".ghc-compiler-python-home")
	os.makedirs(safe_home, exist_ok=True)
	env["HOME"] = safe_home

	# Ensure bundled binaries are FIRST on PATH
	bin_dir = "Scripts" if sys.platform == "win32" else "bin"
	env_bin = os.path.join(sys.prefix, bin_dir)
	env["PATH"] = f"{env_bin}{os.pathsep}{env.get('PATH', '')}"

	return env


def _handle_sigterm(signum: int, frame) -> None:
	sys.exit(128 + signum)


def _handle_sigint(signum: int, frame) -> None:
	sys.exit(130)


def _execute_tool(tool_name: str, extra_args: List[str] = None) -> NoReturn:
	"""Generic subprocess proxy for bundled Haskell tooling."""
	signal.signal(signal.SIGTERM, _handle_sigterm)
	signal.signal(signal.SIGINT, _handle_sigint)

	_validate_c_linker()
	env = _sterilize_environment()
	binary_path = _resolve_binary(tool_name)

	cmd = [binary_path]
	if extra_args:
		cmd.extend(extra_args)
	cmd.extend(sys.argv[1:])

	try:
		result = subprocess.run(cmd, env=env)
		sys.exit(result.returncode)
	except FileNotFoundError:
		sys.stderr.write(f"FATAL ERROR: Binary not found at '{binary_path}'.\n")
		sys.exit(1)
	except PermissionError:
		sys.stderr.write(f"FATAL ERROR: Permission denied executing '{binary_path}'.\n")
		sys.exit(126)
	except KeyboardInterrupt:
		sys.exit(130)
	except Exception as e:
		sys.stderr.write(f"FATAL ERROR: Subprocess exception: {e}\n")
		sys.exit(1)


def execute_ghc() -> NoReturn:
	"""ghc-wrapper — isolated GHC compilation proxy."""
	_execute_tool("ghc", extra_args=["-v0"])


def execute_ghci() -> NoReturn:
	"""ghci-wrapper — isolated GHCi interactive proxy."""
	_execute_tool("ghci")


def execute_cabal() -> NoReturn:
	"""cabal-wrapper — isolated Cabal build tool proxy."""
	_execute_tool("cabal")

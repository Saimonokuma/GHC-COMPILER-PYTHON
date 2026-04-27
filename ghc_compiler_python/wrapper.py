# ghc_compiler_python/wrapper.py
"""
Subprocess proxy wrappers for GHC and Cabal binaries.

Provides hermetic execution isolation, environment sterilization,
pre-flight C-linker validation, runtime path resolution, and process proxying.

FIX v2: Added DYLD_LIBRARY_PATH for macOS runtime library resolution.
"""

import os
import sys
import shutil
import subprocess
import signal
from typing import List, NoReturn, Optional


GHC_VERSION = "9.4.8"
CABAL_VERSION = "3.10.3.0"

HASKELL_POLLUTION_VARS: List[str] = [
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
	"HEAPSIZE",
	"HOME",
]

_HOME_ORIGINAL: Optional[str] = None


def _resolve_binary(name: str) -> str:
	"""Resolve the absolute path to a bundled native binary."""
	binary_name = f"{name}.exe" if sys.platform == "win32" else name

	resolved = shutil.which(binary_name)
	if resolved:
		return resolved

	bin_dir = "Scripts" if sys.platform == "win32" else "bin"
	fallback_path = os.path.join(sys.prefix, bin_dir, binary_name)

	if os.path.exists(fallback_path):
		return fallback_path

	package_dir = os.path.dirname(os.path.abspath(__file__))
	env_bin = os.path.join(os.path.dirname(package_dir), bin_dir, binary_name)
	if os.path.exists(env_bin):
		return env_bin

	sys.stderr.write(
		f"FATAL ERROR: Bundled compiler binary '{binary_name}' could not be located.\n"
	)
	sys.exit(1)


def _validate_c_linker() -> None:
	"""Pre-flight validation: assert the existence of a host C-linker."""
	if not shutil.which("gcc") and not shutil.which("clang"):
		sys.stderr.write(
			"FATAL ERROR: The GHC compiler requires a host C-linker (gcc or clang).\n"
		)
		sys.exit(1)


def _sterilize_environment() -> dict:
	"""Create a sterilized subprocess environment."""
	global _HOME_ORIGINAL
	env = os.environ.copy()

	for var in HASKELL_POLLUTION_VARS:
		env.pop(var, None)

	_HOME_ORIGINAL = env.get("HOME", env.get("USERPROFILE", ""))
	safe_home = os.path.join(sys.prefix, ".ghc-compiler-python-home")
	os.makedirs(safe_home, exist_ok=True)
	env["HOME"] = safe_home

	bin_dir = "Scripts" if sys.platform == "win32" else "bin"
	env_bin = os.path.join(sys.prefix, bin_dir)
	current_path = env.get("PATH", "")
	env["PATH"] = f"{env_bin}{os.pathsep}{current_path}"

	# FIX v2: Set DYLD_LIBRARY_PATH on macOS for runtime library resolution
	if sys.platform == "darwin":
		lib_dir = os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}")
		if os.path.isdir(lib_dir):
			existing_dyld = env.get("DYLD_LIBRARY_PATH", "")
			if existing_dyld:
				env["DYLD_LIBRARY_PATH"] = f"{lib_dir}{os.pathsep}{existing_dyld}"
			else:
				env["DYLD_LIBRARY_PATH"] = lib_dir

	return env


def _resolve_runtime_paths() -> None:
	"""Dynamically replace @GHC_PREFIX@ with the active sys.prefix at runtime."""
	lib_dir = os.path.join(sys.prefix, "lib", f"ghc-{GHC_VERSION}")

	targets = []
	settings_file = os.path.join(lib_dir, "settings")
	if os.path.exists(settings_file):
		targets.append(settings_file)

	pkg_db = os.path.join(lib_dir, "package.conf.d")
	if os.path.exists(pkg_db):
		targets.extend(
			os.path.join(pkg_db, f)
			for f in os.listdir(pkg_db)
			if f.endswith(".conf")
		)

	# FIX v2: Also check root-level package.conf.d (Windows layout)
	root_pkg_db = os.path.join(sys.prefix, "package.conf.d")
	if os.path.exists(root_pkg_db):
		targets.extend(
			os.path.join(root_pkg_db, f)
			for f in os.listdir(root_pkg_db)
			if f.endswith(".conf")
		)

	for target in targets:
		try:
			with open(target, "r", encoding="utf-8") as f:
				content = f.read()
			if "@GHC_PREFIX@" in content:
				prefix_clean = sys.prefix.replace("\\", "/")
				content = content.replace("@GHC_PREFIX@", prefix_clean)
				with open(target, "w", encoding="utf-8") as f:
					f.write(content)
		except Exception:
			pass  # Ignore read-only files if already patched


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
	_resolve_runtime_paths()
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
	except KeyboardInterrupt:
		sys.exit(130)
	except Exception as e:
		sys.stderr.write(f"FATAL ERROR: Subprocess proxy exception: {e}\n")
		sys.exit(1)


def execute_ghc() -> NoReturn:
	_execute_tool("ghc", extra_args=["-v0"])


def execute_ghci() -> NoReturn:
	_execute_tool("ghci")


def execute_cabal() -> NoReturn:
	_execute_tool("cabal")
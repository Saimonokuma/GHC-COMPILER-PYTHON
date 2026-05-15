import os
import re

with open("ghc_compiler_python/wrapper.py", "r") as f:
    content = f.read()

# 1. Optimize environment sterilization
content = content.replace(
"""    env = os.environ.copy()

    _HOME_ORIGINAL = env.get("HOME", env.get("USERPROFILE", ""))

    for var in HASKELL_POLLUTION_VARS:
        env.pop(var, None)""",
"""    env = {k: v for k, v in os.environ.items() if k not in HASKELL_POLLUTION_VARS}

    _HOME_ORIGINAL = os.environ.get("HOME", os.environ.get("USERPROFILE", ""))"""
)

old_match = """    # 🧪 Alchemist: Dictionary mapping with lambdas and generators replace verbose if-chains and manual append loops
    # Lambdas are used for lazy evaluation so that platform-specific code doesn't evaluate eagerly.
    platform_config = {
        "darwin": lambda: (
            [
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib",
                Path(sys.prefix) / "lib",
            ],
            ["DYLD_LIBRARY_PATH", "LD_LIBRARY_PATH"],
        ),
        "linux": lambda: (
            [
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}",
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib",
                Path(_find_platform_lib_subdir() or "."),
                Path(__file__).resolve().parent.parent / "ghc_compiler_python.libs",
            ],
            ["LD_LIBRARY_PATH"],
        ),
    }
    candidates, vars_to_update = platform_config.get(sys.platform, lambda: ([], []))()"""

new_match = """    # 🧪 Alchemist: Structural pattern matching replaces lambda-based dictionary lookup
    match sys.platform:
        case "darwin":
            candidates = [
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib",
                Path(sys.prefix) / "lib",
            ]
            vars_to_update = ["DYLD_LIBRARY_PATH", "LD_LIBRARY_PATH"]
        case "linux":
            candidates = [
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}",
                Path(sys.prefix) / "lib" / f"ghc-{GHC_VERSION}" / "lib",
                Path(_find_platform_lib_subdir() or "."),
                Path(__file__).resolve().parent.parent / "ghc_compiler_python.libs",
            ]
            vars_to_update = ["LD_LIBRARY_PATH"]
        case _:
            candidates, vars_to_update = [], []"""

content = content.replace(old_match, new_match)

with open("ghc_compiler_python/wrapper.py", "w") as f:
    f.write(content)

#!/usr/bin/env python3
"""
Patch GHC paths for relocatability.

Replaces hardcoded absolute paths with @GHC_PREFIX@ placeholders
that will be resolved at runtime by wrapper.py.

FIX v5: Ouroboros Transmutation — The Resource Locator Metaclass.
Replaced 280 lines of procedural path finding and patching logic with a dynamic
iteration over the ResourceMeta registry defined in wrapper.py.
"""

import sys
from pathlib import Path

# Add project root to sys.path to import the wrapper
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ghc_compiler_python.wrapper import BaseResource, GHC_VERSION

PLACEHOLDER_PREFIX = "@GHC_PREFIX@"
STAGING_DIR = Path("ghc-bindist")

def main():
    if not STAGING_DIR.exists():
        print("Staging directory not found, skipping path patching.")
        return 1

    total_patched = 0

    # 🐍 Ouroboros: The Engine
    # Iterate over every registered resource (Settings, PackageDB, BinWrappers)
    # and call its polymorphic patch_build_time method.
    for resource_cls in BaseResource.registry:
        print(f"\n--- Processing {resource_cls.name} ---")
        found_paths = resource_cls.locate(base=str(STAGING_DIR), version=GHC_VERSION)

        if not found_paths:
            print(f"WARNING: Resource '{resource_cls.name}' not found in expected locations.")
            continue

        for path in found_paths:
            print(f"Found {resource_cls.name} at: {path}")
            patched_count = resource_cls.patch_build_time(path, GHC_VERSION, PLACEHOLDER_PREFIX)

            if patched_count > 0:
                print(f"Successfully patched {patched_count} items in {resource_cls.name}")
                total_patched += patched_count
            else:
                print(f"No patching required for {resource_cls.name} at {path}")

    print(f"\nTotal resources patched: {total_patched}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

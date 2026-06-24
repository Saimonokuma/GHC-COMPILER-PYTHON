#!/usr/bin/env python3
"""
Patch GHC paths for relocatability.
Moved all build-time patching logic here, out of the runtime wrapper.
"""
import sys, re
from pathlib import Path

GHC_VERSION = "9.4.8"
PLACEHOLDER = "@GHC_PREFIX@"
STAGING_DIR = Path("ghc-bindist")

def _is_text_file(filepath: Path) -> bool:
    try:
        with filepath.open("rb") as f: return b"\0" not in f.read(1024)
    except OSError: return False

def patch_settings():
    for p in [STAGING_DIR / "lib" / f"ghc-{GHC_VERSION}" / "lib" / "settings", STAGING_DIR / "lib" / "settings", STAGING_DIR / "settings"]:
        if p.exists():
            content = p.read_text(encoding="utf-8", errors="replace")
            pattern = re.compile(r"/(?:usr/local/lib|usr/lib|opt|ghc-prefix)/ghc(?:-|/)" + re.escape(GHC_VERSION) + r"|/ghc-prefix")
            new_content = pattern.sub(lambda m: PLACEHOLDER if m.group(0) == "/ghc-prefix" else f"{PLACEHOLDER}/lib/ghc-{GHC_VERSION}", content)
            if new_content != content: p.write_text(new_content, encoding="utf-8"); return 1
    return 0

def patch_package_db():
    patched = 0
    for db in [STAGING_DIR / "lib" / f"ghc-{GHC_VERSION}" / "lib" / "package.conf.d", STAGING_DIR / "lib" / "package.conf.d", STAGING_DIR / "package.conf.d"]:
        if not db.exists(): continue
        for conf in db.glob("*.conf"):
            content = conf.read_text(encoding="utf-8", errors="replace")
            pattern = re.compile(r"(dynamic-library-dirs:\s*|library-dirs:\s*|include-dirs:\s*)/[^\s]+|/ghc-prefix/lib/ghc-" + re.escape(GHC_VERSION) + r"|/ghc-prefix")
            def repl(m):
                g1 = m.group(1)
                if g1: return f"{g1}{PLACEHOLDER}/lib/ghc-{GHC_VERSION}{'/include' if 'include' in g1 else ''}"
                return PLACEHOLDER if m.group(0) == "/ghc-prefix" else f"{PLACEHOLDER}/lib/ghc-{GHC_VERSION}"
            new_content = pattern.sub(repl, content)
            if new_content != content: conf.write_text(new_content, encoding="utf-8"); patched += 1
        (db / "package.cache").unlink(missing_ok=True)
    return patched

def patch_bin_wrappers():
    patched = 0
    for bin_dir in [STAGING_DIR / ("Scripts" if sys.platform == "win32" else "bin"), STAGING_DIR / "lib" / f"ghc-{GHC_VERSION}" / "bin", STAGING_DIR / "bin", STAGING_DIR / "lib" / "bin"]:
        if not bin_dir.exists(): continue
        for script in bin_dir.iterdir():
            if not script.is_file() or script.is_symlink() or script.name.endswith(".exe") or not _is_text_file(script): continue
            content = script.read_text(encoding="utf-8", errors="replace")
            staging_abs = bin_dir.parent.parent.absolute().as_posix() if bin_dir.parent.name == f"ghc-{GHC_VERSION}" else bin_dir.parent.absolute().as_posix()
            pattern = re.compile(r"/usr/local/lib/ghc-" + re.escape(GHC_VERSION) + r"|/ghc-prefix|" + re.escape(staging_abs) + r"|" + re.escape(staging_abs.replace("/", "\\")))
            new_content = pattern.sub(lambda m: f"{PLACEHOLDER}/lib/ghc-{GHC_VERSION}" if m.group(0).startswith(f"/usr/local/lib/ghc-{GHC_VERSION}") else PLACEHOLDER, content)
            if new_content != content: script.write_text(new_content, encoding="utf-8"); patched += 1
    return patched

def main():
    if not STAGING_DIR.exists(): return 1
    print(f"Patched {patch_settings()} settings files.")
    print(f"Patched {patch_package_db()} package DBs.")
    print(f"Patched {patch_bin_wrappers()} bin wrappers.")
    return 0

if __name__ == "__main__": sys.exit(main())

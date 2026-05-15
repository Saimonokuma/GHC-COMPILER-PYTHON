with open("ghc_compiler_python/wrapper.py", "r") as f:
    content = f.read()

old_code = """        cache_file = path / "package.cache"
        if cache_file.exists():
            try:
                cache_file.unlink()
            except OSError as e:
                sys.stderr.write(f"WARNING: Failed to unlink {cache_file}: {e}\\n")
        return patched_count"""

new_code = """        # 🧪 Alchemist: Walrus operator (:=) consolidates variable assignment and existence check
        if (cache_file := path / "package.cache").exists():
            try:
                cache_file.unlink()
            except OSError as e:
                sys.stderr.write(f"WARNING: Failed to unlink {cache_file}: {e}\\n")
        return patched_count"""

content = content.replace(old_code, new_code)

with open("ghc_compiler_python/wrapper.py", "w") as f:
    f.write(content)

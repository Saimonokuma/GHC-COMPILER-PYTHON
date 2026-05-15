with open("ghc_compiler_python/wrapper.py", "r") as f:
    content = f.read()

old_recache = """        # 🧪 Alchemist: Dictionary unpacking replaces manual environment copying and mutation
        subprocess.run(
            [ghc_pkg, "recache", "--package-db", pkg_db_dir],
            env={**env, "GHC_PACKAGE_PATH": pkg_db_dir},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )"""

new_recache = """        # 🧪 Alchemist: Dictionary merge operator (|) replaces unpacking
        subprocess.run(
            [ghc_pkg, "recache", "--package-db", pkg_db_dir],
            env=env | {"GHC_PACKAGE_PATH": pkg_db_dir},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )"""

content = content.replace(old_recache, new_recache)

with open("ghc_compiler_python/wrapper.py", "w") as f:
    f.write(content)

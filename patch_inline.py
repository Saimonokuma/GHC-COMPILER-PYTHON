with open("ghc_compiler_python/wrapper.py", "r") as f:
    content = f.read()

old_resolve = """    # 🧪 Alchemist: any() replaces manual flag variables and loops for succinct boolean reduction
    if patched_any_conf or any(
        not (pkg_db / "package.cache").exists()
        for pkg_db in PackageDBResource.locate()
    ):
        _rebuild_package_cache(env)


def _rebuild_package_cache(env: dict) -> None:
    \"\"\"Run ghc-pkg recache to regenerate package.cache.

    GHC requires package.cache to function properly. The build process
    deletes it after patching .conf files, so we must regenerate it
    at runtime after @GHC_PREFIX@ replacement.

    Args:
            env: The sterilized environment dict with proper LD_LIBRARY_PATH set.
    \"\"\"
    for pkg_db in PackageDBResource.locate():
        _ghc_pkg_recache(str(pkg_db), env)


def _ghc_pkg_recache(pkg_db_dir: str, env: dict) -> None:"""

new_resolve = """    # 🧪 Alchemist: any() replaces manual flag variables and loops for succinct boolean reduction
    if patched_any_conf or any(
        not (pkg_db / "package.cache").exists()
        for pkg_db in PackageDBResource.locate()
    ):
        [_ghc_pkg_recache(str(pkg_db), env) for pkg_db in PackageDBResource.locate()]


def _ghc_pkg_recache(pkg_db_dir: str, env: dict) -> None:"""

content = content.replace(old_resolve, new_resolve)

with open("ghc_compiler_python/wrapper.py", "w") as f:
    f.write(content)

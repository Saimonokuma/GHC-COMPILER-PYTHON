import os
import sys
import shutil
import subprocess

def execute_ghc():
    """
    Primary entry point for the ghc-wrapper console script.
    Provides execution isolation, environment sterilization, and pre-flight
    validation for the native GHC binary subprocess.
    """
    # 1. Isolate and sterilize the execution environment
    env = os.environ.copy()
    haskell_pollution_vars = [
        "GHC_PACKAGE_PATH",
        "GHC_ENVIRONMENT",
        "CABAL_DIR",
        "CABAL_CONFIG"
    ]
    for var in haskell_pollution_vars:
        env.pop(var, None)

    # 2. Execute Pre-flight validation for Host C-Linker dependency
    # GHC requires a native system linker to finalize binary compilation
    if not shutil.which('gcc') and not shutil.which('clang'):
        sys.stderr.write("FATAL ERROR: The GHC compiler requires a host C-linker.\n")
        sys.stderr.write("Please install 'gcc' or 'clang' and ensure it is available in the system PATH.\n")
        sys.exit(1)

    # 3. Resolve the path to the bundled native GHC binary
    # The binary is placed in the active environment's bin/Scripts path via PEP 427.data/scripts
    binary_target = 'ghc.exe' if sys.platform == 'win32' else 'ghc'
    ghc_bin_path = shutil.which(binary_target)

    if not ghc_bin_path:
        # Fallback heuristic: absolute path resolution based on sys.prefix
        bin_dir = 'Scripts' if sys.platform == 'win32' else 'bin'
        fallback_path = os.path.join(sys.prefix, bin_dir, binary_target)
        if os.path.exists(fallback_path):
            ghc_bin_path = fallback_path
        else:
            fallback_path = os.path.join(sys.prefix, 'local', bin_dir, binary_target)
            if os.path.exists(fallback_path):
                ghc_bin_path = fallback_path
            else:
                # Add check for Python user base installs (e.g. CI environments)
                try:
                    import site
                    user_base_path = os.path.join(site.getuserbase(), bin_dir, binary_target)
                    if os.path.exists(user_base_path):
                        ghc_bin_path = user_base_path
                except Exception:
                    pass

                if not ghc_bin_path:
                    sys.stderr.write(f"FATAL ERROR: Bundled compiler binary '{binary_target}' could not be located.\n")
                    sys.stderr.write(f"Search attempted in sys.prefix ({sys.prefix}) and user base.\n")
                    sys.exit(1)

    scripts_dir = os.path.dirname(ghc_bin_path)

    # Resolve settings file context missing from macOS wheel execution
    if sys.platform != 'win32':
        settings_dir = None
        for base in [os.path.join(scripts_dir, '..'), os.path.join(sys.prefix, 'data')]:
            lib_path = os.path.join(base, 'lib')
            if os.path.exists(lib_path):
                for folder in os.listdir(lib_path):
                    if 'ghc-' in folder:
                        potential_settings = os.path.join(lib_path, folder, 'settings')
                        if os.path.exists(potential_settings):
                            settings_dir = os.path.abspath(os.path.dirname(potential_settings))
                            break
                if settings_dir:
                    break

        if settings_dir:
            cmd_args = ['-B' + settings_dir]
            env['GHC_LIBDIR'] = settings_dir
        else:
            cmd_args = []

    if sys.platform == 'win32':
        # On Windows, GHC expects its tools in the same directory or a predictable relative path
        # If ghc-wrapper is executed directly from a Python path, we might need to manually
        # enforce the libdir or just add the Scripts directory explicitly to the PATH.

        path_additions = []

        # Manually crawl up looking for mingw/bin
        current = scripts_dir
        for _ in range(6):
            potential = os.path.join(current, 'mingw', 'bin')
            if os.path.exists(potential):
                path_additions.append(os.path.abspath(potential))
            potential_lib = os.path.join(current, 'lib', 'mingw', 'bin')
            if os.path.exists(potential_lib):
                path_additions.append(os.path.abspath(potential_lib))
            potential_data = os.path.join(current, 'data', 'mingw', 'bin')
            if os.path.exists(potential_data):
                path_additions.append(os.path.abspath(potential_data))
            potential_site = os.path.join(current, 'Lib', 'site-packages', 'mingw', 'bin')
            if os.path.exists(potential_site):
                path_additions.append(os.path.abspath(potential_site))
            current = os.path.dirname(current)

        if path_additions:
            env['PATH'] = ";".join(path_additions) + ";" + env.get('PATH', '')

    # 4. Proxy subprocess execution
    # Forcing -v0 ensures GHC remains quiet by default during automated pipelines
    if sys.platform != 'win32':
        cmd = [ghc_bin_path] + cmd_args + ['-v0'] + sys.argv[1:]
    else:
        cmd = [ghc_bin_path, '-v0'] + sys.argv[1:]

    try:
        # Execute the compiler in the sanitized subprocess environment
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        # Gracefully handle SIGINT from the user
        sys.exit(130)
    except Exception as e:
        sys.stderr.write(f"FATAL ERROR: Subprocess proxy exception: {str(e)}\n")
        sys.exit(1)

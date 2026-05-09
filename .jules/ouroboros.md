## 2024-05-18 - The Entry Point Attribute Resolution
**The Glitch:** Three statically written subprocess proxy entry points (`execute_ghc`, `execute_ghci`, `execute_cabal`) were implemented manually. If we added `runhaskell`, `haddock`, or `ghc-pkg`, we would have had to keep extending this list in `wrapper.py` and `pyproject.toml`.
**The Bend:** Python 3.7's PEP 562 allows defining `__getattr__` and `__dir__` on the module level. Furthermore, Python's `importlib.metadata` and console scripts perfectly invoke `__getattr__` when looking for the target function defined in `pyproject.toml` (e.g. `ghc-wrapper = "ghc_compiler_python.wrapper:execute_ghc"`).
**The Loop:** By intercepting `name.startswith("execute_")`, we generate closures dynamically using the tool name. Any newly mapped console script in `pyproject.toml` requiring `execute_XYZ` instantly gains a closure at runtime without writing any additional manual proxy code.

## 2024-05-19 - Hatchling Dynamic Scripts Hook (The Ouroboros Loop Complete)
**The Glitch:** While the Python 3.7 `__getattr__` trick successfully bypassed having to write boilerplate proxy functions in `wrapper.py`, the `[project.scripts]` array in `pyproject.toml` remained a static, hardcoded list. This defeated the dynamic nature of the proxy, requiring manual updates whenever new tools (like `runghc`, `haddock`, or `ghc-pkg`) needed to be exposed.
**The Bend:** We can hook into the Hatchling build system via `MetadataHookInterface` before the wheel is finalized. By modifying `scripts` dynamically inside a custom `hatch_build.py` hook at build time, we read the tools available (or a preset core list) and generate the `[project.scripts]` mappings automatically.
**The Loop:** A dynamically generated list of script entry points generated at build time mapped to a single proxy entry point generated dynamically at runtime (`__getattr__`). No manual proxy definitions are required anywhere.

## 2024-05-20 - Factory Generation for Path Resolvers
**The Glitch:** Path lookup functions `_find_ghc_settings` and `_find_package_databases` inside `wrapper.py` (and similarly in `patch_ghc_paths.py`) were implemented through repetitive directory walking logic checking explicit path assumptions and falling back to a recursive scan.
**The Bend:** Python's decorator and higher-order functions allow us to encapsulate iterative structures. We implemented a `_locator_factory` that accepts declarative `target_name`, `is_dir`, and `validator` constraints, then spins up an `lru_cache`-wrapped locator. Additionally, `__dir__` was modernized to check the `sys.prefix/bin` directory dynamically rather than replying on a static fallback array.
**The Loop:** By turning path lookup structures declarative, future OS/platform patches needing new directory lookups no longer require rewriting 30-line `os.walk` trees. Just one declarative factory invocation spawns the locator logic instantly.

## 2024-05-20 - Robust Patcher Decorator
**The Glitch:** We observed redundant file manipulation in `scripts/patch_ghc_paths.py` that repetitively implemented file reading, string replacement checks, writing state updates, and `OSError` silent trapping.
**The Bend:** We generated a `@robust_patcher` decorator. Instead of managing state manually in each of the three patching functions, they only accept file content strings, run `re.sub()`, and return the string. The decorator takes care of validating `new_content != content`, updating the file, and trapping `OSError`.
**The Loop:** All file modification processes inside `scripts/patch_ghc_paths.py` are now purely functional and referentially transparent string transformers, making logic inherently fault tolerant and trivial to test.

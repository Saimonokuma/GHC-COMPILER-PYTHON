## 2024-05-18 - The Entry Point Attribute Resolution
**The Glitch:** Three statically written subprocess proxy entry points (`execute_ghc`, `execute_ghci`, `execute_cabal`) were implemented manually. If we added `runhaskell`, `haddock`, or `ghc-pkg`, we would have had to keep extending this list in `wrapper.py` and `pyproject.toml`.
**The Bend:** Python 3.7's PEP 562 allows defining `__getattr__` and `__dir__` on the module level. Furthermore, Python's `importlib.metadata` and console scripts perfectly invoke `__getattr__` when looking for the target function defined in `pyproject.toml` (e.g. `ghc-wrapper = "ghc_compiler_python.wrapper:execute_ghc"`).
**The Loop:** By intercepting `name.startswith("execute_")`, we generate closures dynamically using the tool name. Any newly mapped console script in `pyproject.toml` requiring `execute_XYZ` instantly gains a closure at runtime without writing any additional manual proxy code.

## 2024-05-19 - Hatchling Dynamic Scripts Hook (The Ouroboros Loop Complete)
**The Glitch:** While the Python 3.7 `__getattr__` trick successfully bypassed having to write boilerplate proxy functions in `wrapper.py`, the `[project.scripts]` array in `pyproject.toml` remained a static, hardcoded list. This defeated the dynamic nature of the proxy, requiring manual updates whenever new tools (like `runghc`, `haddock`, or `ghc-pkg`) needed to be exposed.
**The Bend:** We can hook into the Hatchling build system via `MetadataHookInterface` before the wheel is finalized. By modifying `scripts` dynamically inside a custom `hatch_build.py` hook at build time, we read the tools available (or a preset core list) and generate the `[project.scripts]` mappings automatically.
**The Loop:** A dynamically generated list of script entry points generated at build time mapped to a single proxy entry point generated dynamically at runtime (`__getattr__`). No manual proxy definitions are required anywhere.

## 2024-05-20 - The Resource Locator Metaclass
**The Glitch:** Procedural path discovery code was duplicated in both `wrapper.py` (runtime) and `scripts/patch_ghc_paths.py` (build time). We had verbose procedural logic with ~280 lines across multiple search loops just to locate and patch `settings`, `package.conf.d`, and `bin/*`.
**The Bend:** We abstracted the path finding and patching logic into `BaseResource` subclasses registered automatically via `ResourceMeta`. This unifies platform-specific directory structure paths.
**The Loop:** A polymorphic `patch_build_time` at build time and `locate` at runtime dynamic invocation. Any new GHC resource type needing relocation just subclasses `BaseResource` and specifies its candidates. Boilerplate eliminated entirely.

## 2024-05-20 - Python Pipeline Generator for GitHub Actions
**The Glitch:** The GitHub Actions workflow (`.github/workflows/build.yml`) was using a matrix strategy, leading to excessive `if: runner.os == '...'` conditional statements scattered throughout the steps. This YAML boilerplate made the pipeline hard to read and maintain, acting as a rigid static structure.
**The Bend:** We implemented a Python pipeline generator (`scripts/generate_workflow.py`) that compiles a Python-based pipeline definition into a static, unrolled YAML workflow. This explicitly generates platform-specific jobs (linux, macos, windows) without the need for conditional logic within the steps.
**The Loop:** A dynamic Python configuration source generates a static, clean YAML file. Any new pipeline variations or steps can be added via code logic rather than error-prone YAML conditionals. This resulted in a 3:1 compression ratio in logical flow complexity.

## 2024-05-06 - Avoid unconditional sub-process invocation in wrappers
**Learning:** In the `ghc_compiler_python` wrapper, `_resolve_runtime_paths` originally rebuilt the GHC package cache via `ghc-pkg recache` on *every* invocation. Since wrappers are called frequently (for `ghc`, `ghci`, `cabal`), this ~200ms overhead adds up.
**Action:** When performing initial setup/patching (like replacing `@GHC_PREFIX@`), track if any actual modifications occurred to `.conf` files and conditionally rebuild the cache only if changes were made.

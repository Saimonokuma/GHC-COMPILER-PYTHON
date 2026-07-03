## Pending Optimizations
- Continue profiling `cabal` and `ghc` wrapper proxies to find any remaining CPU or I/O bottlenecks.
- Check if recursive tree walking in `scripts/patch_ghc_paths.py` can be heavily parallelized or optimized.
- Optimize the test suite execution time if there are significant delays.

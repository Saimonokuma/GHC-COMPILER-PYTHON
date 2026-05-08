## REPO CONTEXT (Last updated: 2024-05-06)
**Project:** ghc-compiler-python | **Languages:** Python, Bash | **Build/Test/Lint:** hatch, pytest
**Known Bug Patterns:** Missing trap cleanups, unhandled OS failures in wrappers, paths with spaces
**Fixed Bugs:** Wrapper crashed on read-only sys.prefix, shell script trap cleanup missing.

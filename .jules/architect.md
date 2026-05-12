## REPO CONTEXT (Last updated: 2024-05-12)
**Project:** ghc-compiler-python
**Languages:** Python, Bash
**Build:** hatchling (pep 621, 427) via pyproject.toml
**Test:** uv run pytest
**Lint:** None configured yet
**Docs:** DEPLOYMENT_OPERATIVE_PLAN.md, README.md
**Key Conventions:** Uses subprocess proxies to call GHC correctly, with env overrides and dynamically resolving prefix directories. Uses pathlib where possible.

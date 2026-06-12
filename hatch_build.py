from hatchling.metadata.plugin.interface import MetadataHookInterface
from pathlib import Path

class CustomMetadataHook(MetadataHookInterface):
    def update(self, metadata: dict) -> None:
        """
        Dynamically generates console_scripts entry points for all Haskell tools.
        Eliminates the need to manually update pyproject.toml every time a new
        binary is added to the toolchain.
        """
        # 🧪 Alchemist: Set operations and comprehensions compress dynamic tool registration
        core_tools = {
            "ghc", "ghci", "cabal", "runghc", "runhaskell",
            "haddock", "ghc-pkg", "hsc2hs", "hp2ps", "hpc"
        }

        if (bindist_bin := Path("ghc-bindist/bin")).is_dir():
            core_tools |= {p.stem if p.name.endswith(".exe") else p.name for p in bindist_bin.iterdir() if p.is_file()}

        metadata.setdefault("scripts", {}).update({
            f"{tool}-wrapper": f"ghc_compiler_python.wrapper:execute_{tool.replace('-', '_')}"
            for tool in core_tools
        })

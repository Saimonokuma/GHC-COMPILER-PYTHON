from hatchling.metadata.plugin.interface import MetadataHookInterface
from pathlib import Path

class CustomMetadataHook(MetadataHookInterface):
    def update(self, metadata: dict) -> None:
        """
        Dynamically generates console_scripts entry points for all Haskell tools.
        Eliminates the need to manually update pyproject.toml every time a new
        binary is added to the toolchain.
        """
        scripts = metadata.get("scripts", {})

        # Base tools that are standard for GHC/Cabal
        core_tools = [
            "ghc", "ghci", "cabal", "runghc", "runhaskell",
            "haddock", "ghc-pkg", "hsc2hs", "hp2ps", "hpc"
        ]

        # In case we have downloaded binaries locally during build
        bindist_bin = Path("ghc-bindist/bin")
        if bindist_bin.exists() and bindist_bin.is_dir():
            for p in bindist_bin.iterdir():
                if p.is_file():
                    name = p.stem if p.name.endswith(".exe") else p.name
                    if name not in core_tools:
                        core_tools.append(name)

        for tool in core_tools:
            wrapper_name = f"{tool}-wrapper"
            # Python attributes can't have hyphens
            func_name = f"execute_{tool.replace('-', '_')}"
            scripts[wrapper_name] = f"ghc_compiler_python.wrapper:{func_name}"

        metadata["scripts"] = scripts

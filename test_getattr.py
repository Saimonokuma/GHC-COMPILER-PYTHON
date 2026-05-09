import sys
from typing import NoReturn, Optional, List, Any

def _execute_tool(tool_name: str, extra_args: Optional[List[str]] = None) -> NoReturn:
    print(f"Executing {tool_name} with {extra_args}")
    sys.exit(0)

def __getattr__(name: str) -> Any:
    if name.startswith("execute_"):
        tool_name = name[8:].replace("_", "-")
        extra_args = ["-v0"] if tool_name == "ghc" else None

        def executor() -> NoReturn:
            _execute_tool(tool_name, extra_args=extra_args)

        executor.__name__ = name
        return executor

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

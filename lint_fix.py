import re
from pathlib import Path

path = Path("ghc_compiler_python/wrapper.py")
content = path.read_text(encoding="utf-8")

# Fix F401 typing.Type unused import
content = content.replace("from typing import Any, List, NoReturn, Optional, Type\n", "from typing import Any, List, NoReturn, Optional\n")

# Fix E302 at line 80 (_resolve_binary)
content = re.sub(r'\n    \)\n\ndef _resolve_binary\(name: str\) -> str:', r'\n    )\n\n\ndef _resolve_binary(name: str) -> str:', content)

# Fix E303 at line 174 (too many blank lines)
content = re.sub(r'\n\n\n\nclass BaseResource:', r'\n\n\nclass BaseResource:', content)

# Fix E302 at line 401 (_resolve_runtime_paths)
content = re.sub(r'\n        return patched\ndef _resolve_runtime_paths\(env: dict\) -> None:', r'\n        return patched\n\n\ndef _resolve_runtime_paths(env: dict) -> None:', content)

path.write_text(content, encoding="utf-8")

import os
from pathlib import Path

content = Path("ghc_compiler_python/wrapper.py").read_text()

content = content.replace('out.write(content_to_write.replace(b"@GHC_PREFIX@", prefix_clean_bytes))', 'out.write(content_to_write.replace(b"@GHC_PREFIX@", prefix_clean_bytes))\n                    tmp_path.chmod(target_path.stat().st_mode)')

Path("ghc_compiler_python/wrapper.py").write_text(content)

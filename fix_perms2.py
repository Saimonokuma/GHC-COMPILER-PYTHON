import os
from pathlib import Path

content = Path("ghc_compiler_python/wrapper.py").read_text()

content = content.replace('tmp_path.chmod(conf_file.stat().st_mode if "conf_file" in locals() else script.stat().st_mode)\n                        tmp_path.replace(conf_file)', 'tmp_path.chmod(conf_file.stat().st_mode)\n                        tmp_path.replace(conf_file)')

content = content.replace('tmp_path.chmod(conf_file.stat().st_mode if "conf_file" in locals() else script.stat().st_mode)\n                        tmp_path.replace(script)', 'tmp_path.chmod(script.stat().st_mode)\n                        tmp_path.replace(script)')

Path("ghc_compiler_python/wrapper.py").write_text(content)

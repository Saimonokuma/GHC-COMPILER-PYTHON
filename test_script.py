import re

content = ""
with open("ghc_compiler_python/wrapper.py", "r") as f:
    content = f.read()

# Let's see if we missed any missing check=True
if "subprocess.run(" in content:
    print("Found subprocess.run")

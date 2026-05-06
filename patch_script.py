import re

with open("ghc_compiler_python/wrapper.py", "r") as f:
    content = f.read()

# Put back the comment that was removed:
# # ⚡ Bolt: Read in binary mode first to avoid severe performance degradation
# # when encountering binary files. UTF-8 decoding with errors="replace"
# # on large binaries can take seconds.

new_str = '''    # Replace @GHC_PREFIX@ in all target files
    for target in targets:
        try:
            # ⚡ Bolt: Read in binary mode first to avoid severe performance degradation
            # when encountering binary files. UTF-8 decoding with errors="replace"
            # on large binaries can take seconds.
            with open(target, "rb") as f:
                content = f.read()'''

old_str = '''    # Replace @GHC_PREFIX@ in all target files
    for target in targets:
        try:
            with open(target, "rb") as f:
                content = f.read()'''

content = content.replace(old_str, new_str)

with open("ghc_compiler_python/wrapper.py", "w") as f:
    f.write(content)

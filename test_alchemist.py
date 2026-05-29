from pathlib import Path
class BaseResource:
    name = "bin"
    is_dir = True
    @classmethod
    def validate(cls, p): return True

import os
root = "."
dirs = ["bin"]
files = ["a.txt"]
cls = BaseResource
p = None
if cls.name in (dirs if cls.is_dir else files) and cls.validate(p := Path(root) / cls.name):
    print(f"Found: {p}")

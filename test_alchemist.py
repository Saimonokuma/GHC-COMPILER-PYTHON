import sys
import os
from pathlib import Path

# Python 3.8+ compatible generator comprehension
def test():
    candidates, vars_to_update = {
        "darwin": ([1], ["DYLD_LIBRARY_PATH"]),
        "linux": ([1], ["LD_LIBRARY_PATH"]),
        "win32": ([2], ["PATH"]),
    }.get(sys.platform, ([], []))
    print(candidates, vars_to_update)

test()

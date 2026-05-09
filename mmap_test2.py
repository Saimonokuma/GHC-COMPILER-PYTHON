import mmap
from pathlib import Path

# Create a small file
with open("test.conf", "wb") as f:
    f.write(b"foo @GHC_PREFIX@ bar")

def patch_file(target_path):
    target_path = Path(target_path)
    content_to_write = None
    with target_path.open("rb") as f:
        try:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
                if m.find(b"@GHC_PREFIX@") != -1:
                    f.seek(0)
                    content_to_write = f.read()
        except ValueError:
            pass

    if content_to_write is not None:
        with target_path.open("wb") as out:
            out.write(content_to_write.replace(b"@GHC_PREFIX@", b"/new/prefix"))
        return True
    return False

print(patch_file("test.conf"))
with open("test.conf", "rb") as f:
    print(f.read())

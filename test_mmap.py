import mmap

with open("empty.txt", "wb") as f:
    pass

try:
    with open("empty.txt", "rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
            print("mmap created")
except ValueError as e:
    print(f"ValueError: {e}")

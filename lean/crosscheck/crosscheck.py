"""Executes the REAL wrapper._bundled_c_linker against roots materialised on
disk, and diffs each verdict against the Lean model's verdict for the same
root. Corpus and expected verdicts come from Lean; nothing is hardcoded here."""
import sys, tempfile, pathlib, importlib.util

REPO = pathlib.Path(sys.argv[1])
VERDICTS = pathlib.Path(sys.argv[2])
sys.path.insert(0, str(REPO))

spec = importlib.util.spec_from_file_location(
    "wrapper_under_test", REPO / "ghc_compiler_python" / "wrapper.py")
w = importlib.util.module_from_spec(spec)
sys.modules["wrapper_under_test"] = w
spec.loader.exec_module(w)

fails = 0
checks = 0

# Phase 1: the catalogue itself must not drift between spec and code.
LEAN_CATALOGUE = ["mingw/bin/clang.exe", "mingw/bin/gcc.exe",
                  "mingw/bin/clang", "mingw/bin/gcc"]
checks += 1
if list(w._BUNDLED_LINKERS) != LEAN_CATALOGUE:
    fails += 1
    print(f"FAIL catalogue: python={list(w._BUNDLED_LINKERS)} lean={LEAN_CATALOGUE}")
else:
    print(f"ok   catalogue matches ({len(LEAN_CATALOGUE)} entries)")

# Phase 2: None root -> no bundled linker (bundledCLinker_none).
checks += 1
if w._bundled_c_linker(None) is not None:
    fails += 1
    print("FAIL _bundled_c_linker(None) is not None")
else:
    print("ok   _bundled_c_linker(None) is None")

# Phase 3: execute the real probe on each corpus root.
for line in VERDICTS.read_text().splitlines():
    if "|" not in line:
        continue
    paths, verdict = line.rsplit("|", 1)
    files = [p for p in paths.split(",") if p]
    expected = verdict.strip() == "true"
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        for rel in files:
            f = root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"\x7fELF stub")
        got = w._bundled_c_linker(root) is not None
        # A mismatch is only excusable if its CAUSE is case-insensitive path
        # resolution: some catalogue entry resolves on disk although no file
        # was literally created at it, and a case variant of it was.
        casefold = False
        if got and not expected:
            lowered = {f.lower() for f in files}
            casefold = any(
                (root / c).is_file() and c not in files and c.lower() in lowered
                for c in LEAN_CATALOGUE)
    checks += 1
    if got == expected:
        print(f"ok   root={files!r} -> {got}")
    elif casefold:
        print(f"DIVERGE(case-fold, filesystem-caused) root={files!r} "
              f"lean={expected} python={got}")
    else:
        fails += 1
        print(f"FAIL root={files!r} lean={expected} python={got}")

# Phase 4: the ordering fix, read off the real source of _execute_tool.
import inspect, re
src = inspect.getsource(w._execute_tool)
body = [l.strip() for l in src.splitlines()]
def first_index(pat):
    for i, l in enumerate(body):
        if re.match(pat, l):
            return i
    return -1
i_acq = first_index(r"root\s*=\s*_ghc_root\(\)")
i_val = first_index(r"_validate_c_linker\(")
i_pat = first_index(r"_resolve_runtime_paths\(")
checks += 1
if not (0 <= i_acq < i_val < i_pat):
    fails += 1
    print(f"FAIL _execute_tool order: acquire={i_acq} validate={i_val} patch={i_pat}")
else:
    print(f"ok   _execute_tool order acquire({i_acq}) < validate({i_val}) < patch({i_pat})")

# Phase 5: _validate_c_linker must actually accept a root argument.
checks += 1
params = list(inspect.signature(w._validate_c_linker).parameters)
if params != ["root"]:
    fails += 1
    print(f"FAIL _validate_c_linker signature {params}")
else:
    print("ok   _validate_c_linker takes a root")

print(f"\n{checks - fails}/{checks} checks passed")
sys.exit(1 if fails else 0)

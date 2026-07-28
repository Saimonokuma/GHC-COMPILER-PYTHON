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

# Phase 6: Proofs/Vendor.lean proves a payload cannot be self-contained unless
# the tree is vendored BEFORE it is snapshotted (no_vendor_no_selfContained,
# vendor_after_archive_is_too_late). A proof about an ordering is worth nothing
# if the shipped workflow orders it the other way, so read the generated YAML
# and check the real thing.
#
# Deliberately textual, and that is not a shortcut. It needs no YAML parser --
# so the proofs job keeps zero Python dependencies -- and both step names are
# unique in the file, which makes byte offsets a sound proxy for order.
WORKFLOW = REPO / ".github" / "workflows" / "build.yml"
VENDOR_STEP = "Vendor Shared Libraries Into The Payload (Linux)"
ARCHIVE_STEP = "Build Toolchain Payload Archive"

checks += 1
if not WORKFLOW.is_file():
    fails += 1
    print(f"FAIL {WORKFLOW} not found")
else:
    text = WORKFLOW.read_text(encoding="utf-8")
    i_vendor = text.find(VENDOR_STEP)
    i_archive = text.find(ARCHIVE_STEP)
    if i_vendor < 0 or i_archive < 0:
        fails += 1
        print(f"FAIL step missing from build.yml: "
              f"vendor={i_vendor >= 0} archive={i_archive >= 0}")
    elif i_vendor > i_archive:
        fails += 1
        print("FAIL build.yml vendors AFTER archiving -- Vendor.lean proves the "
              "payload that results cannot start (vendor_after_archive_is_too_late)")
    else:
        print(f"ok   build.yml vendors before archiving "
              f"({VENDOR_STEP!r} at {i_vendor} < {ARCHIVE_STEP!r} at {i_archive})")

# Phase 7: vendoring into the payload accomplishes nothing unless the launcher
# looks there. The payload carrying a library the wrapper never puts on
# LD_LIBRARY_PATH fails exactly like carrying no library at all.
checks += 1
sterilize_src = inspect.getsource(w._sterilize_environment)
if 'ghc_root / "vendor-lib"' not in sterilize_src:
    fails += 1
    print("FAIL wrapper never adds the payload's vendor-lib to LD_LIBRARY_PATH")
else:
    print("ok   wrapper adds the payload's vendor-lib to LD_LIBRARY_PATH")

# Phase 8: EVERYTHING MATCHES.
#
# Proofs/Payload.lean proves the two version axes are independent coordinates
# (download_ignores_the_compiler_axis, report_ignores_the_release_axis). That
# is a statement about the MODEL. It buys nothing if the six files that
# actually carry these strings have drifted apart from each other.
#
# So every version-bearing declaration in the repository is read off disk and
# required to agree. Six places, two axes, one truth each.
import ast

def read_assign(rel, name):
    """Value of a module-level `NAME = "literal"` in a real source file."""
    tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    if isinstance(node.value, ast.Constant):
                        return node.value.value
    return None

def read_lean_def(rel, name):
    m = re.search(rf'def {name} : String := "([^"]+)"',
                  (REPO / rel).read_text(encoding="utf-8"))
    return m.group(1) if m else None

def read_toml_version(rel):
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"',
                  (REPO / rel).read_text(encoding="utf-8"))
    return m.group(1) if m else None

release_axis = {
    "bootstrap.RELEASE_VERSION": read_assign("ghc_compiler_python/bootstrap.py", "RELEASE_VERSION"),
    "generate_workflow.RELEASE_VERSION": read_assign("scripts/generate_workflow.py", "RELEASE_VERSION"),
    "__init__.__version__": read_assign("ghc_compiler_python/__init__.py", "__version__"),
    "pyproject.version": read_toml_version("pyproject.toml"),
    "Payload.lean releaseVersion": read_lean_def("lean/Proofs/Payload.lean", "releaseVersion"),
}
compiler_axis = {
    "bootstrap.GHC_VERSION": read_assign("ghc_compiler_python/bootstrap.py", "GHC_VERSION"),
    "generate_workflow.GHC_VERSION": read_assign("scripts/generate_workflow.py", "GHC_VERSION"),
    "wrapper.GHC_VERSION": read_assign("ghc_compiler_python/wrapper.py", "GHC_VERSION"),
    "__init__.__ghc_version__": read_assign("ghc_compiler_python/__init__.py", "__ghc_version__"),
    "Payload.lean ghcVersion": read_lean_def("lean/Proofs/Payload.lean", "ghcVersion"),
}

for label, axis in (("release", release_axis), ("compiler", compiler_axis)):
    checks += 1
    missing = [k for k, v in axis.items() if v is None]
    values = set(v for v in axis.values() if v is not None)
    if missing:
        fails += 1
        print(f"FAIL {label} axis unreadable in: {missing}")
    elif len(values) != 1:
        fails += 1
        print(f"FAIL {label} axis disagrees: "
              + ", ".join(f"{k}={v}" for k, v in sorted(axis.items())))
    else:
        print(f"ok   {label} axis agrees across {len(axis)} files: {values.pop()}")

# And the two axes must not have quietly become the same number again, which
# would make every theorem above vacuously true rather than false.
checks += 1
r = release_axis["bootstrap.RELEASE_VERSION"]
g = compiler_axis["bootstrap.GHC_VERSION"]
if r is None or g is None:
    fails += 1
    print("FAIL could not read both axes")
elif r == g:
    fails += 1
    print(f"FAIL both axes are {r} -- versions_differ is now false and every "
          f"theorem resting on it is vacuous")
else:
    print(f"ok   axes are distinct: release={r} compiler={g}")

print(f"\n{checks - fails}/{checks} checks passed")
sys.exit(1 if fails else 0)

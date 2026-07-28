<div align="center">

# 🤝 Contributing to GHC Compiler Python

**Every contribution matters — code, tests, proofs, or just telling us what broke**

[![Ko-fi](https://img.shields.io/badge/Support-Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/saimonokuma)
[![Nova-Violet Role](https://img.shields.io/badge/Nova--Violet-Role-9b59b6?style=for-the-badge)](https://github.com/Nova-Violet-Role)

</div>

---

## 💡 The easiest useful thing you can do

**Install it on your machine and tell us what happened.**

```bash
pip install ghc-compiler-python
ghc-wrapper --numeric-version     # should print 9.4.8
```

Then compile something real. If it fails, [open an issue](https://github.com/Saimonokuma/GHC-COMPILER-PYTHON/issues) with your OS, distribution, glibc version (`ldd --version` on Linux), and Python version. Packaging a native toolchain means the interesting failures happen on machines we do not have.

---

## 🗺️ Where things live

| Path | What it is |
|:--|:--|
| `ghc_compiler_python/wrapper.py` | Subprocess proxies. Environment sterilization and hermetic binary resolution. |
| `ghc_compiler_python/bootstrap.py` | First-run acquisition: download, verify, extract, atomic promote. |
| `scripts/generate_workflow.py` | **Generates both workflows.** |
| `scripts/fetch_binaries.sh` | Downloads and stages the upstream GHC distribution. |
| `scripts/optimize_binaries.sh` | Trims the payload from 2,017 MB to 863 MB. |
| `tests/` | Test suite — runs on all three OS, two Python versions. |
| `lean/` | Lean 4 proofs of what must hold for every input. |

---

## ⚠️ Two rules that will save you an afternoon

### 1. Never edit `.github/workflows/*.yml`

They are **generated**. Edit `scripts/generate_workflow.py` and run it:

```bash
python scripts/generate_workflow.py
```

This is not a style preference. A hardening fix once lived only in the generated YAML and was silently reverted on every regeneration until someone diffed the two.

### 2. Measure before you conclude

This project has a history of bugs caused by instruments that looked right:

- `find … -type f -name ghc` reported the compiler missing. `bin/ghc` is a **symlink**, and `-type f` does not match symlinks.
- `find … | grep -q` under `set -o pipefail` passed for 37 files and failed for 1,599 — `grep -q` exits early, `find` takes SIGPIPE, and whether that happens depends on the pipe buffer.
- `manylinux_2_28` was chosen by reasoning about distro coverage instead of measuring what the binaries require. auditwheel refused it.

If a check can pass for the wrong reason, make it print what it *found*, not only what it missed.

---

## 🧪 Running things locally

```bash
# Tests
pip install pytest
python -m pytest tests/ -v

# Proofs (needs elan; the toolchain pins itself)
cd lean && lake build
```

Both run in CI on every pull request, across Linux, macOS and Windows on Python 3.10 and 3.13.

---

## 📐 When to prove instead of test

If a property must hold for **every** input rather than the ones a test supplies, it belongs in `lean/`.

Already proved: payload identities are injective (so two platforms can never share a cache directory), the cache is never observable half-installed, and archive extraction cannot escape its destination.

Good candidates: anything about path handling, version comparison, or state that must be atomic. Proofs depend on **Lean core only — no Mathlib** — and CI fails on any `sorry`, because a file containing one compiles happily and proves nothing.

---

## ✅ What a good pull request looks like

| | |
|:--|:--|
| 🎯 **Fixes a cause** | Not a symptom made to pass |
| 📊 **Shows a measurement** | The output that proves it, not a description of it |
| 🧪 **Extends the tests** | Tests are the floor, not the ceiling |
| 📝 **Explains why** | The commit message should say what was wrong and how you know |

If you found a bug and fixed it, please include the failing output in the commit message. The next person to touch that code will need it.

---

## 🌱 Good first contributions

- **Try it on your distribution.** Especially non-Ubuntu Linux, or older glibc.
- **x86_64 macOS.** Currently only Apple Silicon is built.
- **Linux aarch64.** `bootstrap.py` already knows the tag; nothing builds it yet.
- **Extend the Lean proofs.** Version parsing and path normalization are unproved.
- **Documentation.** If something here confused you, that is a bug in the docs.

---

<div align="center">

### 🤝 Thank you

*Built by and for the community.*

[![Support Our Journey](https://img.shields.io/badge/🔗_Support_Our_Journey-Ko--fi-FF5E5B?style=for-the-badge)](https://ko-fi.com/saimonokuma)

[README](README.md) · [Architecture](ARCHITECTURE.md) · [Issues](https://github.com/Saimonokuma/GHC-COMPILER-PYTHON/issues)

© 2026 Nova-Violet Role · Non-Profit Organization

</div>

<div align="center">

# ⚡ GHC Compiler Python · v9.4.8

**GHC 9.4.8 · Cabal 3.10.3.0 · Windows · macOS · Linux**

*The first pip-installable Glasgow Haskell Compiler*

[![Ko-fi](https://img.shields.io/badge/Support-Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/saimonokuma)
[![PyPI](https://img.shields.io/badge/PyPI-install-3775A9?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/ghc-compiler-python/)
[![Nova-Violet Role](https://img.shields.io/badge/Nova--Violet-Role-9b59b6?style=for-the-badge)](https://github.com/Nova-Violet-Role)

</div>

---

## 🚀 Just install it

```bash
pip install ghc-compiler-python
```

**~17 KiB.** The toolchain for your platform is fetched on first use and verified against a SHA-256 digest baked into the wheel. You do not need anything on this page.

---

## 📦 Which asset do I want?

Only if you need an **offline or air-gapped** install:

| You are on | Download | Size |
|:--|:--|--:|
| 🐧 **Linux** (glibc ≥ 2.39) | `ghc_compiler_python-9.4.8-py3-none-manylinux_2_39_x86_64.whl` | ~370 MB |
| 🍎 **macOS** (Apple Silicon) | `ghc_compiler_python-9.4.8-py3-none-macosx_11_0_arm64.whl` | ~191 MB |
| 🪟 **Windows** (x86_64) | `ghc_compiler_python-9.4.8-py3-none-win_amd64.whl` | ~350 MB |

```bash
pip install ./ghc_compiler_python-9.4.8-py3-none-<your-platform>.whl
```

These bundle the whole toolchain and **never contact the network**.

> On a Linux older than Ubuntu 24.04, use `pip install ghc-compiler-python` instead. GHC is built on glibc 2.39 and the offline wheel says so honestly rather than installing and failing later.

<details>
<summary><b>🔍 Toolchain payloads (advanced)</b></summary>

The `ghc-payload-*` archives are what the thin wheel downloads on first use. You rarely want these directly — but you can pre-seed a cache with one:

```bash
export GHC_COMPILER_PYTHON_HOME=/path/to/cache
# extract the payload there, then run offline
export GHC_COMPILER_PYTHON_OFFLINE=1
```

Each is published with a `.sha256` companion. The digests are embedded in the thin wheel at build time, so verification is automatic.

</details>

---

## ✅ How this release was verified

Every asset here was produced by the same workflow run that proved, **on each operating system separately**:

1. the wheel installs
2. `ghc-wrapper --numeric-version` reports **9.4.8** — our pinned compiler, not one that happened to be on the runner
3. a Haskell program compiles
4. the compiled binary **runs**
5. its output matches exactly

Builds ≠ installs ≠ compiles ≠ delivered. All five links are asserted before anything is published.

The Lean 4 proofs build with zero `sorry` in the same pipeline.

---

## ⚙️ Configuration

| Variable | Effect |
|:--|:--|
| `GHC_COMPILER_PYTHON_HOME` | Where the toolchain is cached |
| `GHC_COMPILER_PYTHON_OFFLINE` | `1` refuses network access entirely |

---

## 💻 Usage

```bash
ghc-wrapper Main.hs      # compile
ghci-wrapper             # REPL
cabal-wrapper build      # build a project
```

Resolution is hermetic — a GHC already on your PATH is deliberately ignored, so you always get the pinned 9.4.8.

---

<div align="center">

### ⚡ One command. Three platforms. The full Haskell toolchain.

If this saved you time, you can support the work:

[![Support Our Journey](https://img.shields.io/badge/🔗_Support_Our_Journey-Ko--fi-FF5E5B?style=for-the-badge)](https://ko-fi.com/saimonokuma)

[README](README.md) · [Architecture](ARCHITECTURE.md) · [Issues](https://github.com/Saimonokuma/GHC-COMPILER-PYTHON/issues)

© 2026 Nova-Violet Role · Non-Profit Organization

*Created with ❤️ for the advancement of human understanding*

</div>

<div align="center">

# ⚡ GHC Compiler Python

**The bridge between Haskell and Python**

*The first pip-installable Glasgow Haskell Compiler — one command, three platforms, the full toolchain*

[![Ko-fi](https://img.shields.io/badge/Support-Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/saimonokuma)
[![PyPI](https://img.shields.io/badge/PyPI-ghc--compiler--python-3775A9?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/ghc-compiler-python/)
[![Nova-Violet Role](https://img.shields.io/badge/Nova--Violet-Role-9b59b6?style=for-the-badge)](https://github.com/Nova-Violet-Role)
[![License](https://img.shields.io/badge/License-MIT-764ba2?style=for-the-badge)](LICENSE)

[![GHC](https://img.shields.io/badge/GHC-9.4.8-5e5086?style=flat-square&logo=haskell&logoColor=white)](https://www.haskell.org/ghc/)
[![Cabal](https://img.shields.io/badge/Cabal-3.10.3.0-5e5086?style=flat-square)](https://www.haskell.org/cabal/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Proved in Lean 4](https://img.shields.io/badge/Proved%20in-Lean%204-2C3E50?style=flat-square)](lean/)

</div>

---

## 📜 About

A Haskell toolchain is normally installed by its own ecosystem installer, which writes to `~/.ghc`, `~/.cabal` and the system PATH. That is awkward inside a Python project, hostile inside CI, and impossible where the global state is not yours to change.

**GHC Compiler Python** delivers GHC through the packaging mechanism Python already has. The compiler lives inside the environment, the wrappers sterilize the environment before every call, and removing the environment removes the toolchain.

- ✅ `pip install ghc-compiler-python`
- ✅ Windows · macOS · Linux
- ✅ Full GHC 9.4.8 compiler
- ✅ Complete Cabal 3.10.3.0 support
- ✅ Any AI with Python execution can now compile Haskell

---

## 🔢 Two version numbers, and what each one means

This trips people up, so it is stated once, plainly:

| | example | what it is |
|---|---|---|
| **package version** | `9.5.0` | *this project* — the wheel you `pip install`. Ours to bump. |
| **compiler version** | `9.4.8` | *GHC itself* — the Haskell compiler you get. Not ours to invent. |

`ghc-wrapper --numeric-version` answers **9.4.8**, because you are asking it which Haskell compiler you have.

The two used to be one number, which broke the moment they had to disagree. The 9.4.8 wheel could not compile on Windows, PyPI does not permit replacing a published version, and the last GHC in the 9.4 line *is* 9.4.8 — so shipping a fix and claiming a new compiler were the same edit. They are now separate, and `lean/Proofs/Payload.lean` proves they can never be confused again: a package bump renames every asset and changes nothing you are told about the compiler.

---

## 🚀 Installation

```bash
pip install ghc-compiler-python
```

Or with [uv](https://github.com/astral-sh/uv) — same package, same index:

```bash
uv pip install ghc-compiler-python          # into a project venv
uv tool install ghc-compiler-python         # 10 commands, available everywhere
uvx --from ghc-compiler-python ghc-wrapper  # run it without installing anything
```

`uv tool install` puts `ghc-wrapper`, `cabal-wrapper`, `ghci-wrapper`, `runghc-wrapper` and six more on your PATH globally — a Haskell toolchain with no Haskell installer, no `~/.ghc`, and nothing to uninstall but the tool itself.

The PyPI package is **~17 KiB**. It fetches the toolchain for your platform on first use and verifies it against a SHA-256 digest embedded in the wheel — a tampered or truncated download cannot install.

### 📦 Offline / air-gapped

Self-contained wheels with the toolchain already bundled live on the [releases page](https://github.com/Saimonokuma/GHC-COMPILER-PYTHON/releases). These never contact the network:

```bash
pip install ghc_compiler_python-9.5.0-py3-none-manylinux_2_38_x86_64.manylinux_2_39_x86_64.whl   # Linux
pip install ghc_compiler_python-9.5.0-py3-none-macosx_11_0_arm64.whl       # macOS
pip install ghc_compiler_python-9.5.0-py3-none-win_amd64.whl               # Windows
```

> The Linux offline wheel carries the tags `manylinux_2_38` **and** `manylinux_2_39`, so it installs on glibc 2.38 or newer. That floor is not chosen — auditwheel derives it by inspecting the versioned symbols the binaries actually reference. A tag lower than the binaries support would install on systems where the toolchain then fails at runtime, so the build states what is true rather than what would be convenient. On older distributions use the thin wheel; its payload is a plain tarball and carries no such constraint.

### 🔧 Requirements

| | |
|:--|:--|
| 🐍 **Python** | `>= 3.10` |
| 🐧 Linux | a C linker — `sudo apt-get install gcc` |
| 🍎 macOS | a C linker — `xcode-select --install` |
| 🪟 **Windows** | **nothing.** The payload carries its own `clang` and `ld`. |

> Windows used to require MinGW-w64 or MSYS2. It never actually needed them: the Windows payload has always shipped a complete mingw toolchain — that is why it is the largest of the three. The wrapper simply refused to look inside it and demanded a system compiler instead, which is what made 9.4.8 unusable on a stock Windows machine. Fixed in 9.4.9; the CI job that certifies Windows now deletes every system compiler from `PATH` before it compiles, so this cannot silently regress.

### ⚙️ Configuration

| Variable | Effect |
|:--|:--|
| `GHC_COMPILER_PYTHON_HOME` | Where the toolchain is cached. Defaults to the platform cache directory. |
| `GHC_COMPILER_PYTHON_OFFLINE` | Set to `1` to refuse network access entirely. |

### 💾 Disk usage

Each release caches its own toolchain, so upgrading leaves the previous one in place — around 1.8 GB per version on Windows. That is deliberate: a payload rebuilt under a new tag is not byte-identical, so reusing the old tree would skip the digest check entirely. It does mean the cache grows.

```bash
python -m ghc_compiler_python.bootstrap --cache-info
```

```
cache root: C:\Users\you\AppData\Local\ghc-compiler-python\Cache
  9.4.8/win_amd64                 1.8 GiB  [superseded]
  9.4.9/win_amd64                 1.8 GiB  [superseded]
  9.5.0/win_amd64                 1.8 GiB  [current]
  --------------------------------------
  total                           5.4 GiB
  superseded (not deleted)        3.5 GiB
```

**Nothing is ever deleted automatically, and there is no flag that deletes.** Removing a toolchain a virtual environment still points at breaks that environment silently, and this package cannot see which ones exist. So it tells you what you have and leaves the decision with you — delete a superseded directory by hand once you are sure nothing uses it.

---

## 💻 Usage

```bash
# Compile a Haskell file
ghc-wrapper Main.hs

# Launch GHCi
ghci-wrapper

# Build a Cabal project
cabal-wrapper build
```

Wrappers sterilize the environment on every call, so a global `~/.ghc/` or `GHC_PACKAGE_PATH` cannot leak into your build.

Resolution is **hermetic**: a GHC already on your PATH is deliberately *ignored*, so you always get the pinned 9.4.8 rather than whatever the host happens to have.

---

## 🖥️ Supported Platforms

| OS | Architecture | Toolchain |
|:--|:--|:--|
| 🐧 **Linux** | x86_64 | GHC 9.4.8 · Cabal 3.10.3.0 |
| 🍎 **macOS** | ARM64 (Apple Silicon) | GHC 9.4.8 · Cabal 3.10.3.0 |
| 🪟 **Windows** | x86_64 | GHC 9.4.8 · Cabal 3.10.3.0 |

Every release is proven on all three: each platform installs the wheel, compiles a Haskell program, **runs** it, and asserts its output — and checks the reported compiler is the pinned 9.4.8 — before anything is published. Builds ≠ installs ≠ compiles ≠ delivered.

---

## 📐 What is proved, not merely tested

Some properties must hold for *every* input, not for the inputs a test happens to supply. Those are proved in **Lean 4** — machine-checked, zero `sorry`, verified in CI.

```lean
theorem payloadKey_injective (p q : Platform) : payloadKey p = payloadKey q → p = q
theorem no_partial_state (s : CacheState) (steps : List Step) : ...
theorem no_escape_without_dotdot : ∀ member base, ¬ member.contains ".." → isWithin base member
```

**Injective** — no two platforms share a payload identity, so one platform can never run another's binaries. **Atomic** — under any interleaving, the cache is observable only as absent or complete, never half-installed. **Contained** — an archive member without `..` cannot escape the destination, for any base and any depth.

---

## 📊 What is in the payload

Measured from the real 9.4.8 distribution — 9,870 entries, 2,017 MB extracted:

| Component | Size | Share | Kept |
|:--|--:|--:|:--|
| Profiling libraries | 602 MB | 29.9% | ❌ |
| Documentation / haddock | 580 MB | 28.7% | ❌ |
| Static archives | 331 MB | 16.4% | ✅ |
| Shared objects | 174 MB | 8.6% | ✅ |
| Executables | 165 MB | 8.2% | ✅ |
| Interface files (static) | 82 MB | 4.1% | ✅ |
| Interface files (dynamic) | 82 MB | 4.1% | ✅ |
| Other | 1 MB | 0.1% | ✅ |
| **Total** | **2,017 MB** | **100.0%** | |

Removing the first two: **2,017 → 863 MB** extracted, **164 → 91 MB** compressed. Linking is static by default, GHCi and TemplateHaskell load the shared objects, and imports cannot resolve without interface files — so those stay. Restore the rest with `GHC_KEEP_PROFILING=1` or `GHC_KEEP_DOCS=1`.

---

## 🤝 Contributing

| Area | How you can help |
|:--|:--|
| 💻 **Code** | Platform support, packaging, wrapper robustness |
| 🧪 **Testing** | Try it on your distribution and report what breaks |
| 📐 **Proofs** | Extend the Lean 4 formalization |
| 📖 **Documentation** | Improve guides and examples |
| 💡 **Ideas** | Tell us what a pip-installable compiler should do next |

See [ARCHITECTURE.md](ARCHITECTURE.md) for how delivery works and why.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

### ⚡ GHC Compiler Python

*One command. Three platforms. The full Haskell toolchain.*

[![Support Our Journey](https://img.shields.io/badge/🔗_Support_Our_Journey-Ko--fi-FF5E5B?style=for-the-badge)](https://ko-fi.com/saimonokuma)

[PyPI](https://pypi.org/project/ghc-compiler-python/) · [Releases](https://github.com/Saimonokuma/GHC-COMPILER-PYTHON/releases) · [Issues](https://github.com/Saimonokuma/GHC-COMPILER-PYTHON/issues)

© 2026 Nova-Violet Role · Non-Profit Organization

*Created with ❤️ for the advancement of human understanding*

</div>

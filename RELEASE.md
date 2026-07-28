<div align="center">

# ⚡ GHC Compiler Python · v9.6.1

**GHC 9.6.1 · Cabal 3.10.3.0 · Windows · macOS · Linux**

*The first pip-installable Glasgow Haskell Compiler*

[![Ko-fi](https://img.shields.io/badge/Support-Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/saimonokuma)
[![PyPI](https://img.shields.io/badge/PyPI-install-3775A9?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/ghc-compiler-python/)
[![Nova-Violet Role](https://img.shields.io/badge/Nova--Violet-Role-9b59b6?style=for-the-badge)](https://github.com/Nova-Violet-Role)

</div>

---

> ### 🚀 New in 9.6.1: the compiler itself is upgraded — GHC 9.4.8 → 9.6.1
>
> Every release up to 9.5.0 shipped GHC **9.4.8**, the last of the 9.4 line. 9.6.1 ships **GHC 9.6.1** on all three platforms.
>
> **The two version numbers now agree, and that is the point.** 9.4.9 and 9.5.0 carried a package number ahead of their compiler, because the 9.4.8 wheel was broken on Windows and PyPI does not allow replacing a published version — there was no GHC 9.4.9 to ship, so the axes had to diverge. With the compiler genuinely upgraded, both axes name 9.6.1 honestly.
>
> Coinciding is not a regression, and the spec had to learn that the hard way: `Proofs/Payload.lean` previously asserted `releaseVersion ≠ ghcVersion` and **would have refused to compile on this release**. That theorem encoded a fact about two past releases as if it were an invariant. It is replaced by properties quantified over any pair of versions, which hold whether the axes agree or not.
>
> **And a new class of theorem, prompted by a request to simply edit the claimed version:**
>
> ```lean
> theorem resolves_iff_claim_matches_artifact (b : Build) :
>     resolves b ↔ b.claimed = b.fetched
> ```
>
> `wrapper.py` builds the toolchain path out of the version it claims — `lib/ghc-<GHC_VERSION>/`. So naming a compiler we did not ship is not a cosmetic dishonesty with an ethics argument attached; it points the launcher at a directory that does not exist. `crosscheck.py` phase 9 now reads `fetch_binaries.sh` and fails if the version we claim is not the version we download.
>
> ---
>
> ### 📉 New in 9.5.0: the Windows download is 148 MB smaller
>
> The Windows payload shipped as a zip through 9.4.9 and now ships as `.tar.xz`, like the other two. Measured on the real toolchain — 1814 MB, 8311 files:
>
> | format | size | build time |
> |---|---:|---:|
> | zip (`7z -tzip -mx=5 -mmt=on`) | 395.8 MB | 26 s |
> | **tar.xz (`xz -T0 -6`)** | **247.3 MB** | 89 s |
>
> **37.5% smaller.** The extra minute is paid once per release, by CI. The 148 MB was paid by every Windows user on every cold install. The round-trip was verified lossless by comparing all 8311 files by SHA-256 — not by spot-checking one binary — and `bootstrap._extract` has always handled `.tar.xz`, so the zip was never a Windows requirement, only an artefact of building it with 7z.
>
> ---
>
> ### ⚠️ 9.4.8 does not work on Windows **or Linux**. Upgrade.
>
> The 9.4.8 wheel aborted with `FATAL ERROR: The GHC compiler requires a host C-linker (gcc or clang)` on any Windows machine without a system compiler — which is nearly all of them. The Windows payload ships its own toolchain (`mingw/bin/clang.exe`, and it is why that payload is 396 MB), but the wrapper checked only the system `PATH` and gave up before it ever looked inside. It also ran the check *before* downloading the payload, so there was nothing to find either way.
>
> CI never caught it because `windows-latest` installs mingw via chocolatey, so a system `gcc` is always present there. It was found on the first genuine end-user install.
>
> **Linux was broken too, and for the same kind of reason.** Installing 9.4.8 on a stock Ubuntu 24.04 downloads and extracts the payload correctly, and then the compiler will not start:
>
> ```
> ghc-9.4.8: error while loading shared libraries: libtinfo.so.5:
> cannot open shared object file: No such file or directory
> ```
>
> GHC 9.4.8 links against ncurses 5; Ubuntu 24.04 ships ncurses 6 and has no `libtinfo.so.5` at all. `auditwheel` vendored that library into the **offline** wheel, but it ran after the payload archive was built — so the payload carried nothing, and every job in the pipeline validated the artifact nobody installing from PyPI receives. In 9.4.9 the payload carries its own `libtinfo.so.5`, `libgmp.so.10` and `libffi.so.8`, exactly as the Windows payload has always carried its own mingw.
>
> Both defects were invisible for the same structural reason: **nothing had ever run the path a real user takes.** The gate that finds it, `verify-delivered-install`, did not exist when 9.4.8 was tagged. It now runs on all three operating systems before anything can publish, and it caught the Linux defect on its very first execution.
>
> ```bash
> pip install --upgrade ghc-compiler-python
> ```
>
> **The version number moved, the compiler did not.** This release packages the same GHC 9.4.8; `ghc-wrapper --numeric-version` still reports `9.4.8`. The distribution version and the compiler version are now separate axes, because PyPI does not allow replacing a published version and a single constant made "publish a fixed wheel" and "claim a GHC release that does not exist" the same edit.

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
| 🐧 **Linux** (glibc ≥ 2.38) | `ghc_compiler_python-9.6.1-py3-none-manylinux_2_38_x86_64.manylinux_2_39_x86_64.whl` | ~188 MB |
| 🍎 **macOS** (Apple Silicon) | `ghc_compiler_python-9.6.1-py3-none-macosx_11_0_arm64.whl` | ~191 MB |
| 🪟 **Windows** (x86_64) | `ghc_compiler_python-9.6.1-py3-none-win_amd64.whl` | ~403 MB |

```bash
pip install ./ghc_compiler_python-9.6.1-py3-none-<your-platform>.whl
```

These bundle the whole toolchain and **never contact the network**.

> On a Linux with glibc older than 2.38, use `pip install ghc-compiler-python` instead. auditwheel derives that floor from the versioned symbols the binaries actually reference, and the wheel states it honestly rather than installing and failing later.

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
2. `ghc-wrapper --numeric-version` reports **9.6.1** — our pinned compiler, not one that happened to be on the runner
3. a Haskell program compiles
4. the compiled binary **runs**
5. its output matches exactly

Builds ≠ installs ≠ compiles ≠ delivered. All five links are asserted before anything is published.

**New in 9.4.9: the Windows leg now removes every system `gcc`/`clang` from `PATH` before it compiles**, and fails loudly if one survives. That single difference between the runner and a real machine is what let 9.4.8 ship green and broken. A runner better equipped than the machine it certifies is not a test, it is a rehearsal. On the run that published this release it dropped three of them — `C:\mingw64\bin`, `C:\Strawberry\c\bin` and `C:\Program Files\LLVM\bin` — and compiled anyway, on the payload's own toolchain.

**Also new: the claim on this page is checked against the index you actually install from.** `verify-pypi.yml` installs the published wheel from pypi.org on all three operating systems, compiles a Haskell program and asserts its output. Verified for 9.4.9 in run [30345687335](https://github.com/Saimonokuma/GHC-COMPILER-PYTHON/actions/runs/30345687335):

| OS | distribution | compiler | program output |
|---|---|---|---|
| ubuntu-latest | 9.4.9 | 9.4.8 | `Installed From PyPI: [1,2,3]` |
| macos-latest | 9.4.9 | 9.4.8 | `Installed From PyPI: [1,2,3]` |
| windows-latest | 9.4.9 | 9.4.8 | `Installed From PyPI: [1,2,3]` |

**And the ordering that caused the Linux defect is now proved, not tested.** `lean/Proofs/Vendor.lean` proves that no build which omits the vendoring step can produce a payload that starts — for every ordering of every other step, not merely the orderings someone thought to test. `crosscheck.py` then verifies the generated `build.yml` really does vendor before it archives, so the proof cannot drift away from the workflow it describes.

The Lean 4 proofs build with zero `sorry` in the same pipeline. The linker fix is covered by `lean/Proofs/Linker.lean`, whose model is diffed against the real `wrapper.py` by a cross-check that materialises toolchain roots on disk and runs the shipped code over them.

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

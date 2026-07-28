# Delivery architecture

This describes how the project is *delivered* as of the production-delivery
work. `WHITEPAPER.md` and `DEPLOYMENT_OPERATIVE_PLAN.md` remain the record of
the original design intent and are still accurate about the wrapper, the fetch
and patch scripts, and the relocation strategy. They are **superseded on
distribution only**, for the reasons below.

## Why the original model could not ship

The original pipeline built one wheel per OS, each containing the entire GHC
toolchain, and pushed all three to PyPI. Every OS build was green. Delivery
still could not work, for four independent reasons — all measured, none
inferred:

1. **Size.** PyPI enforces a 100 MB **per-file** limit. The wheels measured
   363 MB (Linux), 365 MB (macOS) and 539 MB (Windows). Splitting the release
   per OS does not help, because they were already separate files.

2. **Tagging.** All three were tagged `py3-none-any` — "pure Python, runs
   anywhere" — on wheels full of native binaries. Only Linux ran `auditwheel`,
   which retags; macOS ran `delocate-wheel`, which does not; Windows retagged
   nothing. The three collided on a single filename, so PyPI would have
   accepted one and served it to every platform. A Windows user would have
   received macOS binaries.

3. **Authentication.** Tag `v9.4.8` did fire run `25262196892`. Its publish job
   failed with `invalid-publisher: valid token, but no corresponding
   publisher`. The hundreds of green runs were pull-request runs, which never
   reach the publish job.

4. **Interpreter floor.** `requires-python` declared `>=3.8` while `wrapper.py`
   uses `match`/`case`, which is a syntax error before 3.10. pip would have
   installed a package that cannot import.

Only the fourth is a one-line fix. The first two are architectural: no amount
of shrinking makes a 2 GB toolchain fit a 100 MB file, and a universal tag on
a native wheel is wrong regardless of size.

## What ships now

Distribution is split by what actually has to fit where. What must fit inside
PyPI's limit is *Python* — the toolchain is acquired at first use.

| Tier | Artifact | Where | Size | Network |
| :--- | :--- | :--- | :--- | :--- |
| Thin | `py3-none-any` | PyPI | **17.5 KiB** | on first use |
| Payload | per-platform archive | GitHub Release | ~91 MB | n/a |
| Offline | platform-tagged wheel | GitHub Release | ~370 MB | never |

The thin wheel contains no binaries, so `py3-none-any` is now *true* rather
than a lie. GitHub Releases allow 2 GB per file, so the payloads and offline
wheels are unconstrained there.

### First-run acquisition

`ghc_compiler_python/bootstrap.py` resolves the platform, downloads the
matching payload from the release addressed by tag (never "latest", so a 9.4.8
wheel cannot pick up a future payload), verifies it against a SHA-256 digest
embedded in the wheel at build time, extracts it into staging, and promotes it
with an atomic rename.

Guarantees, in order of how badly their absence would hurt:

- **Never a half-install.** The completion stamp is written before the rename,
  and `is_installed` tests only the stamp. An interrupted download leaves an
  unstamped directory, which reads as absent, so the next run simply retries.
- **Never a silent substitution.** A digest mismatch aborts and removes
  everything. A tampered or truncated payload cannot install.
- **Never a traversal.** Archive members resolving outside the destination are
  refused, in both tar and zip.
- **Never a guess.** Every failure names the offline wheel that avoids needing
  the network at all.

Cache location follows the platform convention and is overridable with
`GHC_COMPILER_PYTHON_HOME`. `GHC_COMPILER_PYTHON_OFFLINE=1` refuses network
access outright.

### Payload composition

Measured from the real 9.4.8 Linux bindist — 9,870 entries, 2,017 MB extracted:

| Component | Size | Share | Kept |
| :--- | ---: | ---: | :--- |
| Profiling libraries (`*_p.a`, `*.p_hi`, `*.p_o`) | 602 MB | 29.9% | no |
| Documentation / haddock | 580 MB | 28.7% | no |
| Static archives (`.a`) | 331 MB | 16.4% | **yes** |
| Shared objects (`.so`) | 174 MB | 8.6% | **yes** |
| Executables | 165 MB | 8.2% | **yes** |
| Interface files (`.hi`) | 82 MB | 4.1% | **yes** |
| Interface files (`.dyn_hi`) | 82 MB | 4.1% | **yes** |
| Other | 1 MB | 0.1% | **yes** |
| **Total** | **2,017 MB** | **100.0%** | |

Classified from the archive listing of all 9,870 entries (9,329 regular files;
the remainder are directories and symlinks, which carry no payload). Every
byte is attributed — the categories sum to the total exactly, so nothing is
hidden in an unexamined remainder.

Removing the first two: 2,017 → 863 MB extracted, **164 → 91 MB compressed**.
Verified by extracting, trimming, recompressing and measuring — not estimated.

The retained categories are not negotiable: linking is static by default,
GHCi and TemplateHaskell load the shared objects at runtime, and imports
cannot resolve without interface files. Profiling and docs participate in
neither compiling nor running. Restore either with `GHC_KEEP_PROFILING=1` or
`GHC_KEEP_DOCS=1`.

## Pipeline

`build.yml` and `ci.yml` are both generated by `scripts/generate_workflow.py`.
Edit the generator; editing the YAML is reverted on the next regeneration.
This is not hypothetical — a `2>/dev/null` / `xargs -r` hardening lived only in
the generated file and was silently reverted every time. Dependabot edits the
generated file too, which is why action versions live in an `ACTIONS` table.

```
build-wheels-{linux,macos,windows}     fetch → trim → patch → payload+sha256
                                       → offline wheel → platform tag → E2E
                    ↓ (all three)
build-thin-wheel                       embed digests → build → verify
                    ↓
attach-to-release                      payloads + offline wheels → Release
                    ↓
verify-delivered-install               pip install thin wheel → download
  (linux · macos · windows)            payload from the Release → compile → run
                    ↓
publish-to-pypi                        thin wheel only → PyPI via API token
```

The join is forced by the data: payload digests do not exist until the
payloads are built, and the thin wheel cannot be built until it can embed
them.

`verify-delivered-install` exists because every other job validates the
*offline* wheel — it installs a wheel with the toolchain already inside, which
proves the compiler works but not that the product does. Nobody installing
from PyPI receives that wheel. They receive the thin one, which must reach the
network, fetch its payload from the Release, verify the digest compiled into
it, extract, and only then compile. That path had never run in CI: three green
builds, an attached Release and a successful upload were all compatible with a
wheel that 404s on first use. It deliberately does not set
`GHC_COMPILER_PYTHON_OFFLINE`, and `publish-to-pypi` depends on it, so a wheel
whose download path is broken cannot reach PyPI.

`ci.yml` runs the test suite on all three OS against Python 3.10 and 3.13, and
builds the Lean proofs. The suite previously existed but **no workflow ever
invoked it** — a suite that never runs is documentation, not a floor.

## What is proved rather than tested

`lean/` contains Lean 4 proofs (core only, no Mathlib) of properties that must
hold for every input:

- `payloadKey_injective` — no two platforms share a payload identity. This is
  the shipped tagging bug restated at the cache layer: two platforms resolving
  to one directory means one runs the other's binaries.
- `no_partial_state` — under any interleaving of installer steps, the cache is
  observable only as absent or complete.
- `no_escape_without_dotdot` — a member with no `..` cannot leave the
  destination, for any base and any depth. With `isWithin_sound` this pins the
  contract that the guard compares the *resolved* path, not the raw name; a
  guard comparing the raw name accepts `a/../../etc` because it starts with
  `a`, which is the classic form of this bug.

`lake build` exits 0 with zero `sorry`, asserted in CI — a file containing
`sorry` compiles fine and proves nothing, so the build succeeding is not
sufficient evidence.

## Release checklist

1. Merge to `main`; confirm `ci.yml` green on all three OS.
2. Ensure the repository secret `PYPI_API_TOKEN` is set. Publishing uses API
   token authentication (`user: __token__`), not Trusted Publishing. OIDC was
   tried and failed in run `25262196892` with `invalid-publisher: valid token,
   but no corresponding publisher` — the token was minted correctly, PyPI
   simply had no publisher registered, and nothing on the GitHub side can
   create one.
3. Tag `vX.Y.Z` and push. Tag runs are exempt from concurrency cancellation.
4. Verify through the API, not the badge: the run can be green while the job
   that matters was skipped. Check `publish-to-pypi` specifically.
5. Confirm `pip install ghc-compiler-python` on a clean machine, compile a
   Haskell file, and **run the binary**. Builds ≠ installs ≠ compiles ≠
   delivered.

## Support

If this project is useful to you, you can support its development here:

**[☕ ko-fi.com/saimonokuma](https://ko-fi.com/saimonokuma)**

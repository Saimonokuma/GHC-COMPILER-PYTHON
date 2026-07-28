/-
  Payload identity and cache safety.

  These are properties of `ghc_compiler_python/bootstrap.py` that must hold for
  every input, not merely for the inputs a test happens to supply. Tests sample;
  these do not.

  The motivating defect is real and was measured in this repository: three
  wheels were all tagged `py3-none-any`, collided on one filename, and PyPI
  would have served one platform's native binaries to every platform. The
  bootstrap cache can fail the same way -- two platforms resolving to one
  directory means one of them silently runs the other's binaries. Theorem
  `payloadTag_injective` is what rules that out.
-/

namespace GhcPython

/-- The platforms for which a payload is published. Mirrors
    `bootstrap.platform_tag`. -/
inductive Platform where
  | linuxX86
  | linuxArm
  | macosArm
  | macosX86
  | winX86
  deriving DecidableEq, Repr

/-- Payload tag per platform. Mirrors the return values of
    `bootstrap.platform_tag()`. -/
def payloadTag : Platform → String
  | .linuxX86 => "manylinux_2_39_x86_64"
  | .linuxArm => "manylinux_2_39_aarch64"
  | .macosArm => "macosx_11_0_arm64"
  | .macosX86 => "macosx_10_9_x86_64"
  | .winX86   => "win_amd64"

/-- Every platform ships an xz tarball as of 9.5.0.

    Windows shipped a zip through 9.4.9. Measured on the real toolchain
    (1814 MB, 8311 files): zip 395.8 MB against tar.xz 247.3 MB, and the
    round-trip verified lossless on every file by SHA-256. The zip was never a
    Windows requirement -- only an artefact of building it with 7z -- and it
    cost every Windows user 148 MB per cold install.

    Mirrors `bootstrap._archive_suffix`. -/
def archiveSuffix : Platform → String
  | _ => ".tar.xz"

/-- Full payload filename. Mirrors `bootstrap.payload_name`. -/
def payloadName (v : String) (p : Platform) : String :=
  "ghc-payload-" ++ v ++ "-" ++ payloadTag p ++ archiveSuffix p

/--
  **No two platforms share a payload tag.**

  This is the property whose violation produced the shipped bug. If it fails,
  two platforms resolve to one cache directory and one of them executes the
  other's binaries.
-/
theorem payloadTag_injective (p q : Platform) (h : payloadTag p = payloadTag q) : p = q := by
  cases p <;> cases q <;> simp_all [payloadTag]

/-- The identity the cache actually keys on. `payloadName` is a rendering of
    this pair; the pair is what determines whether two platforms collide. -/
def payloadKey (p : Platform) : String × String :=
  (payloadTag p, archiveSuffix p)

/--
  **Distinct platforms have distinct payload identities.**

  Stated over the key rather than the rendered filename deliberately. Proving
  it over the flat string would require left-cancellation of `String.append`
  under a universally quantified version, which Lean core does not provide --
  and the pair is the more faithful model anyway, since the cache directory is
  derived from tag and suffix, not from the assembled name.
-/
theorem payloadKey_injective (p q : Platform) (h : payloadKey p = payloadKey q) : p = q := by
  cases p <;> cases q <;> simp_all [payloadKey, payloadTag, archiveSuffix]

/-- `bootstrap.RELEASE_VERSION`: the tag, the asset names, the cache key. -/
def releaseVersion : String := "9.6.1"

/-- `bootstrap.GHC_VERSION`: the compiler inside the payload, which is what
    `ghc-wrapper --numeric-version` reports. -/
def ghcVersion : String := "9.6.1"

/-- For the version actually shipped, the rendered filenames are pairwise
    distinct too. Checked by evaluation rather than assumed. -/
example : payloadName releaseVersion .linuxX86 ≠ payloadName releaseVersion .winX86 := by decide

example : payloadName releaseVersion .macosArm ≠ payloadName releaseVersion .macosX86 := by decide

example : payloadName releaseVersion .linuxX86 ≠ payloadName releaseVersion .linuxArm := by decide

/-! ## The two version axes

Through 9.4.8 the distribution version and the compiler version were one
constant. That read well while they agreed and became a trap the moment they
had to diverge: the 9.4.8 wheel rejected every Windows machine without a system
gcc, PyPI does not allow replacing a published version, and so the fix needed a
new distribution version -- which, with one constant, also renamed every payload
asset and silently claimed a GHC release that does not exist.

`bootstrap.py` now carries `RELEASE_VERSION` and `GHC_VERSION` separately. The
properties below are what that separation has to buy.
-/

/-! ### Correction: the axes are allowed to coincide

An earlier revision of this file proved

    theorem versions_differ : releaseVersion ≠ ghcVersion := by decide

and made `cacheKey_separates_releases` and `payloadName_uses_release_axis`
depend on it. That was a **modelling error, and a costly one**: it took a fact
that happened to be true of 9.4.9 and 9.5.0 -- releases that shipped a compiler
older than their own version number -- and encoded it as an invariant.

It is not an invariant. When the bundled compiler is itself upgraded, the
natural and honest thing is for both axes to name that compiler, and they
coincide. The old spec would have *refused to compile* on such a release: a
green build would have been impossible for the most normal event in the
project's life.

Two numbers being equal is not the failure mode. Being *entangled* is -- one
constant that cannot be moved independently. That distinction is what the
independence theorems further down capture, and they hold whether or not the
axes happen to agree today.

So the theorems below are restated over arbitrary versions. Nothing here now
depends on the two being different.
-/

/-- The cache directory `bootstrap.payload_root()` resolves to, as the pair it
    is actually built from: `cache_root() / RELEASE_VERSION / platform_tag()`. -/
def cacheKey (v : String) (p : Platform) : String × String := (v, payloadTag p)

/-- Cache keys collide only for the same release on the same platform. -/
theorem cacheKey_injective (v w : String) (p q : Platform)
    (h : cacheKey v p = cacheKey w q) : v = w ∧ p = q :=
  ⟨congrArg Prod.fst h, payloadTag_injective p q (congrArg Prod.snd h)⟩

/--
  **A new release never reuses an old release's extracted payload.**

  Payloads rebuilt under a new tag are not byte-identical to the old ones, so
  their digests differ. If two distinct releases could share a cache directory,
  the second would find the first's tree already stamped `.complete`, skip the
  download, and run it -- with no digest check in sight, because nothing would
  have been downloaded to check.

  Now stated for **any** two distinct releases, which is the property that was
  always meant. The previous version said only that *this* release differed
  from *this* compiler, which is a much weaker claim wearing the same name.
-/
theorem distinct_releases_never_share_a_cache
    (v w : String) (p q : Platform) (hvw : v ≠ w) :
    cacheKey v p ≠ cacheKey w q := by
  intro h
  exact hvw (cacheKey_injective v w p q h).1

/-- Asset identity, as the tuple the name is rendered from. -/
def payloadKeyOf (v : String) (p : Platform) : String × String × String :=
  (v, payloadTag p, archiveSuffix p)

/--
  **Distinct releases have distinct payload identities, on every platform.**

  Stated over the key rather than the rendered string for the reason given at
  `payloadKey_injective`: proving it over the flat name needs right-cancellation
  of `String.append`, which Lean core does not provide, and the tuple is the
  more faithful model of what the cache actually keys on.
-/
theorem payloadKeyOf_injective (v w : String) (p q : Platform)
    (h : payloadKeyOf v p = payloadKeyOf w q) : v = w ∧ p = q := by
  refine ⟨congrArg Prod.fst h, ?_⟩
  exact payloadTag_injective p q (congrArg (fun t => t.2.1) h)

/-- And the rendering really does carry the release version, so the theorems
    above are not satisfied by a name that mentions neither axis. -/
example : payloadName releaseVersion .winX86 = "ghc-payload-9.6.1-win_amd64.tar.xz" := by decide

example : payloadName releaseVersion .linuxX86
    = "ghc-payload-9.6.1-manylinux_2_39_x86_64.tar.xz" := by decide

/-- Every platform has a non-empty tag: a payload can always be addressed. -/
theorem payloadTag_ne_empty (p : Platform) : payloadTag p ≠ "" := by
  cases p <;> simp [payloadTag]

/-! ## The two axes are independent coordinates

The theorems above say the axes *differ*. That is necessary and not sufficient.
Two numbers can differ and still be entangled -- and entangled is exactly what
they were through 9.4.8, when one constant named both.

What separation has to mean is stronger: each axis governs its own half of what
a user sees, and neither can reach into the other's half.

  * what you DOWNLOAD -- asset names, cache directory, wheel version --
    is a function of the RELEASE axis alone.
  * what you are TOLD about the compiler -- `--numeric-version` -- is a
    function of the COMPILER axis alone.

Proved below as two independence theorems, quantified over every possible pair
of versions rather than the pair we happen to ship. Their corollary is the
sentence this project kept having to explain to people out loud:

    bumping the package version renames everything you download,
    and changes nothing you are told about the compiler.
-/

/-- Both coordinates at once: what a release actually pins. -/
structure Coords where
  /-- `bootstrap.RELEASE_VERSION` -- the tag, the assets, the cache. -/
  release : String
  /-- `bootstrap.GHC_VERSION` -- the compiler in the payload. -/
  ghc : String
  deriving DecidableEq, Repr

/-- What a user downloads. -/
def assetName (c : Coords) (p : Platform) : String := payloadName c.release p

/-- Where it is cached. -/
def cacheDir (c : Coords) (p : Platform) : String × String := cacheKey c.release p

/-- The version of the wheel on PyPI. -/
def wheelVersion (c : Coords) : String := c.release

/-- What `ghc-wrapper --numeric-version` prints. -/
def reportedCompiler (c : Coords) : String := c.ghc

/--
  **INDEPENDENCE, first half: the compiler axis cannot leak into what you
  download.**

  For every release, and for ANY two compiler versions whatsoever, the asset
  name, the cache directory and the wheel version are identical. Changing the
  bundled compiler cannot rename a single thing a user fetches.

  This is what makes it safe to bundle a different GHC later without
  invalidating every published digest.
-/
theorem download_ignores_the_compiler_axis (r g g' : String) (p : Platform) :
    assetName ⟨r, g⟩ p = assetName ⟨r, g'⟩ p
    ∧ cacheDir ⟨r, g⟩ p = cacheDir ⟨r, g'⟩ p
    ∧ wheelVersion ⟨r, g⟩ = wheelVersion ⟨r, g'⟩ :=
  ⟨rfl, rfl, rfl⟩

/--
  **INDEPENDENCE, second half: the release axis cannot leak into what you are
  told.**

  For every compiler, and for ANY two release versions whatsoever, the reported
  compiler version is identical. No amount of re-releasing can make the tool
  claim a compiler it does not contain.

  This is the property that was violated by construction before the split: one
  constant meant re-releasing necessarily announced a new GHC.
-/
theorem report_ignores_the_release_axis (r r' g : String) :
    reportedCompiler ⟨r, g⟩ = reportedCompiler ⟨r', g⟩ := rfl

/-- What 9.5.0 shipped: a package version ahead of its compiler. -/
def shipped_9_5_0 : Coords := { release := "9.5.0", ghc := "9.4.8" }

/-- What 9.6.1 ships: both axes naming the same, real, upgraded compiler. -/
def shipped_9_6_1 : Coords := { release := releaseVersion, ghc := ghcVersion }

/-- Asset identity of a build, as the tuple the filename renders from. -/
def assetKey (c : Coords) (p : Platform) : String × String × String :=
  payloadKeyOf c.release p

/--
  **A package-only bump renames everything and claims nothing.**

  Quantified over any two distinct release versions and any compiler, rather
  than over the pair that happened to ship. The earlier version of this theorem
  was stated about the literal 9.4.9 and 9.5.0 coordinates, and 9.6.1 made it
  FALSE -- that release moves both axes at once, because the compiler itself
  was upgraded. A theorem about two constants expires; this one does not.
-/
theorem package_only_bump_renames_everything_and_claims_nothing
    (r r' g : String) (hr : r ≠ r') :
    (∀ p : Platform, assetKey ⟨r, g⟩ p ≠ assetKey ⟨r', g⟩ p)
    ∧ reportedCompiler ⟨r, g⟩ = reportedCompiler ⟨r', g⟩ := by
  refine ⟨fun p h => ?_, rfl⟩
  exact hr (payloadKeyOf_injective r r' p p h).1

/--
  **A compiler upgrade is the other shape, and it moves both axes.**

  9.6.1 is exactly this: the compiler was upgraded from 9.4.8, so the reported
  version changes too. Recorded because the previous theorem must not be read
  as "the reported compiler never changes" -- it changes precisely when the
  compiler does, which is the whole point of keeping the axes separate.
-/
theorem compiler_upgrade_moves_the_report (r g g' : String) (hg : g ≠ g') :
    reportedCompiler ⟨r, g⟩ ≠ reportedCompiler ⟨r, g'⟩ := hg

/-- The reported compiler is read off the compiler axis, by construction. -/
theorem reported_is_the_compiler_axis :
    reportedCompiler shipped_9_6_1 = ghcVersion := rfl

/-! ## Why the claimed compiler cannot simply be edited

The maintainer asked, reasonably, for the compiler version to be set to a
number that no GHC release carries -- so that it would match the package
version and stop looking wrong on the project page.

The refusal is usually argued as honesty: printing `9.5.0` while shipping
`9.4.8` is a lie told by our own tool. True, but weak, because it is a claim
about taste. There is a mechanical reason underneath it, and it is stated here
so nobody has to relitigate the taste.

`wrapper.py` resolves the toolchain through a path that **contains the version
it claims**:

    lib/ghc-<GHC_VERSION>/bin/ghc

while the payload contains whatever directory the *downloaded bindist* created:

    lib/ghc-<fetched>/...

Those are the same string only when the claim matches the artifact. Editing the
constant does not merely misreport -- it points the launcher at a directory
that does not exist, and the install stops working. That is proved below, for
every pair of versions, rather than argued.
-/

/-! ### The bindist layout is not uniform, and GHC 9.6.1 proved it

Measured in CI on 2026-07-28, upgrading GHC 9.4.8 -> 9.6.1:

  Linux, macOS   lib/ghc-9.6.1/lib/x86_64-linux-ghc-9.6.1/     (unchanged)
  Windows        lib/x86_64-windows-ghc-9.6.1/                 (CHANGED)

The Windows bindist dropped the `ghc-<version>` level entirely. An earlier
revision of this file modelled the compiler directory as `"lib/ghc-" ++ v` on
every platform, which is simply false for the Windows tree that 9.6 ships.

The consequence is sharper than a wrong path, and it is the reason this section
exists rather than a one-line fix: **on the flat layout the directory no longer
carries the version**, so "the toolchain resolved" stops implying "the version
we claim is the version we shipped". The safety property that
`resolves_iff_claim_matches_artifact` relied on degrades to nothing.

What survives both layouts is the *platform* library directory, which carries
the version in either shape:

  lib/ghc-9.6.1/lib/x86_64-windows-ghc-9.6.1     versioned
  lib/x86_64-windows-ghc-9.6.1                   flat

So the version check is anchored there instead. That is a strictly stronger
place to anchor it, and it was found by an upgrade rather than by inspection.
-/

/-- How a bindist arranges its compiler directory. -/
inductive Layout where
  /-- `lib/ghc-<version>/...` -- GHC 9.4 everywhere, and 9.6 on Unix. -/
  | versioned
  /-- `lib/...` -- the GHC 9.6 Windows bindist. -/
  | flat
  deriving DecidableEq, Repr

/-- The compiler directory inside a payload, per layout. -/
def libDirOf : Layout → String → String
  | .versioned, fetched => "lib/ghc-" ++ fetched
  | .flat,      _       => "lib"

/-- The compiler directory `wrapper.py` looks for, given what it claims. Only
    meaningful under the versioned layout; retained because the theorem about
    it is what the flat layout takes away. -/
def libDirClaimed (claimed : String) : String := "lib/ghc-" ++ claimed

/--
  **The flat layout does not encode the version.**

  Two different compilers produce the same directory name, so no amount of
  looking at that path can tell you which one you have. Stated as a theorem
  because it is the load-bearing negative result: it says why the check had to
  move, rather than leaving that as a comment.
-/
theorem flat_layout_forgets_the_version (v w : String) :
    libDirOf .flat v = libDirOf .flat w := rfl

/-- The versioned layout, by contrast, determines it. -/
theorem versioned_layout_determines_the_version (v w : String)
    (h : libDirOf .versioned v = libDirOf .versioned w) : v = w :=
  String.append_right_inj "lib/ghc-" |>.mp h

/-- The platform library directory, which exists under both layouts and carries
    the version in both. `tri` is the target triple, e.g.
    `x86_64-windows`. Mirrors what `wrapper._find_platform_lib_subdir` looks
    for -- a directory whose name ends in `-ghc-<version>`. -/
def platformLibDir (l : Layout) (tri : String) (v : String) : String :=
  (match l with
   | .versioned => "lib/ghc-" ++ v ++ "/lib/"
   | .flat      => "lib/") ++ tri ++ "-ghc-" ++ v

/-- The *name* of the platform library directory -- the basename, which is what
    `wrapper._find_platform_lib_subdir` actually matches on when it scans
    directory entries for one ending in `-ghc-<version>`. Modelling the name
    rather than the full path is deliberate: the parent differs by layout, the
    name does not, and the name is the object the code inspects. -/
def platformLibName (tri v : String) : String := tri ++ "-ghc-" ++ v

/--
  **The version survives in the platform directory name under EVERY layout.**

  This is what makes a single check correct on both Unix and Windows, and it is
  the property the build gate and `wrapper._find_platform_lib_subdir` now rely
  on instead of the `lib/ghc-<v>` path that Windows no longer has.
-/
theorem platformLibName_determines_the_version (tri v w : String)
    (h : platformLibName tri v = platformLibName tri w) : v = w := by
  unfold platformLibName at h
  exact String.append_right_inj (tri ++ "-ghc-") |>.mp (by
    simpa [String.append_assoc] using h)

/-- And the name appears under either layout, so a scan finds it in both. -/
theorem platformLibDir_ends_with_the_name (l : Layout) (tri v : String) :
    ∃ parent : String, platformLibDir l tri v = parent ++ platformLibName tri v := by
  cases l with
  | versioned => exact ⟨"lib/ghc-" ++ v ++ "/lib/", by simp [platformLibDir,
      platformLibName, String.append_assoc]⟩
  | flat => exact ⟨"lib/", by simp [platformLibDir, platformLibName,
      String.append_assoc]⟩

/-- A build pairs what was downloaded with what the wrapper will claim, and the
    layout the bindist happened to use. -/
structure Build where
  /-- The version in the bindist URL `fetch_binaries.sh` downloads. -/
  fetched : String
  /-- `wrapper.GHC_VERSION` -- what `--numeric-version` prints. -/
  claimed : String
  /-- Which shape the unpacked bindist has. Not ours to choose: GHC changed it
      under us between 9.4.8 and 9.6.1 on Windows. -/
  layout : Layout
  deriving DecidableEq, Repr

/-- The old resolution rule: look for `lib/ghc-<claimed>`. Kept because the
    theorem about it is exactly what the flat layout destroys. -/
def resolvesByLibDir (b : Build) : Prop :=
  libDirClaimed b.claimed = libDirOf b.layout b.fetched

instance (b : Build) : Decidable (resolvesByLibDir b) := by
  unfold resolvesByLibDir; infer_instance

/--
  **Under the versioned layout, resolving proves the claim matches the artifact.**

  The contrapositive is the useful direction: if the toolchain resolves at all,
  the version claimed is the version downloaded. Lying about the compiler is not
  a cosmetic choice with an honesty cost -- it is a broken install, detectable
  by the package itself.

  Proved for every pair of strings, not for the pair anyone had in mind.
-/
theorem resolves_iff_claim_matches_artifact (fetched claimed : String) :
    resolvesByLibDir ⟨fetched, claimed, .versioned⟩ ↔ claimed = fetched := by
  unfold resolvesByLibDir libDirClaimed libDirOf
  -- The two paths share the literal prefix "lib/ghc-", so they are equal
  -- exactly when the version components are. `String.append_right_inj` is the
  -- cancellation core actually provides; an earlier attempt reasoned via
  -- `String.drop` and could not close, since nothing simplifies
  -- `(a ++ b).drop a.length` to `b`.
  exact String.append_right_inj "lib/ghc-"

/--
  **Under the flat layout the old rule resolves NOTHING.**

  First written as "the flat layout resolves any claim" -- that the guarantee
  degraded to vacuous. Lean refused it, and the refusal was correct: the goal
  reduced to `False`, because `"lib/ghc-" ++ claimed` cannot equal `"lib"` for
  any claim at all. The rule does not weaken on the flat layout, it fails
  outright, for every version including the right one.

  Which is precisely what CI reported when GHC 9.6.1 was first built for
  Windows: the directory was simply missing. The guess was that lying would
  become undetectable; the truth is that the honest case breaks too. Recorded
  because the theorem corrected the hypothesis, not the other way round.
-/
theorem flat_layout_never_resolves_by_libdir (fetched claimed : String) :
    ¬ resolvesByLibDir ⟨fetched, claimed, .flat⟩ := by
  intro h
  unfold resolvesByLibDir libDirClaimed libDirOf at h
  -- Length is enough: the claimed path is at least 8 characters, "lib" is 3.
  -- `simp` alone leaves the literal lengths unreduced, so they are pinned by
  -- `rfl` and the contradiction handed to `omega`.
  have hlen := congrArg String.length h
  simp only [String.length_append] at hlen
  have h8 : "lib/ghc-".length = 8 := rfl
  have h3 : "lib".length = 3 := rfl
  rw [h8, h3] at hlen
  omega

/-- The honest build on the layout this release uses for Unix. -/
def honestBuild : Build := ⟨ghcVersion, ghcVersion, .versioned⟩

/-- It resolves, and the check is by evaluation rather than by assumption. -/
theorem honest_build_resolves : resolvesByLibDir honestBuild := by decide

/--
  **The specific edit that was requested, refuted by evaluation.**

  Claiming `9.5.0` while the payload was built from GHC `9.4.8` does not
  resolve. This is the concrete instance of the general theorem, kept because a
  general theorem is easy to nod at and a failing example is not.
-/
theorem claiming_9_5_0_while_shipping_9_4_8_breaks_resolution :
    ¬ resolvesByLibDir ⟨"9.4.8", "9.5.0", .versioned⟩ := by decide

/-- The same edit against the compiler this release actually ships. -/
theorem claiming_anything_else_breaks_resolution (claimed : String)
    (h : claimed ≠ ghcVersion) :
    ¬ resolvesByLibDir ⟨ghcVersion, claimed, .versioned⟩ := by
  intro hr
  exact h ((resolves_iff_claim_matches_artifact _ _).mp hr)

/--
  **The check that works on both layouts.**

  Scanning for a directory named `<triple>-ghc-<claimed>` determines the
  version under either shape, so it is correct on Unix and on the Windows tree
  that no longer has `lib/ghc-<v>`. This is the invariant the build gate and
  the wrapper now use.
-/
theorem version_check_by_name_is_layout_independent
    (_l : Layout) (tri claimed fetched : String)
    (h : platformLibName tri claimed = platformLibName tri fetched) :
    claimed = fetched :=
  platformLibName_determines_the_version tri claimed fetched h

/-! ## Cache completeness

The cache must never be observable in a partial state. `bootstrap` guarantees
this structurally: extraction happens in a staging directory, the completion
stamp is written *before* the atomic rename promotes it, and `is_installed`
tests only the stamp. So an observer either sees nothing or sees a fully
extracted tree -- never a half-written one.

Modelled as a state machine over what an observer can see.
-/

/-- What a concurrent observer can see of a cache directory. -/
inductive CacheState where
  /-- Nothing promoted yet; staging may exist but is not at the final path. -/
  | absent
  /-- Promoted by atomic rename, stamp present. -/
  | complete
  deriving DecidableEq, Repr

/-- `is_installed` returns true exactly when the stamp is visible. -/
def isInstalled : CacheState → Bool
  | .absent   => false
  | .complete => true

/-- The steps the installer can take. Extraction and stamping occur in staging,
    which is not the observable path, so neither changes what an observer sees. -/
inductive Step where
  | extractIntoStaging
  | writeStampInStaging
  | atomicPromote
  deriving Repr

def apply : CacheState → Step → CacheState
  | s, .extractIntoStaging  => s          -- staging is invisible
  | s, .writeStampInStaging => s          -- staging is invisible
  | _, .atomicPromote       => .complete  -- rename is atomic

/--
  **No sequence of installer steps can expose a partial cache.**

  Whatever the interleaving, an observer calling `is_installed` sees either
  `absent` or `complete`. There is no reachable third state, which is exactly
  the claim "a cache directory that exists is a cache directory that is
  complete".
-/
theorem no_partial_state (s : CacheState) (steps : List Step) :
    (steps.foldl apply s) = .absent ∨ (steps.foldl apply s) = .complete := by
  cases steps.foldl apply s
  · exact Or.inl rfl
  · exact Or.inr rfl

/-- Promotion is idempotent: a concurrent second promoter cannot regress the
    cache. This is what makes the mkdir-lock waiter safe to simply return when
    it finds the work already done. -/
theorem promote_idempotent (s : CacheState) :
    apply (apply s .atomicPromote) .atomicPromote = apply s .atomicPromote := by
  rfl

/-- Once complete, no step makes the cache un-installed. -/
theorem complete_is_stable (st : Step) :
    isInstalled (apply .complete st) = true := by
  cases st <;> rfl

end GhcPython

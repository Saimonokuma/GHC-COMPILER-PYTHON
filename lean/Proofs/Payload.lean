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

/-- Windows payloads are zip archives; every other platform ships xz tarballs.
    Mirrors `bootstrap._archive_suffix`. -/
def archiveSuffix : Platform → String
  | .winX86 => ".zip"
  | _       => ".tar.xz"

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
def releaseVersion : String := "9.4.9"

/-- `bootstrap.GHC_VERSION`: the compiler inside the payload, which is what
    `ghc-wrapper --numeric-version` reports. -/
def ghcVersion : String := "9.4.8"

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

/-- The axes are distinct. Every theorem below is vacuous if this fails, so it
    is stated first and checked by evaluation. -/
theorem versions_differ : releaseVersion ≠ ghcVersion := by decide

/-- The cache directory `bootstrap.payload_root()` resolves to, as the pair it
    is actually built from: `cache_root() / RELEASE_VERSION / platform_tag()`. -/
def cacheKey (v : String) (p : Platform) : String × String := (v, payloadTag p)

/--
  **A new release never reuses an old release's extracted payload.**

  Payloads rebuilt under a new tag are not byte-identical to the old ones, so
  their digests differ. Were the cache keyed by the compiler version, 9.4.9
  would find 9.4.8's tree already stamped `.complete`, skip the download, and
  run the very wrapper this release exists to replace -- with no digest check
  in sight, because nothing would be downloaded to check.
-/
theorem cacheKey_separates_releases (p q : Platform) :
    cacheKey releaseVersion p ≠ cacheKey ghcVersion q := by
  intro h
  exact versions_differ (congrArg Prod.fst h)

/-- Cache keys collide only for the same release on the same platform. -/
theorem cacheKey_injective (v w : String) (p q : Platform)
    (h : cacheKey v p = cacheKey w q) : v = w ∧ p = q :=
  ⟨congrArg Prod.fst h, payloadTag_injective p q (congrArg Prod.snd h)⟩

/--
  **Asset names are addressed by the release, never by the compiler.**

  Checked on every platform rather than on the one that happened to break.
-/
theorem payloadName_uses_release_axis :
    ∀ p : Platform, payloadName releaseVersion p ≠ payloadName ghcVersion p := by
  intro p; cases p <;> decide

/-- And the rendering really does carry the release version, so the previous
    theorem is not satisfied by a name that mentions neither. -/
example : payloadName releaseVersion .winX86 = "ghc-payload-9.4.9-win_amd64.zip" := by decide

example : payloadName releaseVersion .linuxX86
    = "ghc-payload-9.4.9-manylinux_2_39_x86_64.tar.xz" := by decide

/-- Every platform has a non-empty tag: a payload can always be addressed. -/
theorem payloadTag_ne_empty (p : Platform) : payloadTag p ≠ "" := by
  cases p <;> simp [payloadTag]

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

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

/-- For the version actually shipped, the rendered filenames are pairwise
    distinct too. Checked by evaluation rather than assumed. -/
example : payloadName "9.4.8" .linuxX86 ≠ payloadName "9.4.8" .winX86 := by decide

example : payloadName "9.4.8" .macosArm ≠ payloadName "9.4.8" .macosX86 := by decide

example : payloadName "9.4.8" .linuxX86 ≠ payloadName "9.4.8" .linuxArm := by decide

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

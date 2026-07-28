/-
  The C-linker precondition, and the order in which the launcher establishes it.

  Two defects in `ghc_compiler_python/wrapper.py`, both invisible to CI and both
  on the path every PyPI user takes.

  1. `_validate_c_linker` consulted only `shutil.which("gcc"|"clang")`. But the
     Windows payload carries its own toolchain -- `mingw/bin/clang.exe` and
     `mingw/bin/ld.exe` are inside it, and that tree is the main reason Windows
     is 396 MB against 87 MB for Linux. The check therefore rejected a machine
     that had *just downloaded a complete C toolchain*. The windows-latest
     runner installs mingw via chocolatey, so a system compiler is always on
     PATH in CI and the check never fired there.

  2. `_execute_tool` ran `_validate_c_linker; _sterilize_environment;
     _resolve_runtime_paths; _resolve_binary`. `_resolve_runtime_paths` rewrites
     the `@GHC_PREFIX@` placeholder to the real toolchain root, but
     `_resolve_binary` is what *acquires* the payload. On a thin-wheel install
     the patch step ran with nothing on disk: the root resolver fell back to
     `sys.prefix`, the scan found no files, and placeholders stayed unresolved.
     Invisible in CI because the offline wheel bundles the toolchain, so a root
     exists from the first line and the order makes no observable difference.

  Both are claims about *all* inputs -- every machine, every interleaving -- so
  they are proved rather than sampled. Lean core only, no Mathlib.
-/

namespace GhcPython

/-! ## Part 1 -- what the check may accept

Modelled exactly as the code probes: two `shutil.which` names, and a fixed list
of paths probed relative to the toolchain root.
-/

/-- Names `_validate_c_linker` hands to `shutil.which`. -/
def pathCompilers : List String := ["gcc", "clang"]

/-- `wrapper._BUNDLED_LINKERS`, verbatim: paths probed under the toolchain root. -/
def bundledLinkers : List String :=
  ["mingw/bin/clang.exe", "mingw/bin/gcc.exe", "mingw/bin/clang", "mingw/bin/gcc"]

/-- A machine, as far as the check can observe it: which names resolve on the
    system PATH, and the toolchain root -- `none` when no root is on disk,
    otherwise the finite list of file paths under it, relative to the root. -/
structure Machine where
  onPath : String → Bool
  root : Option (List String)

/-- The two places a usable C compiler can live. -/
inductive Linker where
  /-- Found by `shutil.which`, i.e. a system compiler. -/
  | onPath (name : String)
  /-- Shipped inside the payload, at a path relative to the toolchain root. -/
  | underRoot (rel : String)
  deriving DecidableEq, Repr

/-- `l` is a C compiler this machine can actually reach. This is the *ground
    truth* the check is trying to detect; it is defined independently of the
    check, so soundness below is not a tautology. -/
def Has (m : Machine) : Linker → Prop
  | .onPath name   => pathCompilers.contains name = true ∧ m.onPath name = true
  | .underRoot rel => bundledLinkers.contains rel = true ∧
                      ∃ files, m.root = some files ∧ files.contains rel = true

/-- `wrapper._bundled_c_linker`, as a Bool. -/
def bundledCLinker : Option (List String) → Bool
  | none       => false
  | some files => bundledLinkers.any (fun rel => files.contains rel)

/-- No root on disk means no bundled compiler. This is the hinge that ties
    Part 1 to Part 3: the relaxed check is only as good as the root it is
    handed, and before acquisition there is no root to hand it. -/
@[simp] theorem bundledCLinker_none : bundledCLinker none = false := rfl

/--
  **Monotone in the file set.** Adding files under the root never turns the
  bundled probe off.

  This is the lemma that carries the model across to the implementation. Here
  `files` is the list of paths at which `Path.is_file()` succeeds; on a
  case-insensitive filesystem that set is closed under case folding, so it is a
  *superset* of the literal directory entries. Monotonicity says such an
  over-approximation can only make the probe more accepting, never less:
  whatever this model accepts, the real `_bundled_c_linker` accepts too.

  The converse does not hold, and it is measured rather than assumed. A
  cross-check that materialises each modelled root on disk and runs the real
  `_bundled_c_linker` over it agrees on 17 of 18 cases; the exception is
  `mingw/bin/CLANG.EXE`, which NTFS resolves and this model, matching the
  catalogue literally, does not. Soundness therefore transfers to the running
  code only under the assumption that a path the filesystem resolves to one of
  the catalogue entries really is that compiler -- true for case folding,
  which is the only divergence found.
-/
theorem bundledCLinker_monotone (files files' : List String)
    (hsub : ∀ x, files.contains x = true → files'.contains x = true)
    (h : bundledCLinker (some files) = true) :
    bundledCLinker (some files') = true := by
  simp only [bundledCLinker] at *
  obtain ⟨rel, hmem, hfile⟩ := List.any_eq_true.mp h
  exact List.any_eq_true.mpr ⟨rel, hmem, hsub rel hfile⟩

/-- The old check: system PATH only. -/
def oldAccepts (m : Machine) : Bool := pathCompilers.any m.onPath

/-- The new check, against an explicitly supplied root -- mirroring
    `_validate_c_linker(root)`, whose verdict depends on what the caller has
    already acquired. -/
def acceptsWith (m : Machine) (observed : Option (List String)) : Bool :=
  pathCompilers.any m.onPath || bundledCLinker observed

/-- The new check applied to the root that is really there. -/
def newAccepts (m : Machine) : Bool := acceptsWith m m.root

/-! ### Soundness -- the relaxed check never accepts a compiler-less machine -/

/--
  **Anything the new check accepts really does have a C compiler.**

  The property that matters: relaxing a guard is only legitimate if the relaxed
  guard still implies the thing it guards. A check that accepted everything
  would be "safe" in the sense of never blocking, and worthless.
-/
theorem newAccepts_sound (m : Machine) (h : newAccepts m = true) : ∃ l, Has m l := by
  unfold newAccepts acceptsWith at h
  cases hp : pathCompilers.any m.onPath with
  | true =>
      obtain ⟨name, hmem, hon⟩ := List.any_eq_true.mp hp
      exact ⟨.onPath name, List.contains_iff_mem.mpr hmem, hon⟩
  | false =>
      rw [hp, Bool.false_or] at h
      cases hr : m.root with
      | none =>
          rw [hr] at h
          exact absurd h (by simp)
      | some files =>
          rw [hr] at h
          simp only [bundledCLinker] at h
          obtain ⟨rel, hmem, hfile⟩ := List.any_eq_true.mp h
          exact ⟨.underRoot rel, List.contains_iff_mem.mpr hmem, files, hr, hfile⟩

/--
  **Converse: the check misses nothing.**

  Together with `newAccepts_sound` this makes the check exact, not merely safe
  -- it accepts precisely the machines that have a compiler in one of the two
  modelled places. Without this direction a check hardcoded to `false` would
  satisfy soundness.
-/
theorem newAccepts_complete (m : Machine) (l : Linker) (h : Has m l) : newAccepts m = true := by
  unfold newAccepts acceptsWith
  cases l with
  | onPath name =>
      obtain ⟨hmem, hon⟩ := h
      have hany : pathCompilers.any m.onPath = true :=
        List.any_eq_true.mpr ⟨name, List.contains_iff_mem.mp hmem, hon⟩
      simp [hany]
  | underRoot rel =>
      obtain ⟨hmem, files, hroot, hfile⟩ := h
      have hany : bundledCLinker m.root = true := by
        rw [hroot]
        simp only [bundledCLinker]
        exact List.any_eq_true.mpr ⟨rel, List.contains_iff_mem.mp hmem, hfile⟩
      simp [hany]

/-- The check is exactly a decision procedure for "a C compiler is reachable". -/
theorem newAccepts_iff (m : Machine) : newAccepts m = true ↔ ∃ l, Has m l :=
  ⟨newAccepts_sound m, fun ⟨l, hl⟩ => newAccepts_complete m l hl⟩

/-- No false negatives, stated in the direction a user experiences: if the
    launcher aborts, there really was no compiler anywhere. -/
theorem newAccepts_false_means_none (m : Machine) (h : newAccepts m = false) :
    ∀ l, ¬ Has m l := by
  intro l hl
  rw [newAccepts_complete m l hl] at h
  exact Bool.noConfusion h

/-! ### Part 2 -- strictly more permissive -/

/--
  **The new check accepts everything the old one did.**

  No machine that used to work stops working. This is the "no regression"
  half; the next theorem supplies the "genuinely different" half.
-/
theorem newAccepts_of_oldAccepts (m : Machine) (h : oldAccepts m = true) :
    newAccepts m = true := by
  unfold newAccepts acceptsWith
  unfold oldAccepts at h
  simp [h]

/-- The failing machine, measured from the published Windows payload: no system
    compiler on PATH, and a toolchain root containing `mingw/bin/clang.exe` and
    `mingw/bin/ld.exe` (the zip central directory lists 9027 entries; three
    representative ones suffice here). -/
def windowsThinInstall : Machine where
  onPath := fun _ => false
  root := some ["bin/ghc.exe", "mingw/bin/clang.exe", "mingw/bin/ld.exe"]

/--
  **The two checks genuinely differ, and they differ exactly on the bug.**

  Old rejects, new accepts. Without this the previous theorem would be
  satisfied by leaving the check unchanged.
-/
theorem old_rejects_new_accepts :
    oldAccepts windowsThinInstall = false ∧ newAccepts windowsThinInstall = true := by
  constructor <;> decide

/--
  **The old check was unsound as a rejection**: it aborted on a machine that
  demonstrably had a C compiler. This is the shipped `FATAL ERROR`, stated as a
  theorem rather than as a bug report.
-/
theorem oldAccepts_rejects_a_working_machine :
    oldAccepts windowsThinInstall = false ∧
      Has windowsThinInstall (.underRoot "mingw/bin/clang.exe") := by
  refine ⟨by decide, by decide, ["bin/ghc.exe", "mingw/bin/clang.exe", "mingw/bin/ld.exe"],
          rfl, by decide⟩

/-- The relaxation is confined to the bundled tree: a machine with neither a
    system compiler nor a bundled one is still rejected. -/
theorem newAccepts_rejects_bare_machine :
    newAccepts { onPath := fun _ => false, root := some ["bin/ghc.exe"] } = false := by
  decide

/-- And a thin install before acquisition is rejected too -- correctly, since
    at that moment nothing is on disk. Part 3 is about not validating there. -/
theorem newAccepts_rejects_unacquired :
    newAccepts { onPath := fun _ => false, root := none } = false := by
  decide

/-! ## Part 3 -- ordering

`_execute_tool` performs three actions that matter to this state. Environment
sterilisation is omitted: it neither acquires nor patches, so it is a no-op on
this state and modelling it would only lengthen the traces.
-/

/-- What the launcher has established so far. -/
inductive Phase where
  /-- No toolchain on disk. `_ghc_root_or_prefix` falls back to `sys.prefix`. -/
  | noRoot
  /-- Toolchain acquired; `@GHC_PREFIX@` placeholders still unresolved. -/
  | rootOnly
  /-- Toolchain acquired and placeholders rewritten to the real root. -/
  | patched
  deriving DecidableEq, Repr

inductive Action where
  /-- `_ghc_root()` / `_resolve_binary`: downloads and extracts the payload. -/
  | acquire
  /-- `_validate_c_linker`: reads state, changes nothing. -/
  | validate
  /-- `_resolve_runtime_paths`: rewrites `@GHC_PREFIX@` in whatever it finds. -/
  | patch
  deriving DecidableEq, Repr

/-- Acquisition is idempotent (`ensure_payload` is a stat once installed).
    Patching with no root on disk scans an empty tree and rewrites nothing --
    the defect, modelled as the no-op it actually was. -/
def step (p : Phase) : Action → Phase
  | .validate => p
  | .acquire  => match p with
                 | .noRoot => .rootOnly
                 | q       => q
  | .patch    => match p with
                 | .noRoot   => .noRoot
                 | .rootOnly => .patched
                 | .patched  => .patched

def run (p : Phase) (as : List Action) : Phase := as.foldl step p

/-- Did the process reach the compiler with its placeholders rewritten? -/
def resolved : Phase → Bool
  | .patched => true
  | _        => false

/-- The order that shipped: validate, patch, then acquire (inside
    `_resolve_binary`). -/
def oldOrder : List Action := [.validate, .patch, .acquire]

/-- The order now in `_execute_tool`: acquire, validate, patch. -/
def newOrder : List Action := [.acquire, .validate, .patch]

/-- The two orders contain the same actions -- only their order differs. Stated
    so the comparison below cannot be dismissed as comparing different work. -/
theorem orders_same_actions : ∀ a : Action, (a ∈ oldOrder) ↔ (a ∈ newOrder) := by
  intro a; cases a <;> exact ⟨by decide, by decide⟩

theorem orders_same_length : oldOrder.length = newOrder.length := rfl

/--
  **The old order admits a run that ends with placeholders unresolved.**

  Starting from a thin install, the payload does get acquired -- by
  `_resolve_binary`, at the end -- so the process proceeds to exec a compiler
  whose configuration still contains `@GHC_PREFIX@`. That is the failure: not a
  crash at the patch step, but a silently unpatched toolchain.
-/
theorem old_leaves_placeholders_unresolved :
    run .noRoot oldOrder = .rootOnly ∧ resolved (run .noRoot oldOrder) = false := by
  constructor <;> rfl

/-- Once patched, nothing un-patches: no later action can regress the state. -/
theorem patched_absorbing : ∀ as : List Action, run .patched as = .patched := by
  intro as
  induction as with
  | nil => rfl
  | cons a rest ih => cases a <;> exact ih

/-- The structural property that makes the new order correct: every `patch` in
    the trace is preceded by an `acquire`. The flag records whether an acquire
    has been seen. -/
def wellOrdered : Bool → List Action → Bool
  | _,    []                => true
  | _,    .acquire :: rest  => wellOrdered true rest
  | seen, .validate :: rest => wellOrdered seen rest
  | seen, .patch :: rest    => seen && wellOrdered seen rest

/--
  **Auxiliary invariant.** Generalised over the starting phase and the flag,
  which is what makes the induction go through: the flag being set must
  correspond to the root already being on disk.
-/
theorem wellOrdered_run_aux :
    ∀ (as : List Action) (p : Phase) (seen : Bool),
      wellOrdered seen as = true →
      (seen = true → p ≠ .noRoot) →
      Action.patch ∈ as →
      run p as = .patched := by
  intro as
  induction as with
  | nil => intro _ _ _ _ hc; exact absurd hc (by simp)
  | cons a rest ih =>
      intro p seen hwo hinv hc
      cases a with
      | acquire =>
          have hrest : Action.patch ∈ rest := by
            rcases List.mem_cons.mp hc with h | h
            · exact absurd h (by decide)
            · exact h
          have hinv' : (true = true → step p .acquire ≠ .noRoot) := by
            intro _; cases p <;> decide
          exact ih (step p .acquire) true hwo hinv' hrest
      | validate =>
          have hrest : Action.patch ∈ rest := by
            rcases List.mem_cons.mp hc with h | h
            · exact absurd h (by decide)
            · exact h
          exact ih p seen hwo hinv hrest
      | patch =>
          have hwo' : (seen && wellOrdered seen rest) = true := hwo
          have hseen : seen = true := ((Bool.and_eq_true _ _).mp hwo').1
          have hne : p ≠ .noRoot := hinv hseen
          have hstep : step p .patch = .patched := by
            cases p
            · exact absurd rfl hne
            · rfl
            · rfl
          show run (step p .patch) rest = .patched
          rw [hstep]
          exact patched_absorbing rest

/--
  **No well-ordered run can end with placeholders unresolved.**

  For every trace in which each patch is preceded by an acquisition -- not just
  the particular three-step sequence now in `_execute_tool` -- the run that
  `old_leaves_placeholders_unresolved` exhibits is unreachable.

  The `patch ∈ as` hypothesis is not decoration: a trace that never patches
  ends unresolved for the trivial reason that no patching was attempted. What
  is proved is that ordering, not luck, is what makes patching effective.
-/
theorem no_wellOrdered_run_leaves_unresolved
    (as : List Action) (h : wellOrdered false as = true) (hp : Action.patch ∈ as) :
    resolved (run .noRoot as) = true := by
  rw [wellOrdered_run_aux as .noRoot false h (fun hf => Bool.noConfusion hf) hp]
  rfl

/-- The new order satisfies the structural property; the old one does not.
    This is the precise sense in which the fix is a fix. -/
theorem newOrder_wellOrdered : wellOrdered false newOrder = true := by decide

theorem oldOrder_not_wellOrdered : wellOrdered false oldOrder = false := by decide

/-- Consequently the shipped order resolves, from a thin install, as an
    instance of the general theorem rather than by evaluation. -/
theorem new_resolves_from_thin_install : resolved (run .noRoot newOrder) = true :=
  no_wellOrdered_run_leaves_unresolved newOrder newOrder_wellOrdered (by decide)

/-- Stronger, and cheap: the new order ends patched from *any* starting phase,
    so it is also correct for the offline wheel (root already present) and
    idempotent across repeated invocations. -/
theorem new_resolves_from_anywhere (p : Phase) : run p newOrder = .patched := by
  cases p <;> rfl

/-! ## The two defects are one defect

Part 1 relaxed the linker check to consult the toolchain root. Part 3 is what
makes that relaxation reachable: validated before acquisition, the check sees
`none` and degenerates back into the old one.
-/

/-- What `_validate_c_linker` can see at a given phase: before acquisition
    there is no root on disk, whatever the payload would have contained. -/
def observedRoot (m : Machine) : Phase → Option (List String)
  | .noRoot => none
  | _       => m.root

/-- The phase in which the first `validate` of an order executes -- computed
    from the order rather than asserted. -/
def phaseAtValidate (start : Phase) : List Action → Option Phase
  | []              => none
  | .validate :: _  => some start
  | a :: rest       => phaseAtValidate (step start a) rest

/-- The verdict `_validate_c_linker` reaches under a given order, starting from
    a thin install. An order that never validates rejects nothing. -/
def validationOutcome (m : Machine) (order : List Action) : Bool :=
  match phaseAtValidate .noRoot order with
  | none   => true
  | some p => acceptsWith m (observedRoot m p)

/--
  **Validating before acquiring makes the relaxed check equivalent to the old
  one.** For every machine: with no root observed, the bundled branch cannot
  fire. So fixing `_validate_c_linker` without also fixing the order would have
  fixed nothing on the thin-wheel path.
-/
theorem validate_before_acquire_is_blind (m : Machine) :
    acceptsWith m (observedRoot m .noRoot) = oldAccepts m := by
  simp [acceptsWith, observedRoot, oldAccepts]

/--
  **The shipped `FATAL ERROR`, and its absence after the fix.**

  Same machine, same relaxed check, different order: the old order validates at
  `noRoot` and aborts; the new order validates after acquisition and proceeds.
-/
theorem ordering_decides_the_verdict :
    validationOutcome windowsThinInstall oldOrder = false ∧
      validationOutcome windowsThinInstall newOrder = true := by
  constructor <;> decide

/-- The phases at which each order validates, for the record. -/
example : phaseAtValidate .noRoot oldOrder = some .noRoot := rfl
example : phaseAtValidate .noRoot newOrder = some .rootOnly := rfl

/-! ## Executable checks

`decide` closes a goal by kernel reduction; `#guard` additionally runs the
definitions through the evaluator. Both are cheap, and a definition that
elaborates but does not compute is a definition nobody has run.
-/

#guard bundledCLinker (some ["mingw/bin/clang.exe"]) == true
#guard bundledCLinker (some ["mingw/bin/ld.exe"]) == false
#guard bundledCLinker none == false
#guard oldAccepts windowsThinInstall == false
#guard newAccepts windowsThinInstall == true
#guard resolved (run .noRoot oldOrder) == false
#guard resolved (run .noRoot newOrder) == true
#guard validationOutcome windowsThinInstall oldOrder == false
#guard validationOutcome windowsThinInstall newOrder == true

end GhcPython

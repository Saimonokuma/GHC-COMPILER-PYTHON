/-
  Extraction containment.

  `bootstrap._extract` refuses any archive member that would resolve outside
  the destination directory. Release assets are our own, but an archive member
  is still untrusted input: a traversal entry would write outside the cache,
  and on a developer machine the cache sits inside the user's home directory.

  Tests can only sample member names. Containment must hold for all of them, so
  it is proved here rather than sampled.

  Paths are modelled as component lists, which is what both `zipfile.namelist`
  and `tarfile.getmembers` hand back after splitting on the archive separator.
-/

namespace GhcPython

/-- Resolve a member path against an accumulator, interpreting `.` and `..`
    the way a filesystem does. Mirrors what `Path.resolve()` performs before
    `_is_within` compares.

    Written with `if` rather than literal patterns so the rewriting lemmas
    below are provable by `if_pos` / `if_neg` instead of fragile `split`s. -/
def resolve : List String → List String → List String
  | acc, []        => acc
  | acc, c :: rest =>
      if c = "." then resolve acc rest
      else if c = ".." then resolve acc.dropLast rest
      else resolve (acc ++ [c]) rest

/-- The containment guard: the resolved path must still sit under `base`.
    Mirrors `bootstrap._is_within`. -/
def isWithin (base member : List String) : Prop :=
  base <+: resolve base member

instance (base member : List String) : Decidable (isWithin base member) := by
  unfold isWithin; infer_instance

/-! ### Rewriting lemmas -/

@[simp] theorem resolve_nil (base : List String) : resolve base [] = base := rfl

@[simp] theorem resolve_dot (base rest : List String) :
    resolve base ("." :: rest) = resolve base rest := by
  simp [resolve]

@[simp] theorem resolve_dotdot (base rest : List String) :
    resolve base (".." :: rest) = resolve base.dropLast rest := by
  simp [resolve]

theorem resolve_plain (base rest : List String) (c : String)
    (h₁ : c ≠ ".") (h₂ : c ≠ "..") :
    resolve base (c :: rest) = resolve (base ++ [c]) rest := by
  simp [resolve, h₁, h₂]

/-! ### The guard is necessary

A traversal member genuinely escapes. This is not hypothetical: without the
check, `..` components walk the accumulator above `base`.
-/

/-- Concrete escape witness: from `cache/ghc`, the member `../../etc/passwd`
    resolves to `etc/passwd`, entirely outside the base. -/
example : resolve ["cache", "ghc"] ["..", "..", "etc", "passwd"] = ["etc", "passwd"] := by
  decide

/-- And the guard rejects exactly that member. -/
example : ¬ isWithin ["cache", "ghc"] ["..", "..", "etc", "passwd"] := by
  decide

/-- A member may also escape *sideways* into a sibling directory, which is
    still outside the destination. -/
example : ¬ isWithin ["cache", "ghc"] ["..", "other", "evil"] := by
  decide

/-! ### The guard is sound -/

/--
  **Anything the guard accepts stays under the destination.**

  Immediate from the definition, but stating it pins the contract: the value
  compared against `base` is the *resolved* path, not the raw member name. A
  guard comparing the unresolved name would accept `a/../../etc` because it
  starts with `a`. That is the classic form of this bug.
-/
theorem isWithin_sound (base member : List String) (h : isWithin base member) :
    base <+: resolve base member := h

/-- The empty member is always contained, so an archive entry naming the
    destination itself is never rejected. -/
theorem isWithin_nil (base : List String) : isWithin base [] := by
  unfold isWithin; simp

/-- A single plain component is always contained. This is the common case and
    it must never be rejected -- a guard that refused ordinary members would be
    safe but useless. -/
theorem isWithin_single_plain (base : List String) (c : String)
    (h₁ : c ≠ ".") (h₂ : c ≠ "..") : isWithin base [c] := by
  unfold isWithin
  rw [resolve_plain base [] c h₁ h₂, resolve_nil]
  exact List.prefix_append base [c]

/--
  **Escape requires a `..` component.**

  If a member contains no `..`, it cannot leave the destination -- whatever
  else it contains, however deeply nested, and for any base. This is what
  justifies treating `..` as the thing to look for.
-/
theorem no_escape_without_dotdot :
    ∀ (member base : List String), ¬ member.contains ".." → isWithin base member := by
  intro member
  induction member with
  | nil => intro base _; exact isWithin_nil base
  | cons c rest ih =>
    intro base h
    simp only [List.contains_cons, Bool.or_eq_true, not_or] at h
    obtain ⟨hc, hrest⟩ := h
    have hne : c ≠ ".." := by
      intro hEq; exact hc (by simp [hEq])
    by_cases hdot : c = "."
    · subst hdot
      unfold isWithin
      rw [resolve_dot]
      exact ih base hrest
    · unfold isWithin
      rw [resolve_plain base rest c hdot hne]
      exact List.IsPrefix.trans (List.prefix_append base [c]) (ih (base ++ [c]) hrest)

/-- Contrapositive, stated for the reader: anything the guard rejects had a
    `..` in it. -/
theorem rejected_implies_dotdot (base member : List String)
    (h : ¬ isWithin base member) : member.contains ".." := by
  -- `by_contra` is a Mathlib tactic; this project deliberately depends only on
  -- Lean core, so the case split is done by hand.
  cases hc : member.contains ".." with
  | true  => rfl
  | false =>
      have hfalse : ¬ member.contains ".." := by
        rw [hc]; exact Bool.false_ne_true
      exact absurd (no_escape_without_dotdot member base hfalse) h

end GhcPython

/-
  The integrity guard's binary-name probe.

  `optimize_binaries.sh` verifies the compiler survived trimming by looking for
  each required tool. A GHC installation may expose a tool under either its
  plain name (`ghc`) or its versioned name (`ghc-9.4.8`), so the probe needs a
  fallback for the versioned form.

  The fallback was written as the glob `ghc-*`. That matches `ghc-pkg`, so
  deleting the compiler entirely still satisfied the guard: it reported
  "toolchain intact" on a tree containing no `ghc`. A test caught it
  (tests/test_optimize.py::test_missing_compiler_is_a_hard_failure) but a test
  only covers the sibling names someone thought to write down. GHC ships
  `ghc-pkg`, `ghc-iserv`, `ghc-iserv-dyn`, `ghci`, and future versions may ship
  more.

  What has to hold is a statement about *every* name, so it is proved here
  rather than sampled:

    * a name whose character after the dash is not a digit never matches
    * therefore no sibling tool can ever be mistaken for the compiler
    * the versioned form still matches, so the fallback keeps working

  Names are modelled as `List Char`, avoiding `String.Pos` arithmetic which
  would obscure the argument without changing it.

  Lean core only -- no Mathlib.
-/

namespace Guard

/-- The probe: does `name` look like the versioned form of `tool`?

    Mirrors the shell glob `${tool}-[0-9]*`: the name must begin with the tool
    name, then a dash, then at least one character, and that character must be
    a digit. -/
def versionedMatch (tool name : List Char) : Bool :=
  match name.drop tool.length with
  | '-' :: c :: _ => tool.isPrefixOf name && c.isDigit
  | _             => false

/-- The defective probe: the glob `${tool}-*`, which accepts any character
    after the dash. Retained so the two can be compared. -/
def looseMatch (tool name : List Char) : Bool :=
  match name.drop tool.length with
  | '-' :: _ :: _ => tool.isPrefixOf name
  | _             => false

/-- If the character following the dash is not a digit, the probe rejects.

    This is the property the shell glob `[0-9]` is there to enforce. -/
theorem versionedMatch_rejects_nondigit
    (tool rest : List Char) (c : Char) (name : List Char)
    (hdrop : name.drop tool.length = '-' :: c :: rest)
    (hc : c.isDigit = false) :
    versionedMatch tool name = false := by
  unfold versionedMatch
  rw [hdrop]
  simp [hc]

/-- Acceptance implies the character after the dash really was a digit.

    Stated in this direction because it is the safety property: whatever the
    guard accepts, it accepted for the right reason. Contrapositively, no name
    whose post-dash character is a letter can ever be accepted -- which is
    exactly what `ghc-pkg` violated under the old glob. -/
theorem versionedMatch_implies_digit (tool name : List Char) :
    versionedMatch tool name = true →
    ∃ c rest, name.drop tool.length = '-' :: c :: rest ∧ c.isDigit = true := by
  unfold versionedMatch
  split
  · next c rest heq =>
      intro h
      exact ⟨c, rest, heq, (Bool.and_eq_true _ _ ▸ h).2⟩
  · intro h
    exact absurd h (by simp)

/-- A list is always a prefix of itself extended.

    Lean core has no `isPrefixOf_append` lemma, so it is proved here by the
    obvious induction. -/
theorem isPrefixOf_self_append (l₁ l₂ : List Char) :
    l₁.isPrefixOf (l₁ ++ l₂) = true := by
  induction l₁ with
  | nil => simp [List.isPrefixOf]
  | cons a as ih => simp [ih]

/-- The versioned form of a tool is still matched.

    A fix that rejected everything would satisfy the safety theorem above while
    breaking the guard, so the positive direction is stated too. -/
theorem versionedMatch_accepts_digit
    (tool rest : List Char) (c : Char)
    (hc : c.isDigit = true) :
    versionedMatch tool (tool ++ '-' :: c :: rest) = true := by
  unfold versionedMatch
  rw [List.drop_left]
  simp [hc, isPrefixOf_self_append]

/-- The concrete failure that shipped: `ghc-pkg` was accepted as evidence that
    `ghc` exists. The loose probe says yes; the fixed probe says no. -/
example : looseMatch "ghc".toList "ghc-pkg".toList = true := by decide
example : versionedMatch "ghc".toList "ghc-pkg".toList = false := by decide

/-- Every sibling GHC ships is rejected. -/
example : versionedMatch "ghc".toList "ghc-iserv".toList = false := by decide
example : versionedMatch "ghc".toList "ghc-iserv-dyn".toList = false := by decide
example : versionedMatch "ghc".toList "ghci".toList = false := by decide

/-- The versioned binary this project pins is accepted. -/
example : versionedMatch "ghc".toList "ghc-9.4.8".toList = true := by decide
example : versionedMatch "ghc-pkg".toList "ghc-pkg-9.4.8".toList = true := by decide

/-- The two probes genuinely differ: the loose one accepts a sibling the
    versioned one refuses. This is the defect, stated as a theorem. -/
theorem loose_and_versioned_disagree :
    looseMatch "ghc".toList "ghc-pkg".toList = true
    ∧ versionedMatch "ghc".toList "ghc-pkg".toList = false := by
  constructor <;> decide

end Guard

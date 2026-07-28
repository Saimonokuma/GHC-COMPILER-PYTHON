/-
  Why a green pipeline shipped a payload that could not start.

  Measured, not hypothesised. Tag v9.4.9, run 30342043050, the first time the
  delivered-install gate ever ran on Linux:

      ghc-9.4.8: error while loading shared libraries: libtinfo.so.5:
      cannot open shared object file: No such file or directory

  The payload downloaded, its digest verified, and it extracted. Then the
  compiler would not start. Meanwhile every other job in the same run was
  green.

  The cause is an ORDERING, which is why it belongs here rather than in a test.
  `auditwheel repair` vendors GHC's shared libraries -- but it ran after the
  payload archive was built, and it repaired the WHEEL. So the offline wheel
  carried libtinfo.so.5 and the payload carried nothing. Every job validated
  the offline wheel. Nobody installing from PyPI receives the offline wheel.

  A test can only sample the orders someone thought to write down. What has to
  hold is a statement about EVERY order: a payload cannot be self-contained
  unless the tree was vendored before it was snapshotted. That is
  `no_vendor_no_selfContained` and `vendor_after_archive_is_too_late`.

  The theorem worth reading is `oldOrder_hides_the_defect`: under the old order
  the wheel is fine and the payload is broken, simultaneously. That conjunction
  is not a curiosity, it is the exact reason nine green checks meant nothing.
-/

-- Nested, because `Step`, `step`, `run`, `oldOrder` and `newOrder` already name
-- different things in Payload.lean and Linker.lean. Two models of two different
-- machines should not compete for one identifier.
namespace GhcPython.Vendoring

/-- The build steps that decide whether a payload can start on a user's
    machine. Mirrors the Linux job in `scripts/generate_workflow.py`. -/
inductive Step where
  /-- Copy the fragile shared libraries into `ghc-bindist/vendor-lib`.
      This is the step that did not exist. -/
  | vendorTree
  /-- Snapshot the tree into `payload/ghc-payload-*.tar.xz`. Whatever the tree
      contains at this instant is what a PyPI user will receive, forever. -/
  | archive
  /-- `python -m build --wheel`: the offline wheel, from the same tree. -/
  | buildWheel
  /-- `auditwheel repair`: vendors libraries INTO THE WHEEL. It cannot repair
      a payload that was already written, and it never claimed to. -/
  | auditwheelRepair
  deriving DecidableEq, Repr

/-- What exists so far.

    `payload`/`wheel` are `none` before the artifact is produced, and
    `some true` exactly when the artifact carries the libraries it needs. -/
structure State where
  treeVendored : Bool
  payload : Option Bool
  wheel : Option Bool
  deriving DecidableEq, Repr

/-- Nothing built, nothing vendored. -/
def init : State := { treeVendored := false, payload := none, wheel := none }

/-- One step. The load-bearing line is `archive`: it copies the tree's CURRENT
    state into the payload, and no later step can reach back and change it. -/
def step (s : State) : Step → State
  | .vendorTree       => { s with treeVendored := true }
  | .archive          => { s with payload := some s.treeVendored }
  | .buildWheel       => { s with wheel := some s.treeVendored }
  | .auditwheelRepair => { s with wheel := s.wheel.map (fun _ => true) }

/-- Run a whole job. -/
def run (steps : List Step) (s : State) : State :=
  steps.foldl step s

/-- The payload starts on a machine that has none of these libraries. -/
def payloadOk (steps : List Step) : Bool :=
  (run steps init).payload = some true

/-- The offline wheel starts. This is what every job in the pipeline measured. -/
def wheelOk (steps : List Step) : Bool :=
  (run steps init).wheel = some true

/-- The order that shipped: archive, build the wheel, then repair the wheel. -/
def oldOrder : List Step := [.archive, .buildWheel, .auditwheelRepair]

/-- The order now generated: vendor into the tree first, so the snapshot
    contains the libraries. -/
def newOrder : List Step := [.vendorTree, .archive, .buildWheel, .auditwheelRepair]

/-! ### The defect, and why it was invisible -/

/-- THE CROWN THEOREM. Under the shipped order the wheel is fine and the
    payload is broken, at the same time.

    This is the whole story of the outage in one proposition. The pipeline was
    not lying when it went green: the artifact it validated really did work.
    It validated the artifact nobody receives. -/
theorem oldOrder_hides_the_defect : wheelOk oldOrder = true ∧ payloadOk oldOrder = false := by
  decide

/-- The new order fixes the payload without disturbing the wheel. A fix that
    traded one artifact for the other would not be a fix. -/
theorem newOrder_ships_both : wheelOk newOrder = true ∧ payloadOk newOrder = true := by
  decide

/-- `auditwheelRepair` is powerless over the payload, under every possible
    prefix. It repairs wheels; the payload was already written to disk.

    Stated over an arbitrary `s` on purpose: no reachable state, and no state
    at all, lets this step touch a payload. -/
theorem auditwheel_cannot_repair_a_payload (s : State) :
    (step s .auditwheelRepair).payload = s.payload := rfl

/-! ### The general statements -- these are why this is a proof and not a test -/

/-- Vendoring is never undone. Needed below, and worth stating: if any step
    could unset it, ordering alone would not be enough. -/
theorem vendored_is_monotone (s : State) (b : Step) :
    s.treeVendored = true → (step s b).treeVendored = true := by
  cases b <;> simp [step]

/-- Only `vendorTree` sets it. -/
theorem only_vendor_sets (s : State) (b : Step) :
    s.treeVendored = false → b ≠ .vendorTree → (step s b).treeVendored = false := by
  cases b <;> simp [step]

/-- Without the vendor step the tree is never vendored, however long the job
    and whatever else it does. -/
theorem no_vendor_tree_stays_bare :
    ∀ (steps : List Step) (s : State),
      s.treeVendored = false → Step.vendorTree ∉ steps → (run steps s).treeVendored = false := by
  intro steps
  induction steps with
  | nil => intro s h _; exact h
  | cons b rest ih =>
    intro s h hnin
    have hb : b ≠ Step.vendorTree := by
      intro hb; exact hnin (by simp [hb])
    have hrest : Step.vendorTree ∉ rest := by
      intro hmem; exact hnin (by simp [hmem])
    exact ih (step s b) (only_vendor_sets s b h hb) hrest

/-- SAFETY. No build that omits the vendor step can produce a payload that
    starts. There is no clever ordering of the other steps that rescues it --
    which is precisely what the old pipeline spent nine green checks implying. -/
theorem no_vendor_no_selfContained (steps : List Step) (h : Step.vendorTree ∉ steps) :
    payloadOk steps = false := by
  have key : ∀ (l : List Step) (s : State),
      s.treeVendored = false → s.payload ≠ some true → Step.vendorTree ∉ l →
      (run l s).payload ≠ some true := by
    intro l
    induction l with
    | nil => intro s _ hp _; exact hp
    | cons b rest ih =>
      intro s hv hp hnin
      have hb : b ≠ Step.vendorTree := by
        intro hb; exact hnin (by simp [hb])
      have hrest : Step.vendorTree ∉ rest := by
        intro hmem; exact hnin (by simp [hmem])
      refine ih (step s b) (only_vendor_sets s b hv hb) ?_ hrest
      cases b with
      | vendorTree => exact absurd rfl hb
      | archive => simp [step, hv]
      | buildWheel => simpa [step] using hp
      | auditwheelRepair => simpa [step] using hp
  have := key steps init (by rfl) (by simp [init]) h
  simp [payloadOk, this]

/-- Vendoring after the snapshot is too late. This is not a corner case: it is
    literally the order that shipped, with the new step appended at the end
    instead of inserted before `archive`. -/
theorem vendor_after_archive_is_too_late :
    payloadOk [.archive, .vendorTree] = false := by decide

/-- And immediately before it, it is enough. -/
theorem vendor_before_archive_suffices :
    payloadOk [.vendorTree, .archive] = true := by decide

/-- Repeating the whole old pipeline never helps. Rebuilding, re-running,
    re-releasing -- none of it can produce a working payload, because the
    missing step is missing. A useful thing to know before retrying a red
    release for the third time. -/
theorem retrying_the_old_order_never_helps (n : Nat) :
    payloadOk (List.replicate n Step.archive) = false := by
  apply no_vendor_no_selfContained
  intro h
  have := List.eq_of_mem_replicate h
  exact Step.noConfusion this

/-! ### Concrete instances -- the definitions must also EXECUTE as claimed -/

#guard payloadOk oldOrder = false
#guard wheelOk oldOrder = true
#guard payloadOk newOrder = true
#guard wheelOk newOrder = true
#guard payloadOk [] = false
#guard payloadOk [.vendorTree] = false          -- vendored but never archived
#guard payloadOk [.archive, .vendorTree] = false
#guard payloadOk [.vendorTree, .archive] = true
#guard payloadOk [.vendorTree, .archive, .auditwheelRepair] = true
#guard wheelOk [.buildWheel] = false            -- built from a bare tree
#guard wheelOk [.buildWheel, .auditwheelRepair] = true
#guard wheelOk [.auditwheelRepair] = false      -- nothing to repair

end GhcPython.Vendoring

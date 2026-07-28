/-
  Corpus generator for the spec-to-code cross-check.

  A proof about a model proves nothing about a program unless something binds
  the two. This file emits the modelled roots together with the model's verdict
  for each; `crosscheck.py` materialises those roots on disk, runs the *real*
  `wrapper._bundled_c_linker` over them, and diffs. The corpus lives here only,
  so the two sides cannot drift apart silently.

  Run from `lean/`:

      lake env lean crosscheck/Corpus.lean > verdicts.txt
      uv run --no-project --python 3.12 crosscheck/crosscheck.py .. verdicts.txt

  Exit 0 means the model and the shipped code agree. Verified red against four
  deliberate mutations of `wrapper.py`: catalogue entry removed, `_execute_tool`
  ordering reverted, `_validate_c_linker` losing its `root` parameter, and
  `_bundled_c_linker` never finding anything.
-/

import Proofs.Linker
open GhcPython

/-- Corpus of toolchain roots, as lists of file paths relative to the root.
    Single source of truth: the Python side consumes this output. -/
def corpus : List (List String) :=
  [ []
  , ["bin/ghc.exe"]
  , ["bin/ghc.exe", "mingw/bin/clang.exe", "mingw/bin/ld.exe"]
  , ["mingw/bin/clang.exe"]
  , ["mingw/bin/gcc.exe"]
  , ["mingw/bin/clang"]
  , ["mingw/bin/gcc"]
  , ["mingw/bin/ld.exe"]
  , ["mingw/bin/ld.exe", "lib/ghc-9.4.8/bin/ghc.exe"]
  , ["mingw/bin/CLANG.EXE"]
  , ["bin/clang.exe"]
  , ["mingw/clang.exe"]
  , ["mingw/bin/clang.exe.bak"]
  , ["usr/bin/gcc", "mingw/bin/gcc"]
  ]

#eval IO.println (String.intercalate "\n" (corpus.map (fun fs =>
  String.intercalate "," fs ++ "|" ++ toString (bundledCLinker (some fs)))))

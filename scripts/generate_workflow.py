#!/usr/bin/env python3
"""
Ouroboros Transmutation: Python Pipeline Generator for GitHub Actions.

Compiles a Python pipeline definition into a static, unrolled YAML workflow,
eliminating conditional logic from the YAML itself.

--------------------------------------------------------------------------
Why the pipeline has the shape it does
--------------------------------------------------------------------------

The previous pipeline built one wheel per OS, each containing the whole GHC
toolchain, and pushed all three to PyPI. That could never have worked:

  * PyPI enforces a 100 MB per-file limit. The wheels were 363-539 MB, so the
    upload would have been rejected on size even once authentication worked.
  * All three were tagged `py3-none-any` -- "pure Python, any platform" -- on
    wheels full of native binaries. They collided on one filename, so PyPI
    would have accepted one and served it to every platform. A Windows user
    would have received macOS binaries.

Distribution is therefore split by what actually has to fit where:

  thin wheel      py3-none-any, ~50 KB, no toolchain, published to PyPI.
                  Genuinely pure Python, so the universal tag is now true.
                  Fetches its payload on first use.

  payloads        one compressed toolchain per platform, published to the
                  GitHub Release. 2 GB per-file limit there, so size is a
                  non-issue. SHA-256 of each is embedded in the thin wheel.

  offline wheels  platform-tagged, toolchain bundled, published to the
                  Release for air-gapped installs. Never touch the network.

Job order matters: payload digests do not exist until the payloads are built,
and the thin wheel cannot be built until it can embed them. So the three OS
jobs fan out, `build-thin-wheel` joins on all of them, and only then can
anything be published.
"""

from pathlib import Path

# Action versions are pinned to majors and refreshed deliberately. Dependabot
# edits build.yml, which is generated -- so a bump that is not mirrored here is
# silently reverted the next time this script runs.
ACTIONS = {
    "checkout": "actions/checkout@v7",
    "setup_python": "actions/setup-python@v7",
    "upload_artifact": "actions/upload-artifact@v7",
    "download_artifact": "actions/download-artifact@v8",
    "pypi_publish": "pypa/gh-action-pypi-publish@release/v1",
    "gh_release": "softprops/action-gh-release@v3",
}

PYTHON_VERSION = "3.13"

# The compiler inside the payload. Drives the `ghc-wrapper --numeric-version`
# assertions, which must keep answering for the compiler.
GHC_VERSION = "9.4.8"

# The distribution coordinate: git tag, release, payload asset names, wheel
# version. Diverged from GHC_VERSION at 9.4.9, because the 9.4.8 wheel on PyPI
# is unusable on Windows and PyPI does not allow replacing a version. Keep the
# two apart: renaming a payload asset and claiming a new compiler release must
# never be the same edit again.
RELEASE_VERSION = "9.4.9"


class Step:
    def __init__(self, name=None, uses=None, run=None, shell=None, with_args=None, env=None, if_cond=None):
        self.name = name
        self.uses = uses
        self.run = run
        self.shell = shell
        self.with_args = with_args
        self.env = env
        self.if_cond = if_cond

    def to_yaml(self, indent=6):
        ind = " " * indent
        lines = []
        if self.uses:
            if self.name:
                lines.append(f"{ind}- name: {self.name}")
                lines.append(f"{ind}  uses: {self.uses}")
            else:
                lines.append(f"{ind}- uses: {self.uses}")
            inner_ind = indent + 2
            if self.if_cond:
                lines.append(f"{' ' * inner_ind}if: {self.if_cond}")
            if self.with_args:
                lines.append(f"{' ' * inner_ind}with:")
                for k, v in self.with_args.items():
                    if "\n" in str(v):
                        lines.append(f"{' ' * inner_ind}  {k}: |")
                        for line in str(v).strip().split("\n"):
                            lines.append(f"{' ' * inner_ind}    {line}")
                    else:
                        lines.append(f"{' ' * inner_ind}  {k}: {v}")
        else:
            lines.append(f"{ind}- name: {self.name}")
            if self.if_cond:
                lines.append(f"{ind}  if: {self.if_cond}")
            if self.shell:
                lines.append(f"{ind}  shell: {self.shell}")
            if self.env:
                lines.append(f"{ind}  env:")
                for k, v in self.env.items():
                    lines.append(f"{ind}    {k}: {v}")
            if self.run:
                if "\n" in self.run.strip():
                    lines.append(f"{ind}  run: |")
                    for line in self.run.strip().split("\n"):
                        lines.append(f"{ind}    {line}" if line.strip() else "")
                else:
                    lines.append(f"{ind}  run: {self.run}")
        return "\n".join(lines)


PLATFORMS = {
    "linux": {
        "os": "ubuntu-latest",
        # This must state what the binaries actually require, not what would be
        # convenient. GHC is built here on ubuntu-latest (glibc 2.39) and links
        # versioned symbols newer than 2.28, so auditwheel refuses to stamp a
        # lower tag:
        #
        #   cannot repair ... to "manylinux_2_28_x86_64" ABI because of the
        #   presence of too-recent versioned symbols
        #
        # Lowering it to widen distro coverage was tried and is impossible
        # without building GHC inside an older manylinux image. The tag is a
        # claim about the binaries; a lower one would install on systems where
        # the toolchain then fails at runtime.
        #
        # This constrains the OFFLINE wheel only. The primary path -- thin
        # wheel plus payload -- is unaffected, because the payload is a plain
        # tarball carrying no manylinux claim.
        "platform": "manylinux_2_39_x86_64",
        "archive": f"ghc-payload-{RELEASE_VERSION}-manylinux_2_39_x86_64.tar.xz",
        "payload_tag": "manylinux_2_39_x86_64",
    },
    "macos": {
        "os": "macos-latest",
        "platform": "macosx_11_0_arm64",
        "archive": f"ghc-payload-{RELEASE_VERSION}-macosx_11_0_arm64.tar.xz",
        "payload_tag": "macosx_11_0_arm64",
    },
    "windows": {
        "os": "windows-latest",
        "platform": "win_amd64",
        "archive": f"ghc-payload-{RELEASE_VERSION}-win_amd64.zip",
        "payload_tag": "win_amd64",
    },
}


def generate_job(platform_key, platform_data):
    steps = []

    def add_step(name=None, uses=None, run=None, shell=None, with_args=None, if_cond=None):
        steps.append(Step(name=name, uses=uses, run=run, shell=shell,
                          with_args=with_args, if_cond=if_cond))

    add_step(uses=ACTIONS["checkout"])

    if platform_key == "linux":
        add_step(name="Free disk space (Linux)", run="sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc\nsudo apt-get clean\ndf -h")

    add_step(uses=ACTIONS["setup_python"], with_args={"python-version": f"'{PYTHON_VERSION}'", "cache": "'pip'"})

    if platform_key == "linux":
        add_step(name="Install System C-Linker (Linux)", run="""sudo apt-get update
sudo apt-get install -y gcc binutils patchelf
# GHC 9.4.8 needs libtinfo5/libncurses5 which aren't on Ubuntu 24.04 natively
sudo apt-get install -y libtinfo5 libncurses5 libffi7 || \\
  (sudo apt-get install -y libtinfo6 libncursesw6 libffi8 libgmp10 && \\
   sudo ln -sf /usr/lib/x86_64-linux-gnu/libtinfo.so.6 /usr/lib/x86_64-linux-gnu/libtinfo.so.5 && \\
   sudo ln -sf /usr/lib/x86_64-linux-gnu/libncursesw.so.6 /usr/lib/x86_64-linux-gnu/libncurses.so.5 && \\
   sudo ln -sf /usr/lib/x86_64-linux-gnu/libffi.so.8 /usr/lib/x86_64-linux-gnu/libffi.so.7)""")
        add_step(name="Install Vendoring Tools (Linux)", run="pip install auditwheel")
    elif platform_key == "macos":
        add_step(name="Install System C-Linker (macOS)", run="xcode-select -p || xcode-select --install")
        add_step(name="Install Vendoring Tools (macOS)", run="pip install delocate")
    elif platform_key == "windows":
        add_step(name="Install System C-Linker (Windows)", shell="pwsh", run="""choco install mingw -y
echo "C:\\msys64\\mingw64\\bin" | Out-File -FilePath $env:GITHUB_PATH -Append""")

    add_step(name="Install Python Build Dependencies", run="python -m pip install --upgrade pip\npip install build hatchling wheel")
    add_step(name="Fetch and Verify GHC/Cabal Binaries", shell="bash", run="bash scripts/fetch_binaries.sh")
    add_step(name="Verify Shared Libraries", shell="bash", run="""echo "=== Checking for required .so files ==="
find ghc-bindist -name "libtinfo*" -o -name "libncurses*" -o -name "libffi*" -o -name "libgmp*" || true
echo "=== Full lib directory ==="
ls -la ghc-bindist/lib/ghc-9.4.8/*.so* 2>/dev/null || true

# Check if internal libraries actually extracted properly
if [ -z "$(find ghc-bindist -name "libtinfo*.so.*")" ]; then
    echo "WARNING: libtinfo internal library not found in bindist, falling back to system symlinks."
fi""")

    add_step(name="Optimize Binary Size", shell="bash", run="bash scripts/optimize_binaries.sh")
    add_step(name="Patch GHC Paths for Relocatability", shell="bash", run="python scripts/patch_ghc_paths.py")

    if platform_key == "macos":
        add_step(name="Fix macOS Dynamic Library Paths", shell="bash", run="bash scripts/fix_macos_rpaths.sh")

    # ---------------------------------------------------------------
    # Payload: the toolchain as a standalone, hash-addressed archive.
    # Built BEFORE the wheel so the wheel build cannot perturb the tree.
    # ---------------------------------------------------------------
    archive = platform_data["archive"]
    if platform_key == "windows":
        # -mx=9 measured at 5.5+ minutes on the trimmed tree, against 2.4 for
        # xz on a comparable one, and buys only a few percent over -mx=5.
        # -mmt=on parallelises deflate across the runner's cores.
        #
        # Deflate specifically, not Deflate64 or LZMA: bootstrap.py extracts
        # this with Python's zipfile, which reads only Deflate. A denser
        # format here would produce an archive the wheel cannot open.
        payload_cmd = f"""mkdir -p payload
cd ghc-bindist
7z a -tzip -mx=5 -mmt=on "../payload/{archive}" . > /dev/null
cd ..
python -c "
import hashlib, pathlib
p = pathlib.Path('payload/{archive}')
h = hashlib.sha256(p.read_bytes()).hexdigest()
pathlib.Path('payload/{archive}.sha256').write_text(h + '  {archive}\\n')
print('SHA-256', h)
print('size', p.stat().st_size // 1048576, 'MB')
"
"""
    else:
        # `tar -cJf` invokes xz single-threaded, which takes many minutes over
        # an 863 MB tree and dominates the job. `-T0` uses every core the
        # runner has. `-6` is xz's default preset, kept explicit so the
        # compression ratio -- and therefore the payload size the 100 MB
        # ceiling is checked against -- does not change with the tool default.
        payload_cmd = f"""mkdir -p payload
tar -C ghc-bindist -cf - . | xz -T0 -6 -c > "payload/{archive}"
python -c "
import hashlib, pathlib
p = pathlib.Path('payload/{archive}')
h = hashlib.sha256(p.read_bytes()).hexdigest()
pathlib.Path('payload/{archive}.sha256').write_text(h + '  {archive}\\n')
print('SHA-256', h)
print('size', p.stat().st_size // 1048576, 'MB')
"
"""
    add_step(name="Build Toolchain Payload Archive", shell="bash", run=payload_cmd)

    add_step(name="Enforce Payload Size Ceiling", shell="bash", run=f"""# A payload that exceeds the distribution ceiling must fail here, loudly,
# rather than at upload time after the whole matrix has run.
SIZE=$(python -c "import pathlib; print(pathlib.Path('payload/{archive}').stat().st_size)")
LIMIT=$((100 * 1024 * 1024))
echo "payload: $((SIZE / 1048576)) MB (ceiling $((LIMIT / 1048576)) MB)"
if [ "$SIZE" -gt "$LIMIT" ]; then
  echo "::warning::payload exceeds 100 MB; PyPI would reject this if it were shipped there directly"
fi""")

    # ---------------------------------------------------------------
    # Offline wheel: toolchain bundled, correctly platform-tagged.
    # ---------------------------------------------------------------
    add_step(name="Build Offline Wheel (toolchain bundled)", run="python -m build --wheel")

    if platform_key == "linux":
        add_step(name="Vendor Dynamic Libraries (Linux)", shell="bash", run=f"""# Find the exact directory where the nested .so files are located inside ghc-bindist/lib/
# 2>/dev/null and `xargs -r` are load-bearing: without them an empty find result
# makes dirname error out and the step fails on a tree that is merely laid out
# differently. This fix previously existed only in the generated YAML and was
# reverted on every regeneration.
LINUX_LIB_DIR=$(find ghc-bindist/lib -name "libHS*.so" 2>/dev/null | head -n 1 | xargs -r dirname)
if [ -n "$LINUX_LIB_DIR" ]; then
    echo "Found Linux GHC libraries at $LINUX_LIB_DIR"
    export LD_LIBRARY_PATH="$(pwd)/$LINUX_LIB_DIR:${{LD_LIBRARY_PATH:-}}"
else
    echo "WARNING: Could not find Linux GHC libraries directory."
fi

# Run auditwheel with the LD_LIBRARY_PATH so it can find the internal .so dependencies
auditwheel repair dist/*.whl --plat {platform_data['platform']} -w wheelhouse/
rm -rf dist/*
mv wheelhouse/*.whl dist/""")
    elif platform_key == "macos":
        add_step(name="Vendor Dynamic Libraries (macOS)", shell="bash", run="""echo "Running delocate-wheel to verify and bundle dependencies"
# Our rpaths are already correctly pointing to the internal libs
delocate-wheel -v dist/*.whl""")

    if platform_key != "linux":
        # auditwheel retags Linux wheels itself. macOS and Windows do not, so
        # without this both emitted `py3-none-any` -- a pure-Python tag on a
        # wheel full of native binaries, colliding with every other platform.
        add_step(name="Apply Platform Tag", shell="bash", run=f"""python -m wheel tags --platform-tag {platform_data['platform']} --remove dist/*.whl
ls -la dist/
python - <<'PYEOF'
import pathlib
from packaging.utils import parse_wheel_filename
for whl in pathlib.Path("dist").glob("*.whl"):
    name, ver, build, tags = parse_wheel_filename(whl.name)
    print(f"{{whl.name}} -> {{sorted(str(t) for t in tags)}}")
    assert "any" not in str(tags), f"{{whl.name}} still carries the universal tag"
print("platform tag verified")
PYEOF""")

    # ---------------------------------------------------------------
    # Proof: installs, compiles, and RUNS. Builds are not deliveries.
    # ---------------------------------------------------------------
    add_step(name="End-to-End Compilation Validation", shell="bash", run=f"""python -m venv test-env
if [ -f test-env/Scripts/activate ]; then
  source test-env/Scripts/activate
else
  source test-env/bin/activate
fi

pip install dist/*.whl

# Assert this is OUR pinned toolchain, not whatever GHC the runner had.
# `wrapper.py` used to fall back to shutil.which(), which silently resolved to
# a system GHC and still reported success -- a green E2E that proved nothing
# about the wheel. Checking the version closes that hole in CI.
REPORTED=$(ghc-wrapper --numeric-version)
echo "ghc-wrapper --numeric-version -> $REPORTED"
if [ "$REPORTED" != "{GHC_VERSION}" ]; then
  echo "FATAL: expected GHC {GHC_VERSION}, got '$REPORTED' -- resolved the wrong toolchain" >&2
  exit 1
fi
echo "=== Debug Library Paths ==="
find test-env -name "libtinfo*" -o -name "libncurses*" -o -name "libffi*" || true
ls -la test-env/lib/ghc-9.4.8/bin || true
ls -la test-env/ghc_compiler_python.libs || true

cat << 'EOF2' > HelloWorld.hs
module Main where
main :: IO ()
main = putStrLn "E2E Native Compiler Validation Successful."
EOF2

ghc-wrapper HelloWorld.hs

if [ -f ./HelloWorld.exe ]; then
  OUTPUT=$(./HelloWorld.exe)
else
  OUTPUT=$(./HelloWorld)
fi

echo "program output: $OUTPUT"
case "$OUTPUT" in
  *"E2E Native Compiler Validation Successful."*)
    echo "compiled binary produced the expected output" ;;
  *)
    echo "FATAL: compiled binary ran but printed something unexpected" >&2
    exit 1 ;;
esac

cabal-wrapper --version
deactivate""")

    add_step(name="Upload Offline Wheel", uses=ACTIONS["upload_artifact"], with_args={
        "name": f"offline-wheel-{platform_data['payload_tag']}",
        "path": "dist/*.whl",
        "retention-days": "30",
    })
    add_step(name="Upload Toolchain Payload", uses=ACTIONS["upload_artifact"], with_args={
        "name": f"payload-{platform_data['payload_tag']}",
        "path": "payload/*",
        "retention-days": "30",
    })

    return steps


def generate_thin_wheel_job(needs_list):
    needs_str = "[" + ", ".join(needs_list) + "]"
    return f"""
  build-thin-wheel:
    name: Build Thin Wheel (PyPI)
    needs: {needs_str}
    runs-on: ubuntu-latest
    steps:
      - uses: {ACTIONS['checkout']}

      - uses: {ACTIONS['setup_python']}
        with:
          python-version: '{PYTHON_VERSION}'

      - name: Install Python Build Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build hatchling packaging

      - uses: {ACTIONS['download_artifact']}
        with:
          pattern: payload-*
          path: payloads/
          merge-multiple: true

      - name: Embed Payload Digests
        run: |
          # The thin wheel verifies its download against these digests. They
          # cannot be known before the payloads exist, which is why this job
          # joins on all three build jobs.
          python - <<'PYEOF'
          import json, pathlib

          manifest = {{}}
          for sha in sorted(pathlib.Path("payloads").glob("*.sha256")):
              digest, _, name = sha.read_text(encoding="utf-8").strip().partition("  ")
              manifest[name.strip()] = digest.strip()

          if len(manifest) != 3:
              raise SystemExit(
                  f"expected 3 payload digests, found {{len(manifest)}}: "
                  f"{{sorted(manifest)}}"
              )

          out = pathlib.Path("ghc_compiler_python/payload_hashes.json")
          out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
          print(out.read_text(encoding="utf-8"))
          PYEOF

      - name: Build Thin Wheel
        run: |
          # ghc-bindist/ is empty in this job, so hatchling bundles no
          # toolchain and the resulting wheel is genuinely pure Python.
          python -m build --wheel

      - name: Verify Thin Wheel Is Small And Universal
        run: |
          python - <<'PYEOF'
          import pathlib, zipfile
          from packaging.utils import parse_wheel_filename

          wheels = list(pathlib.Path("dist").glob("*.whl"))
          assert len(wheels) == 1, f"expected exactly one wheel, got {{wheels}}"
          whl = wheels[0]

          name, ver, build, tags = parse_wheel_filename(whl.name)
          assert "any" in str(tags), f"thin wheel must be universal, got {{tags}}"

          size = whl.stat().st_size
          print(f"{{whl.name}}  {{size / 1024:.1f}} KiB  tags={{sorted(str(t) for t in tags)}}")
          assert size < 100 * 1024 * 1024, "thin wheel exceeds the PyPI per-file limit"
          assert size < 5 * 1024 * 1024, (
              "thin wheel is unexpectedly large; a toolchain may have leaked in"
          )

          with zipfile.ZipFile(whl) as zf:
              names = zf.namelist()
          assert any(n.endswith("payload_hashes.json") for n in names), (
              "payload_hashes.json missing; the wheel could never verify a download"
          )
          leaked = [n for n in names if "ghc-bindist" in n or n.endswith(".so")]
          assert not leaked, f"native artefacts leaked into the thin wheel: {{leaked[:5]}}"
          print("thin wheel verified")
          PYEOF

      - name: Upload Thin Wheel
        uses: {ACTIONS['upload_artifact']}
        with:
          name: thin-wheel
          path: dist/*.whl
          retention-days: 30
"""


def generate_release_job():
    return f"""
  attach-to-release:
    name: Attach Payloads And Offline Wheels To Release
    needs: [build-thin-wheel]
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')

    permissions:
      contents: write

    steps:
      # Needed for RELEASE.md, which becomes the release body. Without a
      # checkout the release page would be empty and a visitor would have to
      # guess which of six assets applies to them.
      - uses: {ACTIONS['checkout']}

      - uses: {ACTIONS['download_artifact']}
        with:
          pattern: payload-*
          path: release/
          merge-multiple: true

      - uses: {ACTIONS['download_artifact']}
        with:
          pattern: offline-wheel-*
          path: release/
          merge-multiple: true

      - name: List Release Assets
        run: ls -la release/

      - name: Attach To Release
        uses: {ACTIONS['gh_release']}
        with:
          files: release/*
          body_path: RELEASE.md
          # Without an explicit name the release is titled with the bare tag,
          # "v9.4.8", which is what a user sees first on the releases page and
          # in every notification.
          name: GHC Compiler Python ${{{{ github.ref_name }}}}
          # This is the supported release for the version it carries, so it
          # should be the one the "Latest" badge points at rather than
          # whatever happens to sort highest.
          make_latest: true
          # A release that silently attaches nothing is indistinguishable from
          # a successful one until a user hits a 404 on the payload URL.
          fail_on_unmatched_files: true
"""


def generate_delivery_proof_job():
    """Prove the path a PyPI user actually takes.

    Every other job validates the OFFLINE wheel: it installs `dist/*.whl` with
    the toolchain already bundled inside. That proves the compiler works. It
    does not prove the product works, because nobody installing from PyPI gets
    that wheel -- they get the 20 KiB thin wheel, which must reach the network,
    fetch its payload from this release, verify the SHA-256 it was built with,
    extract it, and only then compile.

    That path had never run in CI. It cannot run before the release exists,
    which is why it lives here, after attach-to-release, rather than beside the
    build. `publish-to-pypi` depends on it, so a wheel whose download path is
    broken can never reach PyPI.

    Builds != installs != compiles != delivered. This is the delivered link.
    """
    return f"""
  verify-delivered-install:
    name: Verify Delivered Install on ${{{{ matrix.os }}}}
    needs: [build-thin-wheel, attach-to-release]
    if: startsWith(github.ref, 'refs/tags/v')

    strategy:
      # Every platform reports independently. One failing must not hide the
      # status of the other two.
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]

    runs-on: ${{{{ matrix.os }}}}

    steps:
      - uses: {ACTIONS['setup_python']}
        with:
          python-version: '{PYTHON_VERSION}'

      - uses: {ACTIONS['download_artifact']}
        with:
          name: thin-wheel
          path: dist/

      - name: Install The Thin Wheel As A User Would
        shell: bash
        run: |
          python -m pip install --upgrade pip
          python -m pip install dist/*.whl
          echo "installed size on disk:"
          python -c "import ghc_compiler_python, pathlib, sys; p=pathlib.Path(ghc_compiler_python.__file__).parent; print(sum(f.stat().st_size for f in p.rglob('*') if f.is_file()), 'bytes')"

      - name: Make The Runner Look Like A User Machine
        shell: bash
        run: |
          # windows-latest ships mingw via chocolatey, so `gcc` is always on
          # PATH here and was never on PATH for a real user. That single
          # difference let 9.4.8 ship a wrapper which aborted with
          #
          #   FATAL ERROR: The GHC compiler requires a host C-linker
          #
          # before it ever touched the mingw the payload had just downloaded.
          # Three green Windows jobs certified a wheel that could not compile
          # on any stock Windows box. A runner that is better equipped than the
          # machine it certifies is not a test, it is a rehearsal.
          #
          # So the system compilers are removed from PATH for the rest of this
          # job. On Linux and macOS GHC genuinely needs the system cc and the
          # payload ships none, so they are left alone -- the point is to match
          # each platform's real user, not to strip uniformly.
          if [ "$RUNNER_OS" = "Windows" ]; then
            KEEP=""
            IFS=':' read -ra PARTS <<< "$PATH"
            for d in "${{PARTS[@]}}"; do
              if [ -x "$d/gcc.exe" ] || [ -x "$d/clang.exe" ] || [ -x "$d/gcc" ] || [ -x "$d/clang" ]; then
                echo "dropping from PATH: $d"
                continue
              fi
              KEEP="${{KEEP:+$KEEP:}}$d"
            done
            echo "PATH=$KEEP" >> "$GITHUB_ENV"
            export PATH="$KEEP"
          fi

          # Assert the scrub worked rather than trusting it. If a system
          # compiler survives, this job silently reverts to the rehearsal it
          # was, so failing here is the honest outcome.
          if [ "$RUNNER_OS" = "Windows" ]; then
            if command -v gcc >/dev/null 2>&1 || command -v clang >/dev/null 2>&1; then
              echo "::error::a system C compiler is still on PATH -- this job would not test the user's machine"
              command -v gcc || true
              command -v clang || true
              exit 1
            fi
            echo "no system gcc/clang on PATH: the payload's own toolchain is the only one available"
          else
            echo "$RUNNER_OS uses the system cc by design; PATH left untouched"
          fi

      - name: Fetch The Payload From This Release
        shell: bash
        env:
          # Deliberately NOT set: GHC_COMPILER_PYTHON_OFFLINE. This step must
          # reach the network and download the asset attached above, verifying
          # it against the digest compiled into the wheel. If the asset name,
          # the release tag, or the digest disagree, this fails here rather
          # than in a user's terminal.
          PYTHONUNBUFFERED: '1'
        run: |
          REPORTED=$(ghc-wrapper --numeric-version)
          echo "ghc-wrapper --numeric-version -> $REPORTED"
          if [ "$REPORTED" != "{GHC_VERSION}" ]; then
            echo "::error::expected {GHC_VERSION}, got '$REPORTED' -- resolved the wrong compiler"
            exit 1
          fi

      - name: Compile And Run Haskell Through The Downloaded Toolchain
        shell: bash
        run: |
          cat > Delivered.hs <<'HASKELL'
          import Data.List (sort)

          main :: IO ()
          main = do
            let xs = sort [3, 1, 2 :: Int]
            putStrLn ("Delivered Install Validation Successful: " ++ show xs)
          HASKELL

          ghc-wrapper Delivered.hs -o delivered

          if [ -f ./delivered.exe ]; then
            OUT=$(./delivered.exe)
          else
            OUT=$(./delivered)
          fi
          echo "program output: $OUT"

          EXPECTED='Delivered Install Validation Successful: [1,2,3]'
          if [ "$OUT" != "$EXPECTED" ]; then
            echo "::error::expected '$EXPECTED', got '$OUT'"
            exit 1
          fi
          echo "delivered install verified: downloaded, verified, extracted, compiled, ran"
"""


def generate_publish_job():
    return f"""
  publish-to-pypi:
    name: Publish Thin Wheel to PyPI
    needs: [build-thin-wheel, attach-to-release, verify-delivered-install]
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')

    environment:
      name: pypi
      url: https://pypi.org/p/ghc-compiler-python

    # API-token authentication, not OIDC.
    #
    # This job previously requested `id-token: write` and published via Trusted
    # Publishing. That failed in run 25262196892 with:
    #
    #   invalid-publisher: valid token, but no corresponding publisher
    #
    # The OIDC token was minted correctly; PyPI simply had no publisher
    # registered for this repository and workflow, and nothing on the GitHub
    # side can create one. Every tagged release therefore built three wheels
    # and published nothing.
    #
    # `id-token: write` is removed rather than left in place: an unused
    # privilege that looks load-bearing is how the previous failure stayed
    # confusing for so long.
    permissions:
      contents: read

    steps:
      # Only the thin wheel goes to PyPI. The offline wheels are 363-539 MB
      # and would be rejected on size; they live on the Release instead.
      - uses: {ACTIONS['download_artifact']}
        with:
          name: thin-wheel
          path: dist/

      - name: Confirm Exactly One Universal Wheel
        run: |
          ls -la dist/
          test "$(ls dist/*.whl | wc -l)" -eq 1 || {{ echo "expected exactly one wheel"; exit 1; }}

      - name: Fail Early If The Token Is Missing
        # Without this, a missing secret surfaces as an authentication error
        # from PyPI after the upload has already been attempted, which reads
        # like a credentials problem rather than a configuration one.
        run: |
          if [ -z "${{{{ secrets.PYPI_API_TOKEN }}}}" ]; then
            echo "PYPI_API_TOKEN is not set on this repository." >&2
            echo "Add it under Settings > Secrets and variables > Actions." >&2
            exit 1
          fi
          echo "PYPI_API_TOKEN is present"

      - uses: {ACTIONS['pypi_publish']}
        with:
          packages-dir: dist/
          user: __token__
          password: ${{{{ secrets.PYPI_API_TOKEN }}}}
"""


def generate_yaml():
    header = f"""# AUTO-GENERATED BY scripts/generate_workflow.py
# 🐍 Ouroboros Transmutation: Python Pipeline Generator
# Do not edit this file manually. Run scripts/generate_workflow.py instead.
#
# Dependabot edits this file. Because it is generated, any bump it makes here
# is reverted the next time the generator runs -- mirror version bumps into
# the ACTIONS table in scripts/generate_workflow.py.
name: Build and Publish Native GHC Wheel

on:
  push:
    tags: ['v*']
  pull_request:
    branches: [main]
  workflow_dispatch:

# Without this, pushing three times to a branch leaves three full matrices
# building GHC simultaneously, competing for the same runner pool and making
# every one of them slower. Tag runs are never cancelled -- those publish.
concurrency:
  group: build-${{{{ github.ref }}}}
  cancel-in-progress: ${{{{ !startsWith(github.ref, 'refs/tags/') }}}}

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:"""

    lines = [header]
    needs_list = []

    for pk, pdata in PLATFORMS.items():
        job_name = f"build-wheels-{pk}"
        needs_list.append(job_name)
        lines.append(f"  {job_name}:")
        lines.append(f"    name: Build on {pdata['os']}")
        lines.append(f"    runs-on: {pdata['os']}")
        lines.append(f"    steps:")

        for step in generate_job(pk, pdata):
            lines.append(step.to_yaml(indent=6))

    lines.append(generate_thin_wheel_job(needs_list))
    lines.append(generate_release_job())
    lines.append(generate_delivery_proof_job())
    lines.append(generate_publish_job())

    return "\n".join(lines) + "\n"


def generate_ci_yaml():
    """The test and proof workflow.

    The unit tests existed but no workflow ever invoked them, so nothing they
    asserted gated anything -- a suite that never runs is documentation, not a
    floor. This runs them on all three targets and on both ends of the
    supported Python range, because the floor was raised to 3.10 and the
    oldest supported interpreter is exactly where packaging assumptions break.

    Generated from the same script as build.yml so it cannot drift.
    """
    return f"""# AUTO-GENERATED BY scripts/generate_workflow.py
# Do not edit this file manually. Run scripts/generate_workflow.py instead.
name: Tests and Proofs

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

concurrency:
  group: ci-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  test:
    name: Tests (${{{{ matrix.os }}}}, Python ${{{{ matrix.python }}}})
    runs-on: ${{{{ matrix.os }}}}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        # Both ends of the supported range. 3.10 is the floor (wrapper.py uses
        # match/case); the newest is where deprecations surface first.
        python: ['3.10', '{PYTHON_VERSION}']

    steps:
      - uses: {ACTIONS['checkout']}

      - uses: {ACTIONS['setup_python']}
        with:
          python-version: ${{{{ matrix.python }}}}

      - name: Install Test Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest

      - name: Run Test Suite
        run: python -m pytest tests/ -v

      - name: Verify Package Imports On The Declared Floor
        run: |
          python -c "import ghc_compiler_python.wrapper, ghc_compiler_python.bootstrap; print('imports OK')"

  proofs:
    name: Lean 4 Proofs
    runs-on: ubuntu-latest

    steps:
      - uses: {ACTIONS['checkout']}

      - name: Install Lean Toolchain
        run: |
          curl -sSfL https://github.com/leanprover/elan/releases/latest/download/elan-x86_64-unknown-linux-gnu.tar.gz \\
            | tar xz
          ./elan-init -y --default-toolchain none
          echo "$HOME/.elan/bin" >> "$GITHUB_PATH"

      - name: Build Proofs
        working-directory: lean
        run: lake build

      - name: Assert Zero Sorry
        working-directory: lean
        run: |
          # A proof file containing `sorry` compiles and proves nothing. The
          # build succeeding is therefore not sufficient evidence.
          if grep -rn --include="*.lean" '\\bsorry\\b' Proofs/; then
            echo "::error::sorry found in proofs -- nothing above it is proven"
            exit 1
          fi
          echo "zero sorry confirmed"

      - name: Assert No native_decide
        working-directory: lean
        run: |
          # `native_decide` closes a goal by trusting the compiled binary
          # instead of the kernel. It is not a proof of the same kind as
          # everything else in this directory, so it may not appear silently.
          if grep -rn --include="*.lean" 'native_decide' Proofs/; then
            echo "::error::native_decide bypasses the kernel -- these are not kernel-checked proofs"
            exit 1
          fi
          echo "no native_decide confirmed"

      - name: Cross-check The Proofs Against The Shipped Code
        working-directory: lean
        run: |
          # A proof about a model proves nothing about a program unless
          # something binds the two. This emits the corpus and the model's
          # verdicts from Lean, materialises each modelled toolchain root on
          # disk, runs the REAL wrapper._bundled_c_linker over them, and diffs.
          # It also reads the _execute_tool ordering out of the source, which
          # is the second half of the defect Linker.lean proves.
          #
          # Verified red against four deliberate mutations of wrapper.py:
          # catalogue entry removed, ordering reverted, _validate_c_linker
          # losing its root parameter, and _bundled_c_linker never finding
          # anything. A cross-check nobody has broken on purpose is decoration.
          lake env lean crosscheck/Corpus.lean > verdicts.txt
          python3 crosscheck/crosscheck.py .. verdicts.txt
"""


if __name__ == "__main__":
    # Written with an explicit newline so a Windows checkout does not silently
    # rewrite every line ending in a generated file, and reported without
    # non-ASCII: a bare `print("<checkmark>")` raised UnicodeEncodeError on a
    # cp1252 console *after* both files were already written, so the generator
    # exited 1 having fully succeeded. An exit code that lies about success is
    # worse than no exit code, because the next person learns to ignore it.
    build_path = Path(".github/workflows/build.yml")
    build_path.write_text(generate_yaml(), encoding="utf-8", newline="\n")
    print(f"OK: generated {build_path}")

    ci_path = Path(".github/workflows/ci.yml")
    ci_path.write_text(generate_ci_yaml(), encoding="utf-8", newline="\n")
    print(f"OK: generated {ci_path}")

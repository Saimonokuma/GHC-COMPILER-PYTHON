#!/usr/bin/env python3
"""
Ouroboros Transmutation: Python Pipeline Generator for GitHub Actions.
Eliminates YAML boilerplate and complex `if:` conditional logic in GitHub Actions
by compiling a Python-based pipeline definition into a static, unrolled YAML workflow.
"""

from pathlib import Path

class Step:
    def __init__(self, name=None, uses=None, run=None, shell=None, with_args=None, env=None):
        self.name = name
        self.uses = uses
        self.run = run
        self.shell = shell
        self.with_args = with_args
        self.env = env

    def to_yaml(self, indent=6):
        ind = " " * indent
        lines = []
        if self.uses:
            if self.name:
                lines.append(f"{ind}- name: {self.name}")
                lines.append(f"{ind}  uses: {self.uses}")
                inner_ind = indent + 2
            else:
                lines.append(f"{ind}- uses: {self.uses}")
                inner_ind = indent + 2
            if self.with_args:
                lines.append(f"{' ' * inner_ind}with:")
                for k, v in self.with_args.items():
                    lines.append(f"{' ' * inner_ind}  {k}: {v}")
        else:
            lines.append(f"{ind}- name: {self.name}")
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
                        lines.append(f"{ind}    {line}")
                else:
                    lines.append(f"{ind}  run: {self.run}")
        return "\n".join(lines)

PLATFORMS = {
    "linux": {
        "os": "ubuntu-latest",
        "platform": "manylinux_2_39_x86_64",
    },
    "macos": {
        "os": "macos-latest",
        "platform": "macosx_arm64",
    },
    "windows": {
        "os": "windows-latest",
        "platform": "win_amd64",
    }
}

def generate_job(platform_key, platform_data):
    steps = []
    def add_step(name=None, uses=None, run=None, shell=None, with_args=None):
        steps.append(Step(name=name, uses=uses, run=run, shell=shell, with_args=with_args))

    add_step(uses="actions/checkout@v4")

    if platform_key == "linux":
        add_step(name="Free disk space (Linux)", run="sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc\nsudo apt-get clean\ndf -h")

    add_step(uses="actions/setup-python@v5", with_args={"python-version": "'3.10'", "cache": "'pip'"})

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

    add_step(name="Install Python Build Dependencies", run="python -m pip install --upgrade pip\npip install build hatchling")
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

    add_step(name="Build PEP 427 Python Wheel", run="python -m build --wheel")

    if platform_key == "linux":
        add_step(name="Vendor Dynamic Libraries (Linux)", shell="bash", run="""# Find the exact directory where the nested .so files are located inside ghc-bindist/lib/
LINUX_LIB_DIR=$(find ghc-bindist/lib -name "libHS*.so" | head -n 1 | xargs dirname)
if [ -n "$LINUX_LIB_DIR" ]; then
    echo "Found Linux GHC libraries at $LINUX_LIB_DIR"
    export LD_LIBRARY_PATH="$(pwd)/$LINUX_LIB_DIR:${LD_LIBRARY_PATH:-}"
else
    echo "WARNING: Could not find Linux GHC libraries directory."
fi

# Run auditwheel with the LD_LIBRARY_PATH so it can find the internal .so dependencies
auditwheel repair dist/*.whl --plat manylinux_2_39_x86_64 -w wheelhouse/
rm -rf dist/*
mv wheelhouse/*.whl dist/""")
    elif platform_key == "macos":
        add_step(name="Vendor Dynamic Libraries (macOS)", shell="bash", run="""echo "Running delocate-wheel to verify and bundle dependencies"
# Our rpaths are already correctly pointing to the internal libs
delocate-wheel -v dist/*.whl""")

    add_step(name="End-to-End Compilation Validation", shell="bash", run="""python -m venv test-env
if [ -f test-env/Scripts/activate ]; then
  source test-env/Scripts/activate
else
  source test-env/bin/activate
fi

pip install dist/*.whl
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
  ./HelloWorld.exe
else
  ./HelloWorld
fi

cabal-wrapper --version
deactivate""")

    add_step(name="Upload Artifacts", uses="actions/upload-artifact@v4", with_args={"name": f"ghc-wheels-{platform_data['platform']}", "path": "dist/*.whl", "retention-days": "30"})

    return steps

def generate_yaml():
    header = """# AUTO-GENERATED BY scripts/generate_workflow.py
# 🐍 Ouroboros Transmutation: Python Pipeline Generator
# Do not edit this file manually. Run scripts/generate_workflow.py instead.
name: Build and Publish Native GHC Wheel

on:
  push:
    tags: ['v*']
  pull_request:
    branches: [main]
  workflow_dispatch:

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

        steps = generate_job(pk, pdata)
        for step in steps:
            lines.append(step.to_yaml(indent=6))

    # Add publish job
    needs_str = "[" + ", ".join(needs_list) + "]"
    publish_job = f"""
  publish-to-pypi:
    name: Zero-Trust PyPI Deployment via OIDC
    needs: {needs_str}
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')

    environment:
      name: pypi
      url: https://pypi.org/p/ghc-compiler-python

    permissions:
      id-token: write
      contents: read

    steps:
      - uses: actions/download-artifact@v4
        with:
          path: dist/
          merge-multiple: true

      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: dist/"""

    lines.append(publish_job)

    return "\n".join(lines) + "\n"

if __name__ == "__main__":
    yaml_content = generate_yaml()
    out_path = Path(".github/workflows/build.yml")
    out_path.write_text(yaml_content, encoding="utf-8")
    print(f"✅ Generated {out_path} successfully.")

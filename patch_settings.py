import re

with open("ghc_compiler_python/wrapper.py", "r") as f:
    content = f.read()

old_settings = """    @classmethod
    def patch_build_time(cls, path: Path, version: str, placeholder: str) -> int:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            patterns = [
                (r"/usr/local/lib/ghc-" + re.escape(version), f"{placeholder}/lib/ghc-{version}"),
                (r"/usr/lib/ghc-" + re.escape(version), f"{placeholder}/lib/ghc-{version}"),
                (r"/opt/ghc/" + re.escape(version), f"{placeholder}/lib/ghc-{version}"),
                (r"/ghc-prefix/lib/ghc-" + re.escape(version), f"{placeholder}/lib/ghc-{version}"),
                (r"/ghc-prefix", placeholder),
            ]
            modified = False
            for pattern, replacement in patterns:
                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    content = new_content
                    modified = True
            if modified:
                path.write_text(content, encoding="utf-8")
                return 1
        except OSError as e:
            sys.stderr.write(f"WARNING: Failed to patch {path}: {e}\\n")
        return 0"""

new_settings = """    @classmethod
    def patch_build_time(cls, path: Path, version: str, placeholder: str) -> int:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            # 🧪 Alchemist: Combine regex patterns into a single pass using alternation
            pattern = re.compile(
                r"/(?:usr/local/lib|usr/lib|opt|ghc-prefix)/ghc(?:-|/)" + re.escape(version) + r"|/ghc-prefix"
            )

            def repl(m: re.Match) -> str:
                match = m.group(0)
                if match == "/ghc-prefix":
                    return placeholder
                return f"{placeholder}/lib/ghc-{version}"

            new_content = pattern.sub(repl, content)
            if new_content != content:
                path.write_text(new_content, encoding="utf-8")
                return 1
        except OSError as e:
            sys.stderr.write(f"WARNING: Failed to patch {path}: {e}\\n")
        return 0"""

content = content.replace(old_settings, new_settings)

with open("ghc_compiler_python/wrapper.py", "w") as f:
    f.write(content)

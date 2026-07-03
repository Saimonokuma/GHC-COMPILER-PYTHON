import re
placeholder = "@GHC_PREFIX@"
version = "9.4.8"

content = "/ghc-prefix/lib/ghc-9.4.8/settings /ghc-prefix /usr/local/lib/ghc-9.4.8"
pattern = re.compile(r"/(?:usr/local/lib|usr/lib|opt|ghc-prefix)/ghc(?:-|/)" + re.escape(version) + r"|/ghc-prefix")
new_content = pattern.sub(lambda m: placeholder if m.group(0) == "/ghc-prefix" else f"{placeholder}/lib/ghc-{version}", content)
print(new_content)

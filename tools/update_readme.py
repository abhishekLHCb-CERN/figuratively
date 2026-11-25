"""Regenerate the option tables in README.md from the option registry."""
import pathlib

from figuratively.options import options_markdown

p = pathlib.Path(__file__).resolve().parents[1] / "README.md"
s = p.read_text()
a, b = "<!-- options:start -->\n", "<!-- options:end -->"
p.write_text(s[: s.index(a) + len(a)] + options_markdown() + s[s.index(b):])
print("README option tables updated")

docs = p.parent / "docs"
docs.mkdir(exist_ok=True)
(docs / "options.md").write_text("# All options\n\nGenerated from the option registry (`fg.options()` prints the same list).\n\n"
                                 + options_markdown())
print("docs/options.md updated")

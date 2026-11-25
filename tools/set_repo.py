"""Fill in your GitHub details once the repository exists.

    python tools/set_repo.py YOUR_GITHUB_NAME [repo-name]

It makes the README images absolute (PyPI cannot show relative images), adds the project links to pyproject.toml and
CITATION.cff, and adds badges. Run it before building the release.
"""
import pathlib
import re
import sys

if len(sys.argv) < 2:
    sys.exit(__doc__)
owner = sys.argv[1]
repo = sys.argv[2] if len(sys.argv) > 2 else "figuratively"
root = pathlib.Path(__file__).resolve().parents[1]
version = re.search(r'__version__ = "([^"]+)"', (root / "src/figuratively/__init__.py").read_text()).group(1)
base = f"https://github.com/{owner}/{repo}"
raw = f"https://raw.githubusercontent.com/{owner}/{repo}/v{version}"

readme = root / "README.md"
s = readme.read_text()
s = re.sub(r"\]\((docs/img/[^)]+)\)", lambda m: f"]({raw}/{m.group(1)})", s)       # images become absolute
s = re.sub(r"https://raw\.githubusercontent\.com/[^/]+/[^/]+/v[^/]+/docs/img", f"{raw}/docs/img", s)
badges = (f"[![PyPI](https://img.shields.io/pypi/v/figuratively)](https://pypi.org/project/figuratively/) "
          f"[![Python](https://img.shields.io/pypi/pyversions/figuratively)](https://pypi.org/project/figuratively/) "
          f"[![CI]({base}/actions/workflows/ci.yml/badge.svg)]({base}/actions) "
          f"[![Licence: MIT](https://img.shields.io/badge/licence-MIT-green)]({base}/blob/main/LICENSE)\n")
if "img.shields.io/pypi/v/figuratively" not in s:
    s = s.replace("**Publication-quality plots straight from ROOT files, with no ROOT installation.**\n",
                  "**Publication-quality plots straight from ROOT files, with no ROOT installation.**\n\n" + badges, 1)
readme.write_text(s)

pp = root / "pyproject.toml"
s = pp.read_text()
if "[project.urls]" not in s:
    s = s.replace("[project.scripts]", f'''[project.urls]
Homepage = "{base}"
Documentation = "https://{owner}.github.io/{repo}/"
Source = "{base}"
Issues = "{base}/issues"
Changelog = "{base}/blob/main/CHANGELOG.md"

[project.scripts]''', 1)
    pp.write_text(s)
cf = root / "CITATION.cff"
s = cf.read_text()
if "repository-code" not in s:
    cf.write_text(s.replace("license: MIT", f"license: MIT\nrepository-code: {base}", 1))
print(f"done: {base}  (images pinned to tag v{version})")

# Contributing

Thank you for helping. Figuratively is small on purpose: one call, sensible defaults, and every customisation optional.

```bash
git clone <your fork> && cd figuratively
pip install -e ".[dev,docs]"
pytest                       # the whole suite, about 40 s
ruff check src tests         # style
bandit -q -r src             # security scan
python tools/update_readme.py  # after changing options (the option tables are generated)
```

Please:
- add a test with every change; every option must be documented in `options.py` (a test enforces it);
- use toy data only in tests, examples and issues. **Never post real analysis data, unpublished results or anything
  covered by a collaboration's rules** (blinded quantities especially);
- be kind. We follow the spirit of the Contributor Covenant: be respectful, assume good faith, and keep discussion
  about the work.

By contributing you agree that your contribution is released under the MIT licence.

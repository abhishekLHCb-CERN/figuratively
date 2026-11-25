# Releasing Figuratively 1.0.0

Everything is prepared; **nothing has been uploaded**. Uploading needs your accounts and cannot be undone (a version
number on PyPI can never be reused), so do these steps yourself, in this order.

## 0. Once: accounts
- GitHub account, and a PyPI account with two-factor authentication (https://pypi.org/account/register/).
- Optional: TestPyPI (https://test.pypi.org), Zenodo (log in with GitHub) for a citable DOI, Read the Docs.

## 1. Create the repository
Create an empty **public** repository named `figuratively` on GitHub (no README, no licence: they exist here), then:

```bash
cd Figuratively            # the project folder
python tools/set_repo.py YOUR_GITHUB_NAME      # makes README images absolute, adds links and badges
git init && git add . && git commit -m "Figuratively 1.0.0"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_NAME/figuratively.git
git push -u origin main
git tag v1.0.0 && git push origin v1.0.0
```
CI (`.github/workflows/ci.yml`) then runs the tests on Python 3.10 to 3.13, a security scan and a dependency audit.
Please read the first CI run: Python 3.10, 3.11 and 3.13 were not available where this was built.

## 2. Rehearse on TestPyPI (recommended)
```bash
pip install build twine
python -m build
twine check dist/*
twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple figuratively
figly --version
```

## 3. Publish on PyPI
Easiest and safest is Trusted Publishing, which stores no password:
1. On pypi.org: Your projects > Publishing > add a pending publisher: owner `YOUR_GITHUB_NAME`, repository
   `figuratively`, workflow `release.yml`, environment `pypi`.
2. On GitHub: create the environment `pypi` (Settings > Environments).
3. Create a GitHub release for tag `v1.0.0`. The `release` workflow builds, checks and uploads.

Or manually: `twine upload dist/*` with an API token (never commit the token).

## 4. Make it visible
- **Docs site**: enable GitHub Pages (Settings > Pages > Source: GitHub Actions); the `docs` workflow publishes
  `https://YOUR_GITHUB_NAME.github.io/figuratively/`. Or import the repository on Read the Docs (`.readthedocs.yaml` is ready).
  The built site is also in the release bundle (`docs-site/`), which any static host (Netlify, Cloudflare Pages) accepts.
- **Zenodo**: connect GitHub, switch the repository on, then publish the release: you get a DOI to cite
  (`CITATION.cff` is used automatically).
- **Announce**: your group's mailing list or Mattermost, the Scikit-HEP "software" channels, and your thesis
  acknowledgements.
- **conda-forge** (later): copy a `grayskull pypi figuratively` recipe into a PR to `conda-forge/staged-recipes`.

## 5. After release
Bump `__version__`, add a CHANGELOG entry, tag again. Never re-upload an existing version.

## Checks done before this bundle was made
Tests (211, plus fuzzing of corrupted ROOT files), `bandit` (no medium/high findings), `pip-audit` (no known
vulnerabilities in the 20 dependencies), `twine check`, fresh-environment install, shell-injection test for the C++ header,
and a scan of the project for personal data (none). See `SECURITY.md` and `NOTICE`.

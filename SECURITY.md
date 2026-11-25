# Security

## Reporting a vulnerability
Please do not open a public issue for a security problem. Contact the maintainer (Abhishek Bohare) privately through the
contact route listed on the project page (GitHub "Report a vulnerability" under the Security tab). Expect an
acknowledgement within a week.

## What Figuratively does and does not do
- It makes **no network connections** and sends **no telemetry**. A test checks that the source contains no network
  or shell code.
- It never evaluates text as code: command-line values are parsed with `ast.literal_eval`, configuration with
  `tomllib`.
- Configuration files (`figuratively.toml`) are **only used if they belong to you and others cannot write to them**;
  they are searched from the current folder up to your home folder, never above it. They may only set documented
  options (never call methods such as `save`), may only write below the project folder, and may not name a URL.
- The C++ header quotes every argument for the shell and creates its temporary file atomically.

## What you should do
- **Only open ROOT files you trust.** ROOT files are a binary format read by the uproot library; a hostile file can
  waste time or memory. Figuratively fails cleanly on corrupted files (it is fuzz-tested), but cannot make an
  untrusted file safe to process.
- Keep dependencies up to date (`pip install -U figuratively`); releases are checked with `pip-audit` and `bandit`.

## Supported versions
The latest 1.x release.

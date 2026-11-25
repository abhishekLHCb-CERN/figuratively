# Changelog

All notable changes to this project are documented here. Format: Keep a Changelog; versioning: SemVer.

## [Unreleased]
### Fixed
- `scale_x=` on a TCanvas gave an empty figure: the canvas's x range was not scaled with the data.
- `strict=True` raised on every ordinary RooFit canvas because of objects ROOT adds by itself (the default title box,
  colour tables). These are no longer reported; a title of your own still is, and a misspelt name is reported first.

## [1.1.3] - 2026-11-25
### Fixed
- Fit components named with `RooFit.Name()` were silently left out of the figure (also with `strict=True`). Every
  further curve beside the total is now a component under its name; the total is the largest curve.
- A `VisualizeError` band could be taken for the total fit, giving wrong pulls. Bands are now recognised, not drawn,
  and reported.
- A `RooPlot` saved to a file, or passed live from PyROOT, could not be read.
- A canvas could fail to read (`IndexError`) when the same file also held a `RooPlot`. Objects of a canvas that cannot
  be read are now reported, and a frame with nothing to draw gives a clear error.
- `figuratively.h` did not compile with ROOT older than 6.32.
- `figly tree` with an expression such as `pt/1000` wrote into a sub-folder; the file is now `..._pt_over_1000`.

## [1.1.2] - 2026-11-25
### Changed
- First release archived on Zenodo (citable DOI per version). No code changes.

## [1.1.1] - 2026-11-25
### Fixed
- `tone="mono"` now draws 2D histograms with a grey colour map (`Plot.zaxis(cmap=...)` still wins).

## [1.1.0] - 2026-11-25
### Added
- `fg.tree(...)` and `figly tree`: histogram a TTree or RNTuple branch (or an expression) with a cut and weights; the
  result is an ordinary histogram for `fg.plot`. Expressions use a checked mini-language, never `eval`.
- `fg.grid(...)`: several plots in one vector figure, with per-cell options, titles and a legend policy.
- `fg.compare(...)`: overlay several fits of the same data with ratio panels.
- `tone="colour" | "mono" | "dark"` (also the presets `mono` and `dark`) and the `mono` palette.
- A TTree passed to `fg.plot` now explains what to do instead of a bare error.
### Changed
- `palette=` now also colours overlaid histograms and graphs, not only fit components.
- `.zenodo.json` and README text for Zenodo archiving (DOI issued from the next GitHub release).

## [1.0.1] - 2026-11-25
### Fixed
- The `figly` command printed a full traceback for a mistyped object name or a missing file; it now prints one
  `figuratively: error: ...` line (with the "did you mean" hint) and exits with code 1. `--debug` restores the traceback.
- Warnings from the command line are one clean line instead of repeating the source line.
- Saving a PDF no longer prints repeated fontTools "timestamp seems very low" notices.

## [1.0.0] - 2026-11-25
### Added
- `figuratively.plot("file.root:object")`: RooFit canvases (data, total, components, pulls), data/MC overlays with
  ratio panel, 2D histograms, graphs, whole-file batch mode.
- `figly` / `figuratively` command line, `figuratively.toml` project configuration.
- Reading of ROOT `TCanvas` objects without ROOT (via uproot, with a guarded fallback).
- "Did you mean" errors for missing objects, notebook inline display.
- Customisation: `components=` (compact style strings), `merge=`, `order=`, `styles=`, `blind=`, labelled
  `vline` / `hline` / `span`, size presets (`column`, `double`, `slide`), `scale_x`, `rebin`, `dpi`, `legend` forms.
- Discovery: `fg.options()`, `fg.inspect()`, `figly inspect`, `figly init`, "did you mean" for options and
  component names, `strict=True`.
- Colours: ROOT colour indices are translated into refined colours (hue kept, lightness and chroma tamed,
  neighbours kept visibly apart), plus R-style palettes (`r4`, `okabe-ito`, `tableau10`, `dark2`, `hcl`).
- ROOT integration: `fg.plot(canvas)` with live PyROOT objects, a C++ header (`figly header`) with
  `Figuratively::Plot(canvas)`, and the `figly` command for any `.root` file.
- Multi-panel canvases give one figure per panel; the text written on the canvas (e.g. the bin range) becomes an
  info line; a wrong object name falls back to the only object in the file; unreadable objects in a canvas are skipped.
- Renaming: `labels` (dict or list, including `data` and `total`), `Plot.rename`, and settable built-in texts.
- Safeguards: `fg.check`, `fg.summary` (text, csv, latex), `figly check` / `figly summary`, warnings for a mis-scaled
  curve, huge pulls, empty bins, silent normalisation, a leaking blind window and undrawn canvas objects
  (`checks=False`, `strict=True`). Pulls use RooFit's bin-averaged curve; the pull range grows with large pulls.
- Canvas fidelity: pad log scales and the frame x range are used as defaults.
- Workflow: presets (built-in and your own), glob and list inputs, `view=True`, comparison of several fits,
  `combine=True` for one figure with all panels of a canvas.
- Security and ethics: configuration files are trusted only if you own them and others cannot write to them, may only
  set documented options and write inside the project; no URLs as styles; the C++ header uses an atomic temporary
  file and quotes every argument; fuzz tests on corrupted ROOT files; `SECURITY.md`, `NOTICE`, `AUTHORS.md`.
### Notes
- No collaboration label is drawn unless the user asks for one (`label=`, `exp=`).

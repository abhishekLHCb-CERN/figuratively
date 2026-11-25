# Troubleshooting

**`'name' not found in file.root`**: the object name differs. `figly ls file.root` lists the objects. If the file holds
exactly one drawable object it is used automatically, with a note.

**`could not read canvas`**: uproot cannot read every canvas. Save the `RooPlot` or the histograms themselves, or report it
with your uproot version.

**Warnings about the fit**: they are the point of `checks`. Read them; `checks=False` silences them.

**My `figuratively.toml` is ignored**: it must belong to you and not be writable by others (`chmod go-w figuratively.toml`),
and it must sit between the current folder and your home folder.

**Nothing in the legend for a component**: its name is in the file; see `fg.inspect(...)`. Use `labels=` to rename.

**Figures are too big or too small**: `size="column"`, `"double"`, `"slide"` or `size=(width, height)` in inches; text
follows the width.

**The files appear and vanish**: some cleanup tools delete new files in `Downloads`; write elsewhere with `outdir=`.

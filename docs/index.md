# Figuratively

**Publication-quality plots straight from ROOT files, with no ROOT installation.**

![A RooFit-style fit with six components and a pull panel, made from toy data](img/01_fit_components.png)

*Toy data. One call: `fg.plot("fit.root:canvas")`.*

```bash
pip install figuratively
```
```python
import figuratively as fg
fg.plot("fit.root")          # every canvas, histogram and graph in the file, as pdf and png
```

## Why

- **One line.** It reads RooFit canvases, multi-panel canvases, histograms and graphs, detects the data, total,
  components, units and pulls, and draws them cleanly.
- **Faithful.** Your macro's colours and line styles are translated (R-inspired), log scales and the frame range are
  respected, and `fg.check` catches a curve that does not match the data.
- **Customisable when you need it.** Rename legends, merge components, blind a window, compare two fits, put all
  panels in one figure, save your own presets.
- **Safe.** No network, no telemetry, no shell; configuration is only used if you own it.

Created by **Abhishek Bohare**. [About and credit](about.md).

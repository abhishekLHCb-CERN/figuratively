# Quick start

```bash
pip install figuratively
figly --version
```

## Plot a file

```python
import figuratively as fg

fg.plot("fit.root:canvas")                       # one canvas: data, total, components, pulls
fg.plot("f.root:h_data", "f.root:h_mc")          # data against simulation, ratio panel added
fg.plot("f.root")                                # everything in the file
fg.plot("Helicity*.root")                        # every matching file, one plot each
fg.plot("run1.root:c", "run2.root:c")            # compare two fits (ratio panel zoomed to the differences)
```
```bash
figly fit.root            # the same from the shell
figly inspect fit.root:c  # what is inside, and a call you can copy and edit
```

Plots go to a `plots/` folder next to the ROOT file as PDF and PNG. A canvas with several panels gives one figure per
panel, or one combined figure with `combine=True`.

## Make it yours

```python
fg.plot("fit.root:c", labels={"sig": "Signal", "data": "Observed"}, logy=True, preset="thesis")
```

Put recurring choices in a `figuratively.toml` (`figly init fit.root:c` writes one with your component names filled in).
Every option is listed in [All options](options.md) or by `fg.options()`.

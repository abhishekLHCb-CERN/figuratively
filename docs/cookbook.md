# Cookbook

| I want to ... | Write |
|---|---|
| plot everything in a file | `fg.plot("f.root")` |
| rename legend entries | `fg.plot(f, labels={"sig": "Signal", "total": "Fit"})` or `labels=["Data", "Fit", "Signal"]` |
| hide a component | `fg.plot(f, hide=["bkg"])` |
| sum backgrounds into one entry | `fg.plot(f, merge={"Backgrounds": ["comb", "bkg*"]})` |
| change one component's look | `fg.plot(f, components={"sig": "red dashed fill"})` |
| stack the components | `fg.plot(f, stack=True)` |
| log scale and a zoom | `fg.plot(f, logy=True, xlim=(1800, 1900))` |
| blind a window | `fg.plot(f, blind=(1840, 1890), blind_curves=True)` |
| mark a cut and a region | `fg.plot(f, vline=(1865, "cut"), span=(1850, 1880, "signal"))` |
| column-width figure for a paper | `fg.plot(f, preset="paper")` or `size="column"` |
| slides version | `fg.plot(f, preset="slides")` |
| change the text | `fg.plot(f, label="Work in progress", info="2018 data", ylabel_prefix="Events")` |
| all panels in one figure | `fg.plot("f.root", combine=True)` |
| compare nominal and variant | `fg.plot("nominal.root:c", "variant.root:c", labels=["Data", "Nominal", "Variant"])` |
| check the fit numbers | `fg.check("f.root:c", nparams=10)` |
| a table for the thesis | `fg.summary("f.root", nparams=10, fmt="latex")` |
| rename after plotting | `p = fg.plot(f, save=False); p.rename({"sig": "Signal"}); p.save("fig.pdf")` |
| raw matplotlib access | `p = fg.plot(f, save=False); p.draw(); p.ax.axvline(1865)` |

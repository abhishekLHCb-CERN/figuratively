# Trust the figure

A plot that looks fine can still be wrong. Figuratively checks the numbers behind it.

```python
fg.check("fit.root:canvas", nparams=10)   # per panel: data vs curve integral, chi2/ndf, empty bins, largest pull
fg.summary("fit.root", nparams=10)        # one row per panel: entries, chi2/ndf and the yield of every component
fg.summary(files, fmt="latex")            # or "csv"
```

While plotting you get a warning when the curve and the data disagree in normalisation (beyond Poisson noise), when many
pulls exceed 5, when there are far more empty bins than the curve predicts, when histograms were normalised
automatically, when a blinded window still shows the model, and when the canvas holds objects that are not drawn
(a `TLegend`, a stats box, a line). `checks=False` silences them, `strict=True` turns them into errors.

Low-statistics panels get a note instead of a warning: the Gaussian chi2 is only approximate there.

Pulls follow RooFit's convention (the curve averaged over each bin); `pull={"mode": "centre"}` uses the bin centre.

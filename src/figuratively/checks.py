"""Sanity checks and summary tables: the numbers behind a figure, so a mis-scaled curve, a poor fit or a
half-empty histogram cannot slip through unnoticed."""
from __future__ import annotations

import numpy as np

from . import data as D
from .plot import model_average


def panel_numbers(items, nparams=None):
    """Data/model numbers of one RooFit panel, or None when it has no data points or no total curve."""
    data = next((o for k, o in items.items() if isinstance(o, D.G) and o.classname == "RooHist"
                 and not k.startswith(("pull_", "resid_"))), None)
    tkey, ckeys, _bands = D.roofit_curves(items)
    total = items.get(tkey) if tkey is not None else None
    if data is None or total is None:
        return None
    lo, hi = data.x - data.exl, data.x + data.exh
    mod = model_average(total, lo, hi)
    err = np.where(data.y > mod, data.eyl, data.eyh)
    ok = err > 0
    pull = np.where(ok, (data.y - mod) / np.where(ok, err, 1.0), 0.0)
    entries, model = float(data.y.sum()), float(mod.sum())
    comps = {c: float(model_average(items[k], lo, hi).sum()) for c, k in ckeys.items()}
    n_bins = len(data.y)
    out = dict(entries=entries, model=model, ratio=entries / model if model > 0 else float("nan"),
               bins=n_bins, empty=int((data.y == 0).sum()), chi2=float((pull[ok] ** 2).sum()),
               used=int(ok.sum()), max_pull=float(np.max(np.abs(pull))) if n_bins else 0.0,
               large=int((np.abs(pull) > 5).sum()), components=comps, warnings=[], notes=[])
    out["ndf"] = out["used"] - nparams if nparams is not None else None
    w, notes = out["warnings"], out["notes"] = out["warnings"], []
    # a normalisation offset only matters if it is both sizeable and beyond Poisson noise
    sigma = abs(entries - model) / np.sqrt(max(model, 1.0))
    out["norm_sigma"] = sigma
    if abs(out["ratio"] - 1) > 0.05 and sigma > 3:
        w.append(f"the curve and the data disagree in normalisation: data {entries:.0f} entries, curve {model:.0f} "
                 f"(ratio {out['ratio']:.3f}, {sigma:.1f} sigma)")
    if out["large"] >= max(2, 0.1 * n_bins):
        w.append(f"{out['large']} of {n_bins} bins have |pull| above 5 (largest {out['max_pull']:.1f}): "
                 "the curve does not describe the data")
    expected_empty = float(np.exp(-np.clip(mod, 0, 50)).sum())  # empty bins that Poisson statistics predict
    out["expected_empty"] = expected_empty
    if out["empty"] > expected_empty + 3 * np.sqrt(max(expected_empty, 1.0)) + 1:
        w.append(f"{out['empty']} of {n_bins} bins are empty, but the curve predicts only {expected_empty:.0f}: "
                 "the data and the curve disagree at low counts")
    if n_bins and entries / n_bins < 5:
        notes.append(f"low statistics ({entries / n_bins:.1f} entries per bin on average): the Gaussian chi2 is only "
                     "approximate; a Poisson likelihood is more reliable")
    return out


def fit_warnings(items, nparams=None) -> list:
    n = panel_numbers(items, nparams)
    return n["warnings"] if n else []


def _expand(spec):
    """A bare file name stands for every canvas in it; 'file.root:name' is one object."""
    if isinstance(spec, str) and D.split_spec(spec)[1] is None:
        return [f"{spec}:{k}" for k, c in D.list_objects(spec).items() if c.startswith(("TCanvas", "RooPlot"))]
    return [spec]


def _panels(spec):
    from .auto import _resolve

    name, kind, payload, texts = _resolve(spec)
    if kind == "pads":
        return name, [(items, tx) for _, items, tx in payload]
    if kind == "frame":
        return name, [(payload, texts)]
    return name, []


def check(spec, nparams=None, show=True) -> list:
    """Sanity numbers for every panel of a fit canvas: data and curve integrals, chi2, empty bins, large pulls.

    >>> fg.check("fit.root:canvas", nparams=10)
    """
    rows = []
    for one in _expand(spec):
        rows += _check_one(one, nparams, show)
    return rows


def _check_one(spec, nparams, show):
    name, panels = _panels(spec)
    rows = []
    for k, (items, texts) in enumerate(panels, 1):
        n = panel_numbers(items, nparams)
        if n is None:
            continue
        n.update(panel=k, label="; ".join(texts))
        rows.append(n)
        if show:
            chi = f"chi2/ndf = {n['chi2']:.1f}/{n['ndf']}" if n["ndf"] is not None else f"chi2 = {n['chi2']:.1f} ({n['used']} bins; give nparams= for ndf)"
            print(f"{name} panel {k}" + (f" [{n['label']}]" if n["label"] else "") + f": data {n['entries']:.0f}, curve "
                  f"{n['model']:.0f} (x{n['ratio']:.3f}), {chi}, max |pull| {n['max_pull']:.1f}, empty bins {n['empty']}/{n['bins']}")
            for w in n["warnings"]:
                print("   WARNING:", w)
            for note in n["notes"]:
                print("   note:", note)
    if show and not rows:
        print(f"{name}: no RooFit data and total curve found, nothing to check")
    return rows


def summary(specs, nparams=None, fmt="text", show=True) -> str:
    """A table with one row per panel: entries, chi2/ndf and the yield of every component.
    fmt: 'text', 'csv' or 'latex'. Handy for systematic tables and for finding the largest component."""
    from pathlib import Path

    from .data import split_spec

    specs = [specs] if isinstance(specs, str) else list(specs)
    rows = []
    for sp0 in specs:
        for sp in _expand(sp0):
            _, panels = _panels(sp)
            stem = Path(split_spec(sp)[0]).stem
            for k, (items, texts) in enumerate(panels, 1):
                n = panel_numbers(items, nparams)
                if n:
                    rows.append((stem, k, "; ".join(texts), n))
    comps = list(dict.fromkeys(c for *_, n in rows for c in n["components"]))
    head = ["file", "panel", "label", "entries", "chi2/ndf" if nparams is not None else "chi2", *comps]

    def cells(stem, k, label, n):
        chi = f"{n['chi2']:.1f}/{n['ndf']}" if n["ndf"] is not None else f"{n['chi2']:.1f}"
        return [stem, str(k), label, f"{n['entries']:.0f}", chi, *[f"{n['components'].get(c, 0):.1f}" for c in comps]]

    body = [cells(*r) for r in rows]
    if fmt == "csv":
        text = "\n".join(",".join(f'"{c}"' if "," in c else c for c in row) for row in [head, *body])
    elif fmt == "latex":
        esc = lambda t: t.replace("_", r"\_").replace("#", r"\#").replace("%", r"\%")
        text = "\n".join([r"\begin{tabular}{" + "l" * 3 + "r" * (len(head) - 3) + "}", r"\hline",
                          " & ".join(esc(h) for h in head) + r" \\", r"\hline",
                          *[" & ".join(esc(c) for c in row) + r" \\" for row in body], r"\hline", r"\end{tabular}"])
    elif fmt == "text":
        widths = [max(len(r[i]) for r in [head, *body]) for i in range(len(head))]
        text = "\n".join("  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in [head, *body])
    else:
        raise ValueError(f"fmt must be 'text', 'csv' or 'latex', got {fmt!r}")
    if show:
        print(text)
    return text

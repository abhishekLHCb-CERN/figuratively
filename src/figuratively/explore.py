"""fg.inspect(): see what a ROOT object contains and get a call you can copy and edit."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import data as D
from .auto import _is_roofit, _resolve, title_label

_trapz = getattr(np, "trapezoid", None) or np.trapz


def _frame_info(items):
    data = [o for k, o in items.items() if isinstance(o, D.G) and o.classname == "RooHist"
            and not k.startswith(("pull_", "resid_"))]
    curves = {k: o.trimmed() for k, o in items.items() if isinstance(o, D.G) and o.classname == "RooCurve"}
    total = next((c for k, c in curves.items() if not D.parse_roofit_name(k)["components"]), None)
    t_int = float(_trapz(total.y, total.x)) if total is not None else 0.0
    comps = []
    for k, c in curves.items():
        n = "+".join(D.parse_roofit_name(k)["components"])
        if n:
            integ = float(_trapz(c.y, c.x))
            comps.append(dict(name=n, peak=float(np.max(c.y)), integral=integ,
                              share=integ / t_int if t_int else float("nan")))
    return data, total, comps


def inspect(spec, show: bool = True) -> dict:
    """Describe a ROOT object and print the exact fg.plot call to edit.

    >>> fg.inspect("fit.root:canvas")
    """
    if isinstance(spec, str) and D.split_spec(spec)[1] is None:  # a whole file: list what is inside
        objs = D.list_objects(spec)
        text = "\n".join([f"{spec}: {len(objs)} objects"] + [f"  {c:<14} {k}" for k, c in objs.items()]
                         + ["", f'Look inside one:  fg.inspect("{spec}:NAME")   or   figly inspect {spec}:NAME'])
        if show:
            print(text)
        return {"spec": spec, "kind": "file", "objects": objs, "text": text, "call": f'fg.plot("{spec}")'}
    name, kind, payload, texts = _resolve(spec)
    label = spec if isinstance(spec, str) else name
    if kind == "pads":  # a canvas with several panels
        rows = []
        for k, (_pn, items, tx) in enumerate(payload, 1):
            data, total, comps = _frame_info(items)
            n = int(sum(d.y.sum() for d in data))
            rows.append(f"  panel {k}: {n} entries, {len(comps)} components"
                        + (f"   [{'; '.join(tx)}]" if tx else ""))
        text = "\n".join([f"{label}: canvas with {len(payload)} panels (one figure per panel)"] + rows
                         + ["", f'Plot them all: fg.plot("{label}")   (files end in _1, _2, ...)'])
        if show:
            print(text)
        return {"spec": label, "kind": "pads", "panels": [{"items": list(i), "texts": t} for _, i, t in payload],
                "text": text, "call": f'fg.plot("{label}")'}
    out: dict = {"spec": label, "name": name}
    lines: list[str] = []
    if kind == "frame" and _is_roofit(payload):
        data, total, comps = _frame_info(payload)
        first = next(iter(payload.values()))
        xl, unit = title_label(getattr(first, "xtitle", ""))
        out.update(kind="fit", components=comps, unit=unit)
        lines.append(f"{label}: RooFit frame")
        lines.append(f"  x axis      : {xl or '(no title)'}" + (f"  [{unit}]" if unit else ""))
        if total is not None:
            lines.append(f"  x range     : {total.x.min():.6g} to {total.x.max():.6g}")
        for d in data:
            w = (d.exl + d.exh)[0] if d.has_xerr else float("nan")
            lines.append(f"  data        : {len(d.x)} points, {d.y.sum():.0f} entries, bin width {w:.4g}")
        lines.append(f"  total fit   : {'yes' if total is not None else 'no'}")
        lines.append("  components  :  name              peak   share of total")
        for c in comps:
            lines.append(f"                 {c['name']:<16} {c['peak']:>8.3g}   {100 * c['share']:>6.2f} %")
        faint = [c["name"] for c in comps if c["share"] < 0.02]
        if faint:
            lines.append(f"  note        : {', '.join(faint)} contribute under 2 %, so they are hard to see; "
                         "consider merge=, a thicker style or hide=.")
        names = [c["name"] for c in comps]
        lab = ", ".join(f'"{n}": "{n}"' for n in names)
        target = f'"{label}"' if isinstance(spec, str) else "frame  # your dict of objects"
        call = [f"fg.plot({target},", f"        labels={{{lab}}},",
                '        # colors={"' + (names[0] if names else "name") + '": "#0072B2"},',
                '        # components={"' + (names[0] if names else "name") + '": "red dashed fill"},',
                '        # merge={"Backgrounds": [' + ", ".join(f'"{n}"' for n in names[1:3]) + "]},",
                "        # hide=[], blind=(lo, hi), logy=True, stack=True, size=\"column\",",
                f'        unit="{unit or ""}")']
    else:
        objs = payload if kind == "frame" else {name: payload}
        out.update(kind="hist", objects=list(objs))
        lines.append(f"{label}: {'canvas with ' + str(len(objs)) + ' drawable objects' if kind == 'frame' else type(payload).__name__}")
        for k, o in objs.items():
            if isinstance(o, D.H1):
                lines.append(f"  {k}: histogram, {len(o.values)} bins from {o.edges[0]:.6g} to {o.edges[-1]:.6g}, "
                             f"integral {o.integral:.6g}")
            elif isinstance(o, D.H2):
                lines.append(f"  {k}: 2D histogram, {o.values.shape[0]} x {o.values.shape[1]} bins")
            else:
                lines.append(f"  {k}: graph, {len(o.x)} points")
        call = [f'fg.plot("{label}", unit="", xlim=None, logy=False)']
    text = "\n".join(call)
    out["call"] = text
    lines += ["", "Copy this, then edit only what you want:", "", text, "",
              "All options: fg.options()   Style words: red / dashed / dotted / fill / thick"]
    out["text"] = "\n".join(lines)
    if show:
        print(out["text"])
    return out


def init(spec, path="figuratively.toml", force: bool = False) -> Path:
    """Write a commented figuratively.toml with every detected component pre-filled, ready to relabel."""
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass force=True (or --force) to overwrite")
    info = inspect(spec, show=False)
    names = [c["name"] for c in info.get("components", [])]
    unit = info.get("unit") or ""
    rows = "\n".join(f'{n} = "{n}"' for n in names) or '# name = "legend text"'
    src = spec if isinstance(spec, str) else "<object>"
    path.write_text(f'''# Generated by `figly init {src}`. Edit the text on the right; delete what you do not need.
label = "Work in progress"   # text at the top left; remove this line to draw none
unit = "{unit}"
formats = ["pdf", "png"]
# com = "13"                 # adds sqrt(s) = 13 TeV
# lumi = "5.4"               # adds the luminosity
# nparams = 10               # number of fit parameters: adds chi2/ndf to fit plots

[labels]                     # legend text per component (LaTeX allowed: '$X\\\\to\\\\gamma\\\\gamma$')
{rows}

[colors]                     # optional, e.g. signal = "#0072B2"
''')
    return path

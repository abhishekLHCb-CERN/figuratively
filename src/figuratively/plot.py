"""The Plot class: build a figure from ROOT objects, customise it, save it."""
from __future__ import annotations

import fnmatch
import inspect as _inspect
import itertools
import math
import re
import warnings
from dataclasses import dataclass, field, replace
from pathlib import Path

import matplotlib.pyplot as plt
import mplhep as hep
import numpy as np
from matplotlib.colors import LogNorm, Normalize, to_rgba
from matplotlib.font_manager import FontProperties

from . import data as D
from .colors import ROOT_HATCH, ROOT_LINESTYLES, root_color, separate
from .colors import palette as _palette
from .options import did_you_mean
from .style import (
    COMP_DASHES,
    DATA_COLOR,
    DEFAULT_STYLE,
    PALETTE,
    PULL_COLOR,
    TOTAL_COLOR,
    use_style,
)

SIZES = {"column": (3.4, 2.8), "double": (7.0, 5.4), "slide": (13.3, 7.5)}
KNOWN_EXT = {".pdf", ".png", ".svg", ".eps", ".jpg", ".jpeg", ".tif", ".tiff"}
CAP = 1.75  # error-bar cap length in points; override per series with capsize=
H1_KINDS = {"step", "fill", "points", "band"}
G_KINDS = {"line", "points", "band", "fill"}


@dataclass
class Series:
    obj: object
    label: str | None
    kind: str
    color: str
    style: dict = field(default_factory=dict)
    base: object = None  # lower edge for stacked series
    in_ratio: bool = True  # False: leave this series out of the ratio panel


def _model_at(obj, x):
    """Evaluate a histogram or graph at x by linear interpolation."""
    if isinstance(obj, D.H1):
        return np.interp(x, obj.centers, obj.values)
    o = np.argsort(obj.x)
    return np.interp(x, obj.x[o], obj.y[o])


def _search(pattern: str, text: str):
    try:
        return re.search(pattern, text)
    except re.error as e:
        raise ValueError(f"hide: '{pattern}' is not a valid regular expression ({e})") from None


def model_average(obj, lo, hi, n=40):
    """The model averaged over each bin [lo, hi] (what RooFit's pullHist uses), not just at the centre."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    t = (np.arange(n) + 0.5) / n
    xs = lo[:, None] + (hi - lo)[:, None] * t[None, :]
    x, y = _xy(obj)
    o = np.argsort(x)
    return np.interp(xs, x[o], y[o]).mean(axis=1)


def _sum_curves(curves, name):
    """Sum RooFit curves on a common grid (for merging components into one legend entry)."""
    curves = [c.trimmed() for c in curves]
    x = np.unique(np.concatenate([c.x for c in curves]))
    y = sum(_model_at(c, x) for c in curves)
    z = np.zeros_like(x)
    return D.G(x, y, z, z, z, z, name, classname="RooCurve")


def _xy(obj):
    return (obj.centers, obj.values) if isinstance(obj, D.H1) else (obj.x, obj.y)


class Plot:
    """Chainable plot builder.

    >>> p = Plot().add("f.root:h_data", "Data", kind="points").add("f.root:h_mc", "MC")
    >>> p.xlabel("$m(K^+K^-)$", unit="MeV/$c^2$").label("Thesis").ratio().save("out.pdf")
    """

    def __init__(self, style: str | None = DEFAULT_STYLE, **rc):
        self._style, self._rc = style, rc
        self.series: list[Series] = []
        self._cycle = itertools.cycle(PALETTE)
        self._roles: dict = {}
        self._leg_order: list | None = None
        self._fscale = 1.0
        self._eff_rc: dict | None = None
        self._sscale = 1.0  # font scale implied by a size preset
        self._blind: list = []
        self._target = None  # a SubFigure when this plot is one panel of a combined figure
        self._pal_name = "figuratively"
        self._lscale = 1.0  # line/marker scale implied by a size preset
        self._top_labels: list = []
        self._o = dict(xlabel=None, ylabel=None, unit=None, prefix="Candidates", xlim=None,
                       ylim=None, logx=False, logy=False, headroom=None, legend={}, label=None,
                       grid=None, minor=True, size=None, title=None, cmap=None, zlog=False,
                       zlim=None, zlabel=None, panel=None, panel_opts={}, hratio=3.2, info=[], layout="topright")
        self._extras: list = []
        self.fig = self.ax = self.rax = None
        self._dirty = True

    # ------------------------------------------------------------- adding data
    def add(self, obj, label=None, kind=None, color=None, *, scale=None, normalise=False,
            density=False, rebin=None, xrange=None, in_ratio=True, **style) -> Plot:
        """Add 'file.root:name' (or an H1/H2/G).

        kind: H1 -> step | fill | points | band ; graph -> line | points | band.
        scale/normalise/density/rebin/xrange act on the data; remaining keywords
        (marker, markersize, linestyle, linewidth, alpha, hatch, zorder, xerr, ...) style it.
        """
        o = D.load(obj)
        if isinstance(o, D.H1):
            o = o.cropped(*xrange) if xrange else o
            o = o.rebinned(rebin) if rebin else o
            o = o.scaled(scale) if scale else o
            o = o.normalised_to(1.0, density) if (normalise or density) else o
            kind = kind or "step"
            if kind not in H1_KINDS:
                raise ValueError(f"histogram kind must be one of {sorted(H1_KINDS)}")
        elif isinstance(o, D.G):
            o = o.cropped(*xrange) if xrange else o
            o = o.scaled(scale) if scale else o
            kind = kind or ("line" if o.classname == "RooCurve" else "points")
            if kind not in G_KINDS:
                raise ValueError(f"graph kind must be one of {sorted(G_KINDS)}")
        else:
            kind = "colormap"
            o = o.scaled(scale) if scale else o
        new = Series(o, label, kind, color or next(self._cycle), style, in_ratio=in_ratio)
        for lo, hi, _lab, curves in self._blind:
            new.obj, new.base = self._blind_series(new, lo, hi, curves)
        self.series.append(new)
        self._dirty = True
        return self

    def add_function(self, func, xrange, label=None, color=None, n=500, **style) -> Plot:
        """Overlay a python callable f(x) (e.g. a fitted PDF) as a curve."""
        x = np.linspace(*xrange, n)
        z = np.zeros_like(x)
        g = D.G(x, np.asarray(func(x), float), z, z, z, z, "func")
        return self.add(g, label, "line", color, **style)

    def add_all(self, spec, include=None, **kw) -> Plot:
        """Add every drawable object of a canvas/RooPlot ('file.root:canvas')."""
        import re
        for name, obj in D.load_all(spec).items():
            if include is None or re.search(include, name):
                self.add(obj, label=name, **kw)
        return self

    def add_stack(self, items: dict, colors=None, alpha=0.9, styles=None, **style) -> Plot:
        """Stack many components bottom to top: {label: obj}. Colours default to COMP_PALETTE.

        Histograms must share binning. Curves/graphs are interpolated on a common grid.
        """
        objs = {k: D.load(v) for k, v in items.items()}
        colors, styles = colors or {}, styles or {}
        first = next(iter(objs.values()))
        pal = iter(_palette(self._pal_name, max(len(objs), 1)))
        if all(isinstance(o, D.H1) for o in objs.values()):
            if any(not np.array_equal(o.edges, first.edges) for o in objs.values()):
                raise ValueError("stacked histograms need identical binning")
            cum = np.zeros_like(first.values)
            for lab, o in objs.items():
                base, cum = cum, cum + o.values
                self.series.append(Series(replace(o, values=cum.copy()), lab, "stack",
                                          colors.get(lab) or next(pal),
                                          {**dict(alpha=alpha, **style), **styles.get(lab, {})}, base=base))
        elif all(isinstance(o, D.G) for o in objs.values()):
            xs = np.unique(np.concatenate([o.trimmed().x for o in objs.values()]))
            cum = np.zeros_like(xs)
            z = np.zeros_like(xs)
            for lab, o in objs.items():
                base, cum = cum, cum + _model_at(o.trimmed(), xs)
                self.series.append(Series(D.G(xs, cum.copy(), z, z, z, z, lab, classname="stack"),
                                          lab, "stack", colors.get(lab) or next(pal),
                                          {**dict(alpha=alpha, **style), **styles.get(lab, {})}, base=base))
        else:
            raise TypeError("stack items must be all histograms or all graphs/curves")
        self._dirty = True
        return self

    def add_roofit(self, spec, labels=None, colors=None, styles=None, hide=None,
                   data_label="Data", total_label="Total fit", comp_kind="line",
                   stack=False, order=None, merge=None, root_colors=True) -> Plot:
        """Add a whole RooFit frame (canvas/RooPlot) with any number of components.

        RooHist -> data points; RooCurve without Comp[] -> total fit; RooCurve with
        Comp[a,b] -> one component named 'a+b'.  Each component gets its own colour and dash.

        labels : {component: legend text}     colors : {component: colour}
        styles : {component: dict(kind=, color=, linestyle=, linewidth=, alpha=, label=)}
        hide   : regexes of ROOT names (or component names) to skip
        root_colors : True takes the colours, line styles and fills stored in the ROOT objects (components and
                      total), translated into refined colours (colors.root_color) and kept visibly apart
                      (colors.separate); "components" leaves the total in the house colour; False ignores ROOT
        comp_kind : 'line' (default), 'fill' or 'band' for every component
        stack  : stack the components (fills) instead of overlaying them
        order  : component names in legend/stack order (default: file order)
        """
        objs = spec if isinstance(spec, dict) else D.load_all(spec)
        labels, colors, styles = labels or {}, colors or {}, styles or {}
        data, totals, comps = [], [], {}
        for name, o in objs.items():
            if not isinstance(o, D.G):
                continue
            info = D.parse_roofit_name(name)
            cname = "+".join(info["components"])
            if re.match(r"(pull|resid)_", name) or (
                    hide and any(_search(h, name) or _search(h, cname) for h in hide)):
                continue  # pulls are recomputed from data and total
            if o.classname == "RooHist":
                data.append(o)
            elif o.classname == "RooCurve":
                (comps.setdefault(cname, o) if cname else totals.append(o))
        taken: set = set()
        original = list(comps)
        for label, members in (merge or {}).items():  # sum several components into one entry
            members = [members] if isinstance(members, str) else list(members)
            sel = [n for n in comps if any(fnmatch.fnmatch(n, m) for m in members) and n not in taken]
            clash = [n for n in original if any(fnmatch.fnmatch(n, m) for m in members) and n in taken]
            if clash:
                warnings.warn(f"merge: {', '.join(clash)} already belong to an earlier group; "
                              f"'{label}' does not include them", stacklevel=3)
            taken.update(sel)
            if not sel:
                continue
            at = list(comps).index(sel[0])
            merged = _sum_curves([comps[n] for n in sel], label)
            rest = [(k, v) for k, v in comps.items() if k not in sel]
            rest.insert(min(at, len(rest)), (label, merged))
            comps = dict(rest)
        if hide:  # a merged entry can be hidden by its new name as well
            comps = {k: v for k, v in comps.items() if not any(_search(h, k) for h in hide)}
        names = [n for n in (order or []) if n in comps] + [n for n in comps if n not in (order or [])]
        pal = iter(_palette(self._pal_name, len(names) + 2))
        tcol = TOTAL_COLOR
        if totals and root_colors in (True, "all"):
            tcol = root_color((getattr(totals[0], "root", None) or {}).get("line_color")) or TOTAL_COLOR
        used = {str(c).lower() for c in colors.values()} | {tcol.lower(), "#000000"}
        cols, root_styles = {}, {}
        for n in names:
            explicit = colors.get(n) or styles.get(n, {}).get("color")
            if explicit:
                cols[n] = explicit
                used.add(str(explicit).lower())
                continue
            cand = None
            if root_colors:
                r = getattr(comps[n], "root", None) or {}
                fs = r.get("fill_style")
                solid = fs == 1001 or fs in ROOT_HATCH
                cand = root_color(r.get("fill_color") if (solid and r.get("fill_color")) else r.get("line_color"))
                if cand and cand.lower() not in used:
                    cand = separate(cand, used)  # keep visibly apart from the colours already taken
                    rs = {}
                    if solid and r.get("fill_color"):
                        rs["kind"] = "fill"
                        if fs in ROOT_HATCH:
                            rs["hatch"] = ROOT_HATCH[fs]
                    ls = ROOT_LINESTYLES.get(r.get("line_style") or 1)
                    if ls and ls != "-":
                        rs["linestyle"] = ls
                    root_styles[n] = rs
                else:
                    cand = None
            if cand is None:
                cand = separate(next(c for c in pal if c.lower() not in used), used)
            cols[n] = cand
            used.add(cand.lower())

        def pretty(n):
            return styles.get(n, {}).get("label") or labels.get(n) or n

        idx = {}
        if stack:
            self.add_stack({pretty(n): comps[n] for n in names},
                           colors={pretty(n): cols[n] for n in names},
                           styles={pretty(n): {k: v for k, v in {**root_styles.get(n, {}), **styles.get(n, {})}.items()
                                               if k in ("hatch", "alpha")} for n in names})
        else:
            for i, n in enumerate(names):
                st = {**root_styles.get(n, {}), **styles.get(n, {})}
                st.pop("label", None)
                st.pop("color", None)
                kind = st.pop("kind", comp_kind)
                if kind == "line":
                    st.setdefault("linestyle", COMP_DASHES[i % len(COMP_DASHES)])
                    st.setdefault("linewidth", 2.0)
                self.add(comps[n], pretty(n), kind, cols[n], **st)
        for o in totals[:1]:
            self.add(o, total_label, "line", tcol, linewidth=2.6, zorder=4)
            idx["total"] = len(self.series) - 1
        for i, o in enumerate(data):
            lab = data_label if i == 0 else None
            self.add(o, lab, "points", DATA_COLOR, zorder=5)
            idx.setdefault("data", len(self.series) - 1)
        self._roles.update(idx)
        labs = [data_label if data else None, total_label if totals else None] + [pretty(n) for n in names]
        self._leg_order = [x for x in labs if x]
        self._dirty = True
        return self

    def info(self, *lines: str, replace=False) -> Plot:
        """Small text lines in the top-right block (mathtext allowed), below the experiment label."""
        self._o["info"] = list(lines) if replace else self._o["info"] + list(lines)
        self._dirty = True
        return self

    def param(self, name: str, value: float, err: float | None = None, unit: str = "",
              fmt: str = ".1f") -> Plot:
        """Add a fitted value line, e.g. param('$m$', 1865.2, 0.1, 'MeV/$c^2$')."""
        txt = f"{name} = {value:{fmt}}" + (rf" $\pm$ {err:{fmt}}" if err is not None else "")
        return self.info(txt + (f" {unit}" if unit else ""))

    def layout(self, kind: str = "topright") -> Plot:
        """'topright' (default): label, info and legend in one small column inside the axes.
        'classic': mplhep label above the axes, legend inside."""
        self._o["layout"] = kind
        self._dirty = True
        return self

    def rename(self, names) -> Plot:
        """Rename legend entries on an existing plot: p.rename({"signal": "Signal"}), or a list that names
        the entries in legend order: p.rename(["Data", "Fit", "Signal"])."""
        shown = [s.label for s in self.series if s.label]
        order = [x for x in (self._leg_order or shown) if x in shown] + [x for x in shown if x not in (self._leg_order or [])]
        if isinstance(names, (list, tuple)):
            if len(names) > len(order):
                raise ValueError(f"rename: {len(names)} names for {len(order)} legend entries ({', '.join(order)})")
            names = dict(zip(order, names))
        for old in names:
            if old not in shown:
                raise KeyError(f"rename: no legend entry '{old}'{did_you_mean(old, shown)} (entries: {', '.join(shown)})")
        for s in self.series:
            if s.label in names:
                s.label = names[s.label]
        self._leg_order = [names.get(x, x) for x in (self._leg_order or [])] or None
        self._dirty = True
        return self

    def font(self, scale: float) -> Plot:
        """Scale every text size (labels, ticks, legend) by `scale`."""
        self._fscale = scale
        self._eff_rc = None
        self._dirty = True
        return self

    # ------------------------------------------------------------- panels
    def ratio(self, ref=None, ylim=None, ylabel="Ratio", band=True, zoom=False) -> Plot:
        """Bottom panel: every series divided by series number `ref`. ylim=None chooses 0.5-1.5, widened
        when many points fall outside; ylim=(lo, hi) fixes it."""
        return self._panel("ratio", ref=ref, ylim=ylim, ylabel=ylabel, band=band, zoom=zoom)

    def pull(self, data=None, model=None, ylim=None, ylabel="Pull", color=None, chi2=False,
             nparams=0, mode="roofit") -> Plot:
        """Bottom panel: (data - model)/sigma_data per point, with 0 and +-3 guides.

        data/model default to the series added by add_roofit (else series 0 and 1).
        mode="roofit" averages the model over each bin like RooFit does; "centre" uses the bin centre.
        ylim=None grows beyond +-5 when the pulls are larger, so large pulls never become solid blocks.
        chi2=True prints chi2/ndf (ndf = bins - nparams) in the panel.
        """
        if mode not in ("roofit", "centre"):
            raise ValueError(f"pull mode must be 'roofit' or 'centre', got {mode!r}")
        return self._panel("pull", data=data, model=model, ylim=ylim, ylabel=ylabel, color=color,
                           chi2=chi2, nparams=nparams, mode=mode)

    def no_panel(self) -> Plot:
        return self._panel(None)

    def _panel(self, kind, **opts):
        self._o["panel"], self._o["panel_opts"] = kind, opts
        self._dirty = True
        return self

    # ------------------------------------------------------------- customisation
    def _set(self, **kw):
        self._o.update(kw)
        self._dirty = True
        return self

    def xlabel(self, text, unit=None):
        return self._set(xlabel=text, **({"unit": unit} if unit is not None else {}))

    def ylabel(self, text=None, prefix=None):
        """Explicit label, or just change the auto-label prefix (default 'Candidates')."""
        return self._set(**({"ylabel": text} if text else {}), **({"prefix": prefix} if prefix else {}))

    def unit(self, unit): return self._set(unit=unit)
    def title(self, text): return self._set(title=text)
    def xlim(self, lo, hi): return self._set(xlim=(lo, hi))
    def ylim(self, lo, hi): return self._set(ylim=(lo, hi))
    def logx(self, on=True): return self._set(logx=on)
    def logy(self, on=True): return self._set(logy=on)
    def headroom(self, factor): return self._set(headroom=factor)
    def size(self, width, height=None):
        """size(w, h) in inches, size(w) (height = 0.75 w) or a preset: 'column' (3.4 in), 'double' (7 in),
        'slide' (13.3 in). Presets also scale text, lines and markers to suit that width."""
        preset = False
        if isinstance(width, str):
            if width not in SIZES:
                raise ValueError(f"unknown size preset '{width}'{did_you_mean(width, SIZES)} (presets: {', '.join(SIZES)})")
            width, height = SIZES[width]
            preset = True
        elif isinstance(width, (tuple, list)):
            if len(width) != 2:
                raise ValueError(f"size expects (width, height) in inches, got {tuple(width)!r}")
            width, height = width
        if width is None:
            raise ValueError("size: the width must be a number of inches")
        height = 0.75 * float(width) if height is None else float(height)
        self._sscale = max(min(float(width) / 11.0, 1.3), 0.3)  # text follows the figure width
        self._lscale = max(min(self._sscale, 1.3), 0.45)
        self._eff_rc = None
        return self._set(size=(float(width), height))

    def grid(self, on=True, **kw): return self._set(grid=(on, kw))
    def minor_ticks(self, on=True): return self._set(minor=on)
    def rc(self, **kw): self._rc.update(kw); self._eff_rc = None; self._dirty = True; return self

    def legend(self, show=True, loc="upper right", ncol="auto", title=None, order=None, **kw):
        """legend("lower left"), legend(False), or legend(loc=, ncol=, title=, order=).

        ncol='auto' scales columns and font with the number of entries.

        loc: any matplotlib location, or 'outside' / 'outside right' to put a long legend
        beside the axes. order: list of label strings or indices.
        """
        if isinstance(show, str):
            show, loc = True, show
        from matplotlib.legend import Legend

        allowed = set(_inspect.signature(Legend.__init__).parameters) | {"order", "show"}
        bad = [k for k in kw if k not in allowed]
        if bad:
            raise ValueError(f"legend: unknown option '{bad[0]}'{did_you_mean(bad[0], allowed)} "
                             "(use loc, ncol, title, order, fontsize, frameon, ...)")
        return self._set(legend=dict(show=show, loc=loc, ncol=ncol, title=title, order=order, **kw))

    def label(self, text="Work in progress", exp="", data=True, loc=0, lumi=None, com=None, **kw):
        """Label text top left. exp="" (default) claims no collaboration; pass exp="LHCb" yourself if you
        are entitled to. data=False adds 'Simulation'. text=None removes the label."""
        if text is not None and not data and text.strip().lower() == "simulation":
            text = ""  # mplhep already prints 'Simulation' when data=False
        if com in (None, ""):  # no collision-energy text unless asked for, e.g. com="13"
            kw.setdefault("rlabel", "")
            com = None
        return self._set(label=None if text is None else dict(
            exp=exp, text=text, data=data, loc=loc, lumi=lumi, com=com, **kw))

    def zaxis(self, cmap=None, log=False, lim=None, label=None):
        """2D histograms: colour map, log colour scale, (zmin, zmax), colour-bar label."""
        return self._set(cmap=cmap, zlog=log, zlim=lim, zlabel=label)

    def text(self, x, y, s, coords="axes", **kw):
        """coords='axes' (0-1 fractions) or 'data'."""
        def f(ax, _):
            ax.text(x, y, s, transform=ax.transAxes if coords == "axes" else ax.transData, **kw)
        return self._extra(f)

    def palette(self, name: str) -> Plot:
        """Colour palette for components and series: figuratively, r4, okabe-ito, tableau10, dark2 or hcl.
        Palettes are extended with evenly spaced HCL hues, so many components never repeat a colour."""
        _palette(name)  # validates the name
        self._pal_name = name
        self._dirty = True
        return self

    def _small(self):
        return FontProperties(size=plt.rcParams["legend.fontsize"]).get_size_in_points() * 0.8

    def _top_label(self, ax, x, text):
        """Label just above the axes at data position x; neighbours that would overlap are stacked."""
        xf = float(ax.transLimits.transform((x, 0))[0])
        level = 0
        while any(abs(xf - o) < 0.14 and lv == level for o, lv in self._top_labels):
            level += 1
        self._top_labels.append((xf, level))
        ax.text(xf, 1.012 + 0.065 * level, text, transform=ax.transAxes, ha="center", va="bottom",
                fontsize=self._small(), color="0.25", clip_on=False)

    def vline(self, x, text=None, **kw):
        """Dashed vertical line at x, with an optional small label above the axes."""
        def f(ax, _):
            ax.axvline(x, **{"color": "0.4", "ls": "--", "lw": 1, **kw})
            if text:
                self._top_label(ax, x, text)
        return self._extra(f)

    def hline(self, y, text=None, **kw):
        """Dashed horizontal line at y, with an optional small label at the right."""
        def f(ax, _):
            ax.axhline(y, **{"color": "0.4", "ls": "--", "lw": 1, **kw})
            if text:
                ax.text(0.99, y, text, transform=ax.get_yaxis_transform(), ha="right", va="bottom",
                        fontsize=self._small(), color="0.3")
        return self._extra(f)

    def span(self, x0, x1, text=None, **kw):
        """Shaded x window (signal region, sidebands) with an optional label above the axes."""
        def f(ax, _):
            ax.axvspan(x0, x1, **{"color": "0.8", "alpha": 0.4, "lw": 0, **kw})
            if text:
                self._top_label(ax, 0.5 * (x0 + x1), text)
        return self._extra(f)

    def blind(self, lo, hi=None, label="Blinded", curves=False):
        """Blind a window: data points (and their pulls) inside [lo, hi] are removed and a hatched
        band marks the window. curves=True also blanks the model curves there. blind((lo, hi)) works too."""
        if hi is None:
            try:
                lo, hi = lo
            except (TypeError, ValueError):
                raise TypeError("blind expects (lo, hi), or a list of (lo, hi) pairs") from None
        lo, hi = float(lo), float(hi)
        if hi < lo:
            lo, hi = hi, lo
        self._blind.append((lo, hi, label, bool(curves)))
        for s in self.series:
            s.obj, s.base = self._blind_series(s, lo, hi, curves)
        self._dirty = True
        return self

    @staticmethod
    def _blind_series(s, lo, hi, curves):
        if s.kind == "points":
            return D.mask_window(s.obj, lo, hi), s.base
        if not curves:
            return s.obj, s.base
        base = s.base
        if isinstance(base, np.ndarray) and isinstance(s.obj, D.G):
            base = np.where((s.obj.x >= lo) & (s.obj.x <= hi), np.nan, base)
        elif isinstance(base, np.ndarray) and isinstance(s.obj, D.H1):
            base = np.where((s.obj.centers >= lo) & (s.obj.centers <= hi), np.nan, base)
        return D.blank_window(s.obj, lo, hi), base

    def _draw_blind(self):
        for lo, hi, label, _curves in self._blind:
            for a in (self.ax, self.rax):
                if a is not None:
                    a.axvspan(lo, hi, facecolor="#EFEFEF", edgecolor="#9A9A9A", hatch="////", lw=0,
                              zorder=0.5, label="_blind")
            if label:
                x0, x1 = self.ax.get_xlim()
                narrow = (hi - lo) / abs(x1 - x0) < 0.12
                self.ax.text(0.5 * (lo + hi), 0.5, label, transform=self.ax.get_xaxis_transform(),
                             rotation=90 if narrow else 0, ha="center", va="center", style="italic",
                             fontsize=self._small() * 1.1, color="#555555",
                             bbox=dict(fc="#EFEFEF", ec="none", alpha=0.92, pad=1.5), zorder=8)

    def annotate(self, func):
        """Escape hatch: func(ax, rax) runs after drawing, e.g. for arrows."""
        return self._extra(func)

    def _extra(self, f):
        self._extras.append(f)
        self._dirty = True
        return self

    def _legend_plan(self):
        """(n entries, ncol, font shrink, outside?) so many components stay readable."""
        leg = self._o["legend"]
        n = sum(1 for x in self.series if x.label)
        ncol = leg.get("ncol", "auto")
        if ncol in (None, "auto"):
            ncol = 1 if n <= 5 else 2 if n <= 12 else 3
        shrink = 1.0 if n <= 5 else 0.85 if n <= 9 else 0.75 if n <= 14 else 0.65
        return n, ncol, shrink, str(leg.get("loc", "")).startswith("outside")

    # ------------------------------------------------------------- rendering
    def render(self):
        if self._target is not None:
            self._target.clf()
        elif self.fig is not None:
            plt.close(self.fig)
        if not self.series:
            raise ValueError("nothing to plot: add() something first (or every object was hidden or empty)")
        self._top_labels = []
        with self._rc_context():
            if any(s.kind == "colormap" for s in self.series):
                self._render2d()
            else:
                self._render1d()
            self._finish()
        self._dirty = False
        return self.fig

    def _rc_context(self):
        """Style as a matplotlib rc_context: the user's global rcParams are left untouched."""
        if self._eff_rc is None:
            with plt.rc_context():
                before = dict(plt.rcParams)
                use_style(self._style, font_scale=self._fscale * self._sscale, **self._rc)
                self._eff_rc = {k: v for k, v in plt.rcParams.items() if before.get(k) != v}
        return plt.rc_context(self._eff_rc)

    def _figure(self, two):
        o = self._o
        if self._target is not None:
            fig = self._target
            if two:
                ax, rax = fig.subplots(2, 1, sharex=True, gridspec_kw=dict(height_ratios=[o["hratio"], 1], hspace=0.07))
                return fig, ax, rax
            return fig, fig.subplots(), None
        w, h = plt.rcParams["figure.figsize"]
        kw = {"figsize": o["size"] or ((w, h * 1.12) if two else (w, h))}
        if two:
            fig, (ax, rax) = plt.subplots(2, 1, sharex=True, gridspec_kw=dict(
                height_ratios=[o["hratio"], 1], hspace=0.07), **kw)
            return fig, ax, rax
        fig, ax = plt.subplots(**kw)
        return fig, ax, None

    def _render1d(self):
        o = self._o
        self.fig, self.ax, self.rax = self._figure(o["panel"] is not None)
        ax = self.ax
        for s in self.series:
            self._draw(ax, s)
        self._axes_1d(ax)
        if o["panel"] == "ratio":
            self._ratio(self.rax)
        elif o["panel"] == "pull":
            self._pull(self.rax)
        if self.rax is not None:
            ax.tick_params(labelbottom=False)
            ax.set_xlabel("")
            self.rax.set_xlabel(self._xlabel_text())

    def _draw(self, ax, s):
        st, c, o = dict(s.style), s.color, s.obj
        lab = s.label
        if isinstance(o, D.G):
            o = o.trimmed()
        alpha, lw, ls = st.pop("alpha", None), st.pop("linewidth", None), st.pop("linestyle", None)
        z = st.pop("zorder", None)
        hatch = st.pop("hatch", None)
        L = self._lscale
        lw = (lw if lw is not None else 1.6) * L
        if s.kind == "stack":
            fc, ec = to_rgba(c, alpha if alpha is not None else 0.9), st.pop("edgecolor", "white")
            if isinstance(o, D.H1):
                ax.stairs(o.values, o.edges, baseline=s.base, fill=True, facecolor=fc,
                          edgecolor=ec, lw=0.8, label=lab, zorder=z or 1, hatch=hatch)
            else:
                ax.fill_between(o.x, s.base, o.y, facecolor=fc, edgecolor=ec, lw=0.8, label=lab,
                                zorder=z or 1, hatch=hatch)
        elif isinstance(o, D.H1):
            if s.kind == "step":
                ax.stairs(o.values, o.edges, color=c, label=lab, lw=lw, ls=ls or "-",
                          alpha=alpha, zorder=z or 2, **st)
            elif s.kind == "fill":
                ax.stairs(o.values, o.edges, fill=True, facecolor=to_rgba(c, alpha or 0.5),
                          edgecolor=c, lw=lw, ls=ls or "-", label=lab, zorder=z or 1, hatch=hatch, **st)
            elif s.kind == "band":
                ax.stairs(o.values + o.errors, o.edges, baseline=o.values - o.errors, fill=True,
                          facecolor=to_rgba(c, alpha or 0.3), edgecolor="none", zorder=1)
                ax.stairs(o.values, o.edges, color=c, label=lab, lw=lw, zorder=z or 2)
            else:
                xerr = st.pop("xerr", False)
                ax.errorbar(o.centers, o.values, yerr=o.errors, xerr=o.widths / 2 if xerr else None,
                            fmt=st.pop("marker", "o"), ms=st.pop("markersize", 5) * L, color=c,
                            capsize=st.pop("capsize", CAP) * L, elinewidth=1.5 * L, capthick=1.5 * L, label=lab, zorder=z or 3, alpha=alpha,
                            **st)
        else:
            if s.kind == "line":
                ax.plot(o.x, o.y, color=c, label=lab, lw=lw, ls=ls or "-", alpha=alpha,
                        zorder=z or 2, **st)
            elif s.kind == "fill":
                ax.fill_between(o.x, o.y, facecolor=to_rgba(c, alpha or 0.35), edgecolor=c, lw=lw,
                                linestyle=ls or "-", label=lab, zorder=z or 1, hatch=hatch)
            elif s.kind == "band":
                ax.fill_between(o.x, o.y - o.eyl, o.y + o.eyh, facecolor=to_rgba(c, alpha or 0.3),
                                edgecolor="none", zorder=1)
                ax.plot(o.x, o.y, color=c, label=lab, lw=lw, zorder=z or 2)
            else:
                xerr = [o.exl, o.exh] if (o.has_xerr and st.pop("xerr", True)) else None
                yerr = [o.eyl, o.eyh] if o.has_yerr else None
                ax.errorbar(o.x, o.y, yerr=yerr, xerr=xerr, fmt=st.pop("marker", "o"),
                            ms=st.pop("markersize", 5) * L, color=c, capsize=st.pop("capsize", CAP) * L, elinewidth=1.5 * L, capthick=1.5 * L,
                            label=lab, zorder=z or 3, alpha=alpha, **st)

    # axis labels ---------------------------------------------------------
    def _first(self):
        return self.series[0].obj

    def _xlabel_text(self):
        o = self._o
        text = o["xlabel"] if o["xlabel"] is not None else getattr(self._first(), "xtitle", "")
        return f"{text} [{o['unit']}]" if (o["unit"] and text) else text

    def _ylabel_text(self):
        o = self._o
        if o["ylabel"]:
            return o["ylabel"]
        h = next((s.obj for s in self.series if isinstance(s.obj, D.H1)), None)
        if h is None:  # RooHist data: infer the bin width from its x error bars
            g = next((s.obj for s in self.series if isinstance(s.obj, D.G) and s.obj.has_xerr), None)
            if g is None:
                return getattr(self._first(), "ytitle", "")
            w = g.exl + g.exh
            if not np.allclose(w, w[0], rtol=1e-3):
                return o["prefix"]
            ws = f"{w[0]:.3g}"
            return f"{o['prefix']} / ({ws} {o['unit']})" if o["unit"] else f"{o['prefix']} / {ws}"
        prefix = "Fraction of candidates" if h.normalised and o["prefix"] == "Candidates" else o["prefix"]
        if not h.uniform:
            return prefix
        w = f"{h.widths[0]:.3g}"
        return f"{prefix} / ({w} {o['unit']})" if o["unit"] else f"{prefix} / {w}"

    def _axes_1d(self, ax):
        o = self._o
        ax.set_ylabel(self._ylabel_text())
        ax.set_xlabel(self._xlabel_text())
        xs = [x for x in (_xy(s.obj.trimmed() if isinstance(s.obj, D.G) else s.obj)[0] for s in self.series)
              if len(x)]
        lo = min((float(np.min(x)) for x in xs), default=0.0)
        hi = max((float(np.max(x)) for x in xs), default=1.0)
        for s in self.series:
            if isinstance(s.obj, D.H1):
                lo, hi = min(lo, s.obj.edges[0]), max(hi, s.obj.edges[-1])
        ax.set_xlim(*(o["xlim"] or (lo, hi)))
        if o["logx"]:
            ax.set_xscale("log")

        def values(s):
            x, y = _xy(s.obj)
            err = s.obj.errors if isinstance(s.obj, D.H1) else s.obj.eyh
            return y, err

        live = [s for s in self.series if len(values(s)[0]) and np.isfinite(values(s)[0]).any()]
        top = max((float(np.nanmax(values(s)[0] + values(s)[1])) for s in live), default=1.0)
        # log floor from the data and the histograms, never from the tiny tails of component curves
        ref = [s for s in live if s.kind == "points" or (isinstance(s.obj, D.H1) and s.kind in ("step", "fill", "band"))]
        ref = ref or live[:1]
        pos = [float(np.nanmin(values(s)[0][values(s)[0] > 0])) for s in ref if np.any(values(s)[0] > 0)]
        if o["logy"]:
            ax.set_yscale("log")
            from matplotlib.ticker import LogFormatterSciNotation, NullFormatter
            ax.yaxis.set_major_formatter(LogFormatterSciNotation())
            ax.yaxis.set_minor_formatter(NullFormatter())
            ymin = max(min(pos) / 3, top * 1e-6) if pos else 1e-1
            ax.set_ylim(*(o["ylim"] or (ymin, top * (o["headroom"] or self._auto_head(True)))))
        else:
            floor = min((float(np.nanmin(values(s)[0])) for s in live), default=0.0)
            ax.set_ylim(*(o["ylim"] or (min(0.0, floor * 1.2),
                                        top * (o["headroom"] or self._auto_head(False)))))

    def _auto_head(self, log):
        """Room above the data for the legend: grows with the number of rows."""
        if self._o["layout"] == "topright":
            return 3.0 if log else 1.1  # refined in _fit_block once the text column is measured
        n, ncol, _, outside = self._legend_plan()
        rows = 0 if (outside or not self._o["legend"].get("show", True)) else math.ceil(n / ncol)
        return 10 ** (0.45 + 0.22 * rows) if log else 1.12 + 0.085 * rows

    # ratio / pull ----------------------------------------------------------
    def _ratio(self, rax):
        po = self._o["panel_opts"]
        iref = po["ref"] if po["ref"] is not None else self._roles.get("total", 0)
        ref = self.series[iref].obj
        ref = ref.trimmed() if isinstance(ref, D.G) else ref
        rx, rv = _xy(ref)
        rerr = ref.errors if isinstance(ref, D.H1) else None
        if po["band"] and rerr is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                rel = rerr / rv
            rax.stairs(1 + rel, ref.edges, baseline=1 - rel, fill=True, facecolor="0.85",
                       edgecolor="none", zorder=0)
        rax.axhline(1, color="0.4", lw=1, zorder=1)
        seen_lo, seen_hi = [], []
        for i, s in enumerate(self.series):
            if i == iref or s.kind in ("stack", "fill") or not s.in_ratio:
                continue
            x, v = _xy(s.obj.trimmed() if isinstance(s.obj, D.G) else s.obj)
            with np.errstate(divide="ignore", invalid="ignore"):
                r_at = _model_at(ref, x)
                r = v / r_at
                if isinstance(s.obj, D.H1):
                    re_at = np.interp(x, rx, rerr) if rerr is not None else 0
                    err = np.sqrt((s.obj.errors / r_at) ** 2 + (v * re_at / r_at**2) ** 2)
                    noisy = ~(err < 1.0)  # a point with an error above 100 % says nothing
                    r, err = np.where(noisy, np.nan, r), np.where(noisy, np.nan, err)
                    seen_lo.append(r - err)
                    seen_hi.append(r + err)
                    rax.errorbar(x, r, yerr=err, fmt="o", ms=4, color=s.color, capsize=CAP, elinewidth=1.3, capthick=1.3, zorder=3)
                elif s.kind == "line":
                    seen_lo.append(r)
                    seen_hi.append(r)
                    rax.plot(x, r, color=s.color, lw=1.6 * self._lscale, ls=s.style.get("linestyle", "-"))
                else:
                    rax.errorbar(x, r, yerr=[s.obj.eyl / r_at, s.obj.eyh / r_at], fmt="o", ms=4,
                                 color=s.color, capsize=CAP, elinewidth=1.3, capthick=1.3, zorder=3)
        lim = po["ylim"]
        if lim is None and po.get("zoom"):  # comparing fits: zoom in on how much they differ
            allr = np.concatenate(seen_lo) if seen_lo else np.array([])
            allr = allr[np.isfinite(allr) & (allr > 0)]
            if allr.size:
                m = min(0.5, max(0.02, 1.3 * float(np.max(np.abs(allr - 1)))))
                lim = (1 - m, 1 + m)
        if lim is None:  # widen the default range when many points would fall outside it
            lim = (0.5, 1.5)
            lo = np.concatenate(seen_lo) if seen_lo else np.array([])
            hi = np.concatenate(seen_hi) if seen_hi else np.array([])
            if np.isfinite(lo).sum() > 3:
                lim = (min(0.5, max(0.0, float(np.nanpercentile(lo[np.isfinite(lo)], 5)))),
                       max(1.5, min(3.0, float(np.nanpercentile(hi[np.isfinite(hi)], 95)))))
        rax.set_ylim(*lim)
        rax.set_ylabel(po["ylabel"])

    def _pull(self, rax):
        po = self._o["panel_opts"]
        self._chi2_text = None
        try:
            d = self.series[po["data"] if po["data"] is not None else self._roles.get("data", 0)]
            m = self.series[po["model"] if po["model"] is not None else self._roles.get("total", 1)]
        except IndexError:
            warnings.warn("pull panel skipped: it needs the data and the total curve", stacklevel=3)
            rax.set_ylabel("Pull")
            return
        x, y = _xy(d.obj)
        if po.get("mode", "roofit") == "roofit":
            lo, hi = ((d.obj.edges[:-1], d.obj.edges[1:]) if isinstance(d.obj, D.H1) else
                      ((d.obj.x - d.obj.exl, d.obj.x + d.obj.exh) if d.obj.has_xerr else (x, x)))
            mod = model_average(m.obj, lo, hi) if np.any(hi > lo) else _model_at(m.obj, x)
        else:
            mod = _model_at(m.obj, x)
        if isinstance(d.obj, D.H1):
            err, wid = d.obj.errors, d.obj.widths
        else:
            err = np.where(y > mod, d.obj.eyl, d.obj.eyh)  # RooFit convention
            wid = (d.obj.exl + d.obj.exh) if d.obj.has_xerr else np.full(
                len(x), float(np.median(np.diff(x))) if len(x) > 1 else 1.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            pull = np.where(err > 0, (y - mod) / err, 0.0)
        rax.bar(x, pull, width=wid, color=po["color"] or PULL_COLOR, lw=0, zorder=2)
        if po["chi2"]:
            ok = err > 0
            chi2, ndf = float(np.sum(pull[ok] ** 2)), int(ok.sum()) - po["nparams"]
            self._chi2_text = rf"$\chi^2/\mathrm{{ndf}}$ = {chi2:.1f}/{ndf}"
            if self._o["layout"] != "topright":
                rax.text(0.98, 0.9, self._chi2_text, ha="right", va="top",
                         bbox=dict(fc="white", ec="none", alpha=0.85, pad=2), zorder=6,
                         transform=rax.transAxes, fontsize=plt.rcParams["legend.fontsize"] * 0.8)
        rax.axhline(0, color="0.3", lw=1, zorder=3)
        for k in (-3, 3):
            rax.axhline(k, color="0.5", lw=1, ls="--", zorder=1)
        lim = po["ylim"]
        if lim is None:
            big = float(np.nanmax(np.abs(pull))) if np.isfinite(pull).any() else 0.0
            m = max(5.0, float(np.ceil(1.15 * min(big, 25.0))))
            lim = (-m, m)
        rax.set_ylim(*lim)
        rax.set_yticks([-3, 0, 3])
        rax.set_ylabel(po["ylabel"])

    # 2D --------------------------------------------------------------------
    def _render2d(self):
        o = self._o
        if len(self.series) != 1 or o["panel"]:
            raise ValueError("a 2D histogram is drawn alone, without panels")
        h = self.series[0].obj
        self.fig, self.ax, self.rax = self._figure(False)
        v = h.values
        if o["zlog"]:
            v = np.ma.masked_less_equal(v, 0)
            lim = o["zlim"] or (v.min(), v.max())
            norm = LogNorm(*lim)
        else:
            norm = Normalize(*(o["zlim"] or (None, None)))
        mesh = self.ax.pcolormesh(h.xedges, h.yedges, v.T, cmap=o["cmap"] or "viridis", norm=norm,
                                  rasterized=True)
        cb = self.fig.colorbar(mesh, ax=self.ax, pad=0.02)
        cb.set_label(o["zlabel"] if o["zlabel"] is not None else h.ztitle)
        self.ax.set_xlabel(o["xlabel"] if o["xlabel"] is not None else h.xtitle)
        self.ax.set_ylabel(o["ylabel"] if o["ylabel"] is not None else h.ytitle)
        if o["xlim"]:
            self.ax.set_xlim(*o["xlim"])
        if o["ylim"]:
            self.ax.set_ylim(*o["ylim"])

    # shared finishing --------------------------------------------------------
    def _finish(self):
        o, ax = self._o, self.ax
        xl = ax.get_xlim()
        self._draw_blind()
        if o["title"]:
            ax.set_title(o["title"])
        for a in (ax, self.rax):
            if a is None:
                continue
            if o["minor"]:
                a.minorticks_on()
            if o["grid"] and o["grid"][0]:
                a.grid(True, **{"alpha": 0.3, **o["grid"][1]})
        if self.rax is not None:
            from matplotlib.ticker import MaxNLocator
            if not o["logy"]:  # keep matplotlib's log locator on log axes
                ax.yaxis.set_major_locator(MaxNLocator(nbins="auto", prune="lower"))
            self.fig.align_ylabels([ax, self.rax])
        yl = ax.yaxis.label
        n = len(yl.get_text())
        if n > 28:  # long auto-labels: shrink so they fit the axis height
            yl.set_fontsize(yl.get_fontsize() * (0.8 if n <= 40 else 0.65))
        if self.rax is not None:
            self.rax.yaxis.label.set_fontsize(yl.get_fontsize())
        if self.series[0].kind == "colormap":
            if o["label"]:
                hep.label.exp_label(ax=ax, **{k: v for k, v in o["label"].items()
                                              if v is not None or k == "com"})
        elif o["layout"] == "classic":
            if o["label"]:
                hep.label.exp_label(ax=ax, **{k: v for k, v in o["label"].items()
                                              if v is not None or k == "com"})
            self._legend(ax, None)
        else:
            self._topright(ax)
        for f in self._extras:
            f(ax, self.rax)
        ax.set_xlim(xl)


    # ------------------------------------------------------------- top-right text block
    def _renderer(self):
        try:
            return self.fig.canvas.get_renderer()
        except AttributeError:
            return self.fig._get_renderer()

    def _legend(self, ax, anchor_y, ncol=None):
        """Draw the legend. anchor_y: axes-fraction y of the top edge (top-right layout)."""
        o = self._o
        leg = {"show": True, "loc": "upper right", "title": None, "order": None}
        leg.update(o["legend"])
        _, leg["ncol"], shrink, outside = self._legend_plan()
        if ncol:
            leg["ncol"] = ncol
        base = FontProperties(size=plt.rcParams["legend.fontsize"]).get_size_in_points()
        if outside:
            leg.update(loc="upper left", bbox_to_anchor=(1.01, 1.0), ncol=1, borderaxespad=0.0)
        elif anchor_y is not None:
            leg.update(loc="upper right", bbox_to_anchor=(1.0, anchor_y), borderaxespad=0.8)
        leg.setdefault("fontsize", base * shrink)
        if not leg.pop("show"):
            return None
        handles, labels = ax.get_legend_handles_labels()
        pairs = [(h, l) for h, l in zip(handles, labels) if l and not l.startswith("_")]
        order = leg.pop("order")
        if not order:
            names = [l for _, l in pairs]
            first = self._leg_order or [x.label for x in self.series]
            order = [b for b in dict.fromkeys(first) if b in names]
            order += [n for n in names if n not in order]
        names = [l for _, l in pairs]
        pairs = [pairs[names.index(k) if isinstance(k, str) else k] for k in order]
        return ax.legend(*zip(*pairs), **leg) if pairs else None

    def _topright(self, ax):
        """Experiment label top-left; info lines and legend as a small right-aligned column top-right."""
        from matplotlib.offsetbox import AnchoredOffsetbox, HPacker, TextArea, VPacker
        o = self._o
        base = FontProperties(size=plt.rcParams["legend.fontsize"]).get_size_in_points()
        fam = plt.rcParams["font.family"]
        left_rows, right_rows = [], []
        lab = o["label"]
        if lab:
            parts = []
            if lab.get("exp"):
                parts.append(TextArea(lab["exp"], textprops=dict(
                    fontweight="bold", fontsize=base * 1.25, family=fam)))
            tail = " ".join(t for t in [("Simulation" if not lab.get("data", True) else ""),
                                        lab.get("text") or ""] if t)
            if tail:
                parts.append(TextArea(tail, textprops=dict(
                    fontstyle="italic", fontsize=base * 1.1, family=fam)))
            if parts:
                left_rows.append(HPacker(children=parts, pad=0, sep=5, align="baseline"))
            extra = []
            if lab.get("com"):
                extra.append(f"\u221as = {lab['com']} TeV")
            if lab.get("lumi"):
                extra.append(rf"{lab['lumi']} fb$^{{-1}}$")
            if extra:
                left_rows.append(TextArea(", ".join(extra), textprops=dict(
                    fontsize=base * 0.82, family=fam)))
        lines = list(o["info"]) + ([self._chi2_text] if getattr(self, "_chi2_text", None) else [])
        for ln in lines:
            right_rows.append(TextArea(ln, textprops=dict(fontsize=base * 0.82, family=fam)))

        def box(rows, loc, align):
            ab = AnchoredOffsetbox(loc=loc, child=VPacker(children=rows, pad=0, sep=3, align=align),
                                   pad=0.0, borderpad=0.75, frameon=False,
                                   prop=FontProperties(size=base))
            ax.add_artist(ab)
            return ab

        r = self._renderer()
        inv = ax.transAxes.inverted()
        free = not (o["ylim"] or o["headroom"])
        needs = []
        if left_rows:
            bl = box(left_rows, "upper left", "left").get_window_extent(r).transformed(inv)
            needs.append((0.0, bl.x1 + 0.01, bl.y0))
        ab = box(right_rows, "upper right", "right") if right_rows else None
        low, left = 1.0, 1.0
        y_top = None
        if ab is not None:
            bb = ab.get_window_extent(r).transformed(inv)
            low, left, y_top = bb.y0, bb.x0, bb.y0 - 0.012
        auto = o["legend"].get("ncol", "auto") in (None, "auto") and not self._legend_plan()[3]
        cands = [1, 2, 3] if auto and free else [None]
        best = None
        for nc in cands:
            leg = self._legend(ax, y_top, ncol=nc)
            lo_, le_ = low, left
            if leg is not None and not self._legend_plan()[3]:
                bb = leg.get_window_extent(r).transformed(inv)
                lo_, le_ = min(lo_, bb.y0), min(le_, bb.x0)
            reg = needs + ([(le_, 1.0, lo_)] if lo_ < 1.0 else [])
            top = max([self._fit_block(ax, a, b, y0, apply=False) for a, b, y0 in reg] or [0])
            if best is None or top < best[0] - 1e-9 * abs(top):
                best = (top, nc)
            if len(cands) > 1 and leg is not None:
                leg.remove()
        if len(cands) > 1:
            self._legend(ax, y_top, ncol=best[1])
        if free and best[0]:
            ax.set_ylim(ax.get_ylim()[0], best[0])

    def _fit_block(self, ax, xa_f, xb_f, y0f, apply=False):
        """y-limit needed so no data sits under a text block spanning [xa_f, xb_f] x [y0f, 1] (axes fractions)."""
        xl, yl = ax.get_xlim(), ax.get_ylim()

        def to_x(f):
            return (10 ** (math.log10(xl[0]) + f * (math.log10(xl[1]) - math.log10(xl[0])))
                    if self._o["logx"] else xl[0] + f * (xl[1] - xl[0]))

        xa, xb = to_x(xa_f), to_x(xb_f)
        loc, glob = yl[0], yl[0]
        for s in self.series:
            o_ = s.obj.trimmed() if isinstance(s.obj, D.G) else s.obj
            x, y = _xy(o_)
            top = y + (o_.errors if isinstance(o_, D.H1) else o_.eyh)
            if not np.isfinite(top).any():
                continue
            glob = max(glob, float(np.nanmax(top)))
            m = (x >= xa) & (x <= xb) & np.isfinite(top)
            if np.any(m):
                loc = max(loc, float(np.max(top[m])))
        frac = max(y0f - 0.02, 0.15)
        if self._o["logy"]:
            new = max(yl[0] * (loc / yl[0]) ** (1 / frac), glob * 1.6)
        else:
            new = max(yl[0] + (loc - yl[0]) / frac, glob * 1.08)
        if apply:
            ax.set_ylim(yl[0], new)
        return new

    # ------------------------------------------------------------- output
    def draw(self):
        """Return (fig, ax, rax); re-renders only if something changed."""
        if self._dirty or self.fig is None:
            self.render()
        return self.fig, self.ax, self.rax

    def save(self, path, formats=None, dpi=None, transparent=False):
        """save('out.pdf') or save('out', formats=('pdf', 'png')). Dots in a name are kept."""
        fig, _, _ = self.draw()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        has_ext = p.suffix.lower() in KNOWN_EXT
        stem = p.with_suffix("") if has_ext else p
        if formats:
            targets = [Path(f"{stem}.{f.lstrip('.')}") for f in formats]
        else:
            targets = [p if has_ext else Path(f"{p}.pdf")]
        with self._rc_context():
            for t in targets:
                fig.savefig(t, dpi=dpi, transparent=transparent)
        return self

    def close(self) -> Plot:
        """Unregister the figure from pyplot (frees it for batch runs). The Plot, p.fig and p.ax
        stay usable for save() and further customisation."""
        if self.fig is not None and self._target is None:
            plt.close(self.fig)
        return self

    def _repr_png_(self):
        """Inline display in Jupyter."""
        import io

        fig, _, _ = self.draw()
        buf = io.BytesIO()
        with self._rc_context():
            fig.savefig(buf, format="png", dpi=150)
        return buf.getvalue()

    def show(self):
        self.draw()
        plt.show()
        return self


class Panels(list):
    """The panels of a combined figure (a list of Plot); ``.fig`` is the shared matplotlib Figure."""

    def __init__(self, plots, fig):
        super().__init__(plots)
        self.fig = fig

    def save(self, path, formats=None, dpi=None, transparent=False):
        """save('all.pdf') or save('all', formats=('pdf', 'png'))."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        has_ext = p.suffix.lower() in KNOWN_EXT
        stem = p.with_suffix("") if has_ext else p
        targets = ([Path(f"{stem}.{f.lstrip('.')}") for f in formats] if formats
                   else [p if has_ext else Path(f"{p}.pdf")])
        with self[0]._rc_context():
            for t in targets:
                self.fig.savefig(t, dpi=dpi, transparent=transparent)
        return self

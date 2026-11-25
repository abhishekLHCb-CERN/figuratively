"""The single registry of every option ``fg.plot`` understands.

One record per option: name, one-line doc, an example value and the kind of plot it applies to.
The README table, ``fg.options()``, the typo suggestions and the test-suite are all driven from here,
so an option cannot exist without documentation.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass

# Project-wide defaults (also the keys allowed in figuratively.toml and fg.configure).
DEFAULTS: dict = dict(
    exp="", label=None, data=True, com=None, lumi=None, unit=None,
    formats=("pdf", "png"), outdir="plots", style="LHCb2", dpi=None, transparent=False,
    labels={}, colors={}, info=(), nparams=None,
    data_label="Data", total_label="Total fit", data_pattern=r"data",
    palette="figuratively", tone="colour", root_colors=True, blind_curves=False, suffix="", canvas_text=True,
    ylabel_prefix="Candidates", pull_label="Pull", ratio_label="Data / MC", blind_label="Blinded",
    preset=None, presets={}, view=False, checks=True,
)


@dataclass(frozen=True)
class Opt:
    name: str
    doc: str
    example: object
    ctx: str = "any"  # "fit" (RooFit canvas), "hist" (histogram overlay) or "any"
    group: str = "text"


_O = Opt
OPTIONS: list[Opt] = [
    # ---- components of a fit
    _O("components", "per-component style: {'sig': 'red dashed fill', 'bkg*': {'alpha': .4}}", {"sig": "red dashed"}, "fit", "components"),
    _O("labels", "rename legend entries: {'sig': 'Signal', 'data': 'Data', 'total': 'Fit'} or just a list in legend "
       "order ['Data', 'Fit', 'Signal', ...]", {"sig": "Signal", "data": "Observed", "total": "Fit"}, "fit", "components"),
    _O("colors", "colour per object or component: {'sig': '#0072B2'}", {"sig": "#0072B2"}, "fit", "components"),
    _O("styles", "full per-component style dicts: {'comb': {'kind': 'fill', 'hatch': '//'}}", {"comb": {"kind": "fill", "hatch": "//"}}, "fit", "components"),
    _O("comp_kind", "default drawing style of every component: 'line', 'fill' or 'band'", "fill", "fit", "components"),
    _O("merge", "sum several components into one entry: {'Backgrounds': ['comb', 'bkg*']}", {"Backgrounds": ["comb", "bkg_a"]}, "fit", "components"),
    _O("hide", "regular expressions of components to leave out", ["bkg_c"], "fit", "components"),
    _O("order", "component order in the legend and the stack", ["comb", "sig"], "fit", "components"),
    _O("stack", "stack the components as filled areas", True, "fit", "components"),
    _O("root_colors", "True takes colours, line styles and fills from the ROOT objects (refined, and kept visibly "
       "apart); 'components' leaves the total in the house colour; False ignores ROOT", True, "fit", "components"),
    _O("tone", "overall look: colour (default), mono (greys and line styles, for print) or dark (light on dark, for slides)",
       "mono", "any", "figure"),
    _O("palette", "colours for components without a ROOT colour: figuratively, r4, okabe-ito, tableau10, dark2, hcl",
       "okabe-ito", "any", "components"),
    _O("pull", "False to drop the pull panel, or a dict of Plot.pull options: {'ylim': (-4, 4), 'mode': 'centre'}; the "
       "range grows beyond +-5 by itself when the pulls are larger", {"ylim": (-4, 4)}, "fit", "panels"),
    _O("nparams", "number of fit parameters; adds chi2/ndf to the info block", 10, "fit", "panels"),
    # ---- histograms
    _O("ratio", "False to drop the ratio panel, or its y-range: (0.7, 1.3)", (0.7, 1.3), "hist", "panels"),
    _O("normalise", "normalise every histogram to unit area", True, "hist", "histograms"),
    _O("rebin", "merge N neighbouring bins", 2, "hist", "histograms"),
    _O("kind", "drawing style of histograms: 'step', 'fill', 'points' or 'band'", "step", "hist", "histograms"),
    _O("data_pattern", "regular expression that marks an object as data", "data", "hist", "histograms"),
    # ---- regions, lines and text
    _O("blind", "hide data in a window and mark it: (1840, 1890) or [(a, b), (c, d)]", (1840, 1890), "any", "annotations"),
    _O("blind_curves", "with blind=: also blank the model curves inside the window", True, "fit", "annotations"),
    _O("vline", "vertical line(s): 1865, (1865, 'label') or a list of those", [1865, (1840, "cut")], "any", "annotations"),
    _O("hline", "horizontal line(s): 100, (100, 'label') or a list of those", (100, "threshold"), "any", "annotations"),
    _O("span", "shaded window(s): (x0, x1) or (x0, x1, 'label') or a list of those", (1850, 1880, "signal"), "any", "annotations"),
    _O("text", "text at axes fractions: (0.05, 0.9, 'text') or a list of those", (0.05, 0.9, "text"), "any", "annotations"),
    _O("canvas_text", "text written on the canvas (e.g. the bin range): True shows it, False hides it, a dict {old: new} "
       "edits it, a function f(text, panel) rewrites it (return None to drop)", {"#DeltaM": "m"}, "fit", "annotations"),
    _O("ylabel_prefix", "start of the automatic y-label, e.g. 'Events' gives 'Events / (2 MeV)'", "Events", "any", "axes"),
    _O("pull_label", "y-label of the pull panel", "(data - fit) / error", "fit", "panels"),
    _O("ratio_label", "y-label of the ratio panel", "Data / sim.", "hist", "panels"),
    _O("blind_label", "text inside a blinded band (a window can also carry its own: (lo, hi, 'text'))", "Hidden", "fit", "annotations"),
    _O("info", "small text lines in the top-right block (string or list)", ["2018 data"], "any", "annotations"),
    _O("label", "top-left label text, e.g. 'Work in progress' (none by default)", "Work in progress", "any", "annotations"),
    _O("exp", "collaboration name in the label; empty by default, set it only if you are entitled to", "", "any", "annotations"),
    _O("com", "centre-of-mass energy in TeV for the label, e.g. '13'", "13", "any", "annotations"),
    _O("lumi", "integrated luminosity in fb^-1 for the label", "5.4", "any", "annotations"),
    _O("data", "False prints 'Simulation' in the label", True, "any", "annotations"),
    # ---- axes
    _O("xlim", "x range (lo, hi); None keeps a side automatic", (1750, 1950), "any", "axes"),
    _O("ylim", "y range (lo, hi)", (0, 3000), "any", "axes"),
    _O("xrange", "alias of xlim", (1750, 1950), "any", "axes"),
    _O("yrange", "alias of ylim", (0, 3000), "any", "axes"),
    _O("logx", "logarithmic x axis", True, "hist", "axes"),
    _O("logy", "logarithmic y axis", True, "any", "axes"),
    _O("log", "'x', 'y' or 'xy': shorthand for logx / logy", "y", "any", "axes"),
    _O("xlabel", "x label, or (text, unit)", ("$m$", "MeV/$c^2$"), "any", "axes"),
    _O("ylabel", "y label (default is generated from the bin width)", "Events", "any", "axes"),
    _O("unit", "unit used in the axis labels and the bin-width label", "MeV", "any", "axes"),
    _O("scale_x", "multiply the x axis, e.g. 1e-3 for MeV to GeV (set unit= too)", 1e-3, "any", "axes"),
    _O("title", "figure title", "A title", "any", "axes"),
    _O("grid", "draw a grid", True, "any", "axes"),
    _O("headroom", "factor of free space above the data", 1.5, "any", "axes"),
    # ---- figure
    _O("preset", "a named bundle of settings: thesis, paper, slides, poster, or one of your own from the "
       "[presets.NAME] tables of figuratively.toml; the call's own keywords always win", "slides", "any", "figure"),
    _O("presets", "your own presets as a dict {name: {option: value}} (usually written in figuratively.toml)",
       {"mine": {"size": "double", "palette": "okabe-ito"}}, "any", "figure"),
    _O("size", "figure size (w, h) in inches or a preset: 'column', 'double', 'slide'", "column", "any", "figure"),
    _O("figsize", "alias of size", (8, 6), "any", "figure"),
    _O("font", "scale every text size", 1.2, "any", "figure"),
    _O("legend", "False, a location string, or a dict(loc=, ncol=, title=)", {"loc": "lower left"}, "any", "figure"),
    _O("style", "mplhep style name or path of a .mplstyle file", "LHCb2", "any", "figure"),
    _O("data_label", "legend text of the data", "Data", "fit", "figure"),
    _O("total_label", "legend text of the total fit", "Fit", "fit", "figure"),
    # ---- output
    _O("formats", "file formats to write", ("png",), "any", "output"),
    _O("suffix", "text added to the automatic file name, so variants do not overwrite each other: '_stack_log'", "_v2", "any", "output"),
    _O("checks", "warn about a curve that does not match the data, huge pulls, a leaking blind window, silent "
       "normalisation and objects of the canvas that are not drawn (False silences them)", False, "any", "output"),
    _O("view", "open the saved figure in your default viewer when done", False, "any", "output"),
    _O("outdir", "folder for the output, relative to the ROOT file", "plots", "any", "output"),
    _O("dpi", "resolution of raster output", 200, "any", "output"),
    _O("transparent", "transparent background", True, "any", "output"),
    _O("strict", "turn warnings about unmatched names into errors", False, "any", "output"),
]
ALIASES = {"figsize": "size", "xrange": "xlim", "yrange": "ylim"}
BY_NAME = {o.name: o for o in OPTIONS}


def suggest(name: str, choices, n: int = 3) -> list[str]:
    return difflib.get_close_matches(str(name), [str(c) for c in choices], n=n, cutoff=0.5)


def did_you_mean(name: str, choices) -> str:
    near = suggest(name, choices)
    return f"; did you mean {', '.join(repr(x) for x in near)}?" if near else ""


def options(show: bool = True, group: str | None = None) -> list[Opt]:
    """List every option with its default and a one-line description (fg.options())."""
    rows = [o for o in OPTIONS if group in (None, o.group)]
    if show:
        w = max(len(o.name) for o in rows)
        last = None
        for o in rows:
            if o.group != last:
                print(f"\n[{o.group}]")
                last = o.group
            d = DEFAULTS.get(o.name, "")
            print(f"  {o.name:<{w}}  {o.doc}" + (f"  (default: {d!r})" if o.name in DEFAULTS and d not in ("", None) else ""))
    return rows


_TITLES = {"components": "Fit components", "panels": "Panels", "histograms": "Histograms",
           "annotations": "Regions, lines and text", "axes": "Axes", "figure": "Figure", "output": "Output"}


def options_markdown() -> str:
    """The option tables of the README, generated from the registry (a test keeps them in sync)."""
    out: list[str] = []
    for g, title in _TITLES.items():
        rows = [o for o in OPTIONS if o.group == g]
        if rows:
            out += [f"**{title}**", "", "| Option | Effect |", "|---|---|"]
            out += [f"| `{o.name}` | {o.doc.replace('|', '/')} |" for o in rows]
            out.append("")
    return "\n".join(out).rstrip() + "\n"

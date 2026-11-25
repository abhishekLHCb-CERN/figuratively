"""Plotting from TTrees, multi-panel grids and fit comparisons, built on ``fg.plot``.

    h = fg.tree("f.root:DecayTree", "D0_M", bins=60, range=(1800, 1930), cut="D0_PT > 2000 and nTracks < 400")
    fg.plot(h)                                  # or overlay several: fg.plot(h_data, h_mc)
    fg.grid("f.root:a", "f.root:b", ("f.root:data", "f.root:mc"), shape=(1, 3))
    fg.compare("fit_a.root:canvas", "fit_b.root:canvas", names=["nominal", "alternative"])

Cuts and expressions are evaluated by a small checked evaluator (branch names, numbers, comparisons, and/or/not,
+ - * / ** and a few maths functions), never by ``eval``.
"""
from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np

from . import data as D
from .data import split_spec
from .options import did_you_mean

_TREE_CLASSES = ("TTree", "ROOT::RNTuple", "ROOT::Experimental::RNTuple")
_FUNCS = {"abs": np.abs, "sqrt": np.sqrt, "log": np.log, "log10": np.log10, "exp": np.exp}
_BIN = {ast.Add: np.add, ast.Sub: np.subtract, ast.Mult: np.multiply, ast.Div: np.true_divide, ast.Pow: np.power}
_CMP = {ast.Lt: np.less, ast.LtE: np.less_equal, ast.Gt: np.greater, ast.GtE: np.greater_equal,
        ast.Eq: np.equal, ast.NotEq: np.not_equal}


def _evaluate(expr: str, columns: dict):
    """Evaluate ``expr`` over numpy columns. Anything outside the small grammar is refused."""
    if len(expr) > 500:
        raise ValueError("expression is too long (500 characters at most)")
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"cannot read the expression '{expr}': {e.msg}") from None

    def go(n):
        if isinstance(n, ast.Expression):
            return go(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.Name):
            if n.id not in columns:
                raise KeyError(f"'{n.id}' is not a branch of the tree{did_you_mean(n.id, columns)} "
                               f"(branches: {', '.join(list(columns)[:12])}{', ...' if len(columns) > 12 else ''})")
            return columns[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            return _BIN[type(n.op)](go(n.left), go(n.right))
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.BitAnd, ast.BitOr)):
            f = np.logical_and if isinstance(n.op, ast.BitAnd) else np.logical_or
            return f(go(n.left), go(n.right))
        if isinstance(n, ast.UnaryOp):
            v = go(n.operand)
            if isinstance(n.op, ast.USub):
                return -v
            if isinstance(n.op, ast.UAdd):
                return v
            if isinstance(n.op, (ast.Not, ast.Invert)):
                return np.logical_not(v)
        if isinstance(n, ast.BoolOp):
            f = np.logical_and if isinstance(n.op, ast.And) else np.logical_or
            out = go(n.values[0])
            for v in n.values[1:]:
                out = f(out, go(v))
            return out
        if isinstance(n, ast.Compare):
            left, out = go(n.left), None
            for op, comp in zip(n.ops, n.comparators):
                if type(op) not in _CMP:
                    break
                right = go(comp)
                r = _CMP[type(op)](left, right)
                out = r if out is None else np.logical_and(out, r)
                left = right
            else:
                return out
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS
                and len(n.args) == 1 and not n.keywords):
            return _FUNCS[n.func.id](go(n.args[0]))
        raise ValueError(f"'{ast.unparse(n)}' is not allowed in an expression (use branch names, numbers, "
                         "comparisons, and/or/not, + - * / ** and abs, sqrt, log, log10, exp)")

    return go(tree)


def _names_in(expr: str) -> list[str]:
    try:
        return sorted({n.id for n in ast.walk(ast.parse(expr.strip(), mode="eval")) if isinstance(n, ast.Name)
                       and n.id not in _FUNCS})
    except SyntaxError:
        return []


def _open_tree(spec: str):
    import uproot

    path, key = split_spec(spec)
    f = uproot.open(path)
    trees = [k.split(";")[0] for k, c in f.classnames().items() if c in _TREE_CLASSES]
    if key is None:
        if len(trees) != 1:
            raise ValueError(f"{path} holds {len(trees)} trees or ntuples ({', '.join(trees) or 'none'}); name one: '{path}:TREE'")
        key = trees[0]
    elif key not in trees and f"{key}" not in f:
        raise KeyError(f"'{key}' not found in {path}{did_you_mean(key, trees)} (trees: {', '.join(trees) or 'none'})")
    return f[key], key


def tree(spec, expr, bins=50, range=None, cut=None, weight=None, name=None, xtitle=None, entry_stop=None) -> D.H1:
    """Histogram a TTree branch (or an expression of branches) into an ``H1`` that ``fg.plot`` can draw.

    ``spec``   'file.root:TreeName' (the name may be left out when the file holds one tree)
    ``expr``   a branch name or an expression such as 'D0_PT / 1000'
    ``bins``   a number of bins or an array of edges; ``range`` is (lo, hi), by default the span of the data
    ``cut``    e.g. 'D0_M > 1800 and nTracks < 400' (see the module help for what is allowed)
    ``weight`` a branch or expression giving the weight of each entry (errors are then sqrt of the sum of w^2)
    """
    import awkward as ak

    t, key = _open_tree(spec)
    needed = sorted(set(_names_in(expr)) | set(_names_in(cut or "")) | set(_names_in(weight or "")))
    available = [k for k in t.keys()]
    for n in needed:
        if n not in available:
            raise KeyError(f"'{n}' is not a branch of {key}{did_you_mean(n, available)} "
                           f"(branches: {', '.join(available[:12])}{', ...' if len(available) > 12 else ''})")
    arrays = t.arrays(needed, library="ak", entry_stop=entry_stop)
    cols = {n: np.asarray(ak.to_numpy(arrays[n])) if arrays[n].ndim == 1 else None for n in needed}
    if any(v is None for v in cols.values()):
        jag = [n for n, v in cols.items() if v is None]
        if len(needed) > 1 or len(jag) > 1:
            raise ValueError(f"{', '.join(jag)} holds several values per entry; cannot be combined with other "
                             "branches. Plot such a branch on its own (its values are flattened).")
        cols = {jag[0]: np.asarray(ak.to_numpy(ak.flatten(arrays[jag[0]], axis=None)))}
    x = np.asarray(_evaluate(expr, cols), dtype=float)
    keep = np.ones(x.shape, dtype=bool)
    if cut:
        keep &= np.asarray(_evaluate(cut, cols), dtype=bool)
    keep &= np.isfinite(x)
    w = None
    if weight:
        w = np.asarray(_evaluate(weight, cols), dtype=float)
    xs = x[keep]
    if xs.size == 0:
        raise ValueError(f"no entries of {key} survive the cut{f' ({cut})' if cut else ''}")
    if isinstance(bins, (list, tuple, np.ndarray)):
        edges = np.asarray(bins, dtype=float)
    else:
        lo, hi = range if range is not None else (float(xs.min()), float(xs.max()))
        if not hi > lo:
            hi = lo + 1.0
        edges = np.linspace(lo, hi, int(bins) + 1)
    ws = None if w is None else w[keep]
    values, _ = np.histogram(xs, bins=edges, weights=ws)
    errors = (np.sqrt(np.histogram(xs, bins=edges, weights=ws**2)[0]) if ws is not None
              else np.sqrt(values))
    label = name or Path(split_spec(spec)[0]).stem
    return D.H1(values=values.astype(float), edges=edges, errors=errors.astype(float), name=label,
                xtitle=xtitle if xtitle is not None else expr, ytitle="")


def grid(*cells, shape=None, out=None, save=True, panel_size=(5.2, 4.2), legend="first", titles=None, **opts):
    """Several plots in one figure, in vector quality. Each cell is a spec ('f.root:name'), a histogram from
    ``fg.tree``, or a tuple of those to overlay (data against MC, say). Keywords go to every panel.

        fg.grid("a.root:h", "b.root:h", ("a.root:data", "a.root:mc"), shape=(1, 3), out="all.pdf")

    A cell may end with a dict of options for that panel only: ``("a.root:data", "a.root:mc", {"normalise": True})``.
    ``shape`` is (rows, cols) (default: up to 3 columns), ``legend`` is 'first', 'all' or 'none', ``titles`` a list
    of panel titles. Returns the list of Plots; ``.save('x.pdf')`` writes it again.
    """
    import matplotlib.pyplot as plt

    from .auto import CONFIG, _view, plot
    from .plot import KNOWN_EXT, Panels

    if len(cells) == 1 and isinstance(cells[0], list):
        cells = tuple(cells[0])
    if not cells:
        raise ValueError("grid needs at least one cell: fg.grid('a.root:h', 'b.root:h')")
    items = [tuple(c) if isinstance(c, (tuple, list)) else (c,) for c in cells]
    own = [dict(i[-1]) if isinstance(i[-1], dict) else {} for i in items]
    items = [i[:-1] if isinstance(i[-1], dict) else i for i in items]
    if any(not i for i in items):
        raise ValueError("grid: a cell that holds only options has nothing to draw")
    n = len(items)
    ncols = shape[1] if shape else min(3, n)
    nrows = shape[0] if shape else math.ceil(n / ncols)
    if nrows * ncols < n:
        raise ValueError(f"grid: {n} cells do not fit {nrows} x {ncols}")
    if legend not in ("first", "all", "none"):
        raise ValueError(f"grid: legend is 'first', 'all' or 'none', got {legend!r}")
    if titles is not None and len(titles) != n:
        raise ValueError(f"grid: {len(titles)} titles for {n} cells")
    pw, ph = panel_size
    fig = plt.figure(figsize=(pw * ncols, ph * nrows))
    subs = list(fig.subfigures(nrows, ncols, wspace=0.01, hspace=0.01).ravel())
    scale = max(min(pw / 11.0, 1.3), 0.3)
    plots = []
    for k, item in enumerate(items):
        kw = {**opts, **own[k]}
        if k > 0:
            kw["label"] = None
        if legend == "none" or (legend == "first" and k > 0):
            kw["legend"] = False
        p = plot(*item, save=False, _target=subs[k], **kw)
        if isinstance(p, (list, tuple)):
            raise ValueError(f"grid: cell {k + 1} is a canvas with several panels; use plot(..., combine=True) for it")
        p._sscale, p._lscale, p._eff_rc = scale, max(min(scale, 1.3), 0.45), None
        p.draw()
        if titles:
            p.ax.set_title(str(titles[k]))
        plots.append(p)
    panels = Panels(plots, fig)
    if save:
        target = Path(out) if out else Path(CONFIG["outdir"]) / "grid"
        has_ext = target.suffix.lower() in KNOWN_EXT
        panels.save(target, formats=None if has_ext else CONFIG["formats"], dpi=CONFIG["dpi"],
                    transparent=CONFIG["transparent"])
        print("wrote", target if has_ext else f"{target}.{{{','.join(CONFIG['formats'])}}}")
        if CONFIG["view"]:
            _view(target if has_ext else Path(f"{target}.{CONFIG['formats'][0]}"))
        plt.close(fig)
    return panels


def compare(*specs, names=None, **opts):
    """Overlay several fits of the same data: the data once, every total curve, and a ratio panel of each total to
    the first. ``names`` are the legend names (default: the file names).

        fg.compare("nominal.root:canvas", "variant.root:canvas", names=["nominal", "variant"])
    """
    from .auto import plot

    if len(specs) < 2:
        raise ValueError("compare needs at least two fits: fg.compare('a.root:canvas', 'b.root:canvas')")
    if names is not None:
        if isinstance(names, str) or len(names) != len(specs):
            raise ValueError(f"compare: give one name per fit ({len(specs)}), got {names!r}")
        opts["_names"] = list(names)
    return plot(*specs, **opts)

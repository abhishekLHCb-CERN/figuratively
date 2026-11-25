"""One-call interface: ``fg.plot("file.root:name")`` chooses sensible defaults for everything.

Set project-wide defaults once with ``fg.configure(...)`` or a ``figuratively.toml`` file (looked for in
the current folder and its parents, then in ~/.config/). Every keyword is listed by ``fg.options()``.
"""
from __future__ import annotations

import fnmatch
import re
import warnings
from pathlib import Path

from . import data as D
from .data import split_spec
from .options import ALIASES, BY_NAME, DEFAULTS, did_you_mean
from .plot import KNOWN_EXT, Panels, Plot

CONFIG: dict = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
_state = {"loaded": False, "path": None}
DRAWABLE = ("TH1", "TH2", "TProfile", "TGraph", "TCanvas", "RooPlot")


_TYPES = {"labels": (dict, list, tuple), "colors": dict, "formats": (list, tuple), "info": (str, list, tuple),
          "dpi": (int, float, type(None)), "transparent": bool, "nparams": (int, type(None)),
          "label": (str, type(None)), "exp": str, "unit": (str, type(None)), "com": (str, int, float, type(None)),
          "lumi": (str, int, float, type(None)), "outdir": str, "style": (str, type(None)), "data": bool,
          "palette": str, "root_colors": (bool, str), "blind_curves": bool, "suffix": str, "canvas_text": object, "preset": (str, list, tuple, type(None)), "presets": dict, "view": bool, "checks": bool, "ylabel_prefix": str, "pull_label": str,
          "ratio_label": str, "blind_label": str,
          "data_label": str, "total_label": str, "data_pattern": str}


def _validate(cfg: dict, source: str = "configure()"):
    for k, v in cfg.items():
        want = _TYPES.get(k)
        if want and not isinstance(v, want) or (want is not None and isinstance(v, bool) and bool not in (
                want if isinstance(want, tuple) else (want,)) and k != "transparent"):
            names = " or ".join(t.__name__ for t in (want if isinstance(want, tuple) else (want,)))
            raise TypeError(f"{source}: '{k}' must be {names}, got {type(v).__name__} ({v!r})")


def configure(**kw) -> dict:
    """Set defaults for every later plot, e.g. configure(label="Work in progress", unit="MeV")."""
    bad = [k for k in kw if k not in DEFAULTS]
    if bad:
        raise KeyError("; ".join(f"unknown config key '{k}'{did_you_mean(k, DEFAULTS)}" for k in bad)
                       + f" (valid: {', '.join(sorted(DEFAULTS))})")
    _validate(kw)
    CONFIG.update(kw)
    return CONFIG


def config_path():
    """The figuratively.toml that is in use, or None."""
    return _state["path"]


def _safe_outdir(value, source: str):
    """Configuration may only write below the current project: a relative folder without '..'."""
    o = Path(str(value))
    if o.is_absolute() or ".." in o.parts:
        raise ValueError(f"{source}: outdir must be a relative folder inside the project, got {value!r}")


def _check_settings(cfg: dict, source: str):
    """Settings that come from a file are checked harder than settings typed in your own code."""
    if "outdir" in cfg:
        _safe_outdir(cfg["outdir"], source)
    if isinstance(cfg.get("style"), str) and "://" in cfg["style"]:
        raise ValueError(f"{source}: style must not be a URL")
    for name, preset in (cfg.get("presets") or {}).items():
        _check_preset(name, preset, source)


def _allowed_options() -> set:
    return {o.name for o in BY_NAME.values()} | set(DEFAULTS) | set(ALIASES)


def _check_preset(name, preset, source: str):
    """A preset may only set documented options (see fg.options()), never call arbitrary methods such as save."""
    if not isinstance(preset, dict):
        raise TypeError(f"{source}: preset '{name}' must be a table of options")
    allowed = _allowed_options()
    for k, v in preset.items():
        if k.startswith("_") or k not in allowed:
            raise ValueError(f"{source}: preset '{name}' sets '{k}', which is not a documented option "
                             f"(presets may only use the options listed by fg.options()){did_you_mean(k, allowed)}")
        if k == "outdir":
            _safe_outdir(v, f"{source}: preset '{name}'")
        if k == "style" and isinstance(v, str) and "://" in v:
            raise ValueError(f"{source}: preset '{name}': style must not be a URL")


def _trusted_file(path: Path) -> bool:
    """A configuration file is only used if it belongs to you and nobody else can write to it."""
    import os

    try:
        st = path.stat()
    except OSError:
        return False
    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        return False
    return not (st.st_mode & 0o022)


def _config_candidates() -> list:
    """The current folder and its parents up to your home folder (never above it), then ~/.config."""
    home, cwd = Path.home().resolve(), Path.cwd().resolve()
    dirs = [cwd, *cwd.parents]
    dirs = dirs[: dirs.index(home) + 1] if home in dirs else [cwd]
    return [d / "figuratively.toml" for d in dirs] + [home / ".config" / "figuratively.toml"]


def load_config(path=None):
    """Read a figuratively.toml (explicit path, else the nearest one). Called automatically once."""
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib
        except ModuleNotFoundError:
            return None
    cands = [Path(path)] if path else _config_candidates()
    for c in cands:
        if c.is_file():
            if not path and not _trusted_file(c):
                warnings.warn(f"{c} was ignored: it belongs to another user or others can write to it "
                              "(chmod go-w to use it)", stacklevel=2)
                continue
            cfg = tomllib.loads(c.read_text())
            _check_settings(cfg.get("figuratively", cfg), str(c))
            cfg = cfg.get("figuratively", cfg)
            for k in [k for k in cfg if k not in DEFAULTS]:
                warnings.warn(f"{c}: unknown key '{k}'{did_you_mean(k, DEFAULTS)}; ignored", stacklevel=2)
            _validate({k: v for k, v in cfg.items() if k in DEFAULTS}, source=str(c))
            configure(**{k: v for k, v in cfg.items() if k in DEFAULTS})
            _state["path"] = c
            return c
    return None


# ------------------------------------------------------------- ROOT titles -> matplotlib
_GREEK = ["alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta", "theta", "vartheta", "iota", "kappa", "lambda", "mu", "nu", "xi", "omicron", "pi", "varpi", "rho", "sigma", "varsigma", "tau", "upsilon", "phi", "varphi", "chi", "psi", "omega", "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon", "Phi", "Psi", "Omega", "rightarrow", "leftarrow", "pm", "mp", "times", "infty", "partial", "nabla", "in", "leq", "geq"]
_TEX = re.compile(r"#(" + "|".join(sorted(_GREEK, key=len, reverse=True)) + r")")


def root_tex(s: str) -> str:
    """ROOT TLatex ('m(K^{+}K^{-}#gamma)') -> mathtext; plain words are left alone."""
    out = []
    for tok in s.split(" "):
        if re.search(r"#|\^|_\{", tok):
            tok = "$" + _TEX.sub(lambda m, t=tok: "\\" + m.group(1) + (
                " " if m.end() < len(t) and t[m.end()].isalpha() else ""), tok) + "$"
        out.append(tok)
    return " ".join(out)


_UNIT = re.compile(r"^(?:[kMGT]?eV|[pnum]?s|[kmcu]?m|rad|mrad|%|deg)(?![A-Za-z])")


def title_label(title: str):
    """'mass [MeV/c^{2}]' -> ('mass', 'MeV/$c^2$'); titles without a unit give unit None."""
    title = title or ""
    m = re.search(r"\s*[\[(]\s*([^\])]*?)\s*[\])]\s*$", title)
    if m and _UNIT.match(m.group(1)):
        unit = re.sub(r"c\^\{?2\}?", "$c^2$", m.group(1))
        return root_tex(title[:m.start()].strip()), unit
    return root_tex(title.strip()), None


# ------------------------------------------------------------- builders
def _resolve(spec):
    """-> (name, kind, payload, text labels); kind is 'frame' (one dict of objects), 'pads' (several panels)
    or 'obj' (one histogram or graph)."""
    if isinstance(spec, dict):
        return "fit", "frame", spec, []
    if isinstance(spec, (D.H1, D.H2, D.G)):
        return spec.name or "obj", "obj", spec, []
    obj, name = D._open_keyed(spec)
    if getattr(obj, "classname", "") in ("TCanvas", "TPad", "RooPlot"):
        pads = D.leaf_pads(obj)
        if len(pads) >= 2:
            return name, "pads", pads, []
        if len(pads) == 1:
            return name, "frame", pads[0][1], pads[0][2]
        return name, "frame", D.load_all(obj), []
    c = D.convert(obj)
    if c is None:
        raise TypeError(f"{spec} is a {obj.classname}, which figuratively cannot draw")
    return name, "obj", c, []


def _is_roofit(items) -> bool:
    return any(isinstance(o, D.G) and o.classname in ("RooHist", "RooCurve") for o in items.values())


def component_names(items) -> list[str]:
    """Names of the fit components found in a RooFit frame, in file order (total and pulls excluded)."""
    names: list[str] = []
    for key, o in items.items():
        if isinstance(o, D.G) and o.classname == "RooCurve" and not re.match(r"(pull|resid)_", key):
            c = "+".join(D.parse_roofit_name(key)["components"])
            if c and c not in names:
                names.append(c)
    return names


# ---- compact style strings: "red dashed fill thick"
_LINESTYLES = {"solid": "-", "dashed": "--", "dotted": ":", "dashdot": "-."}
_KINDS = ("line", "fill", "band")
_WIDTHS = {"thin": 1.0, "thick": 3.0}


def parse_style(value) -> dict:
    """'red dashed fill' or a dict -> a style dict for one component."""
    if isinstance(value, dict):
        allowed = {"color", "label", "kind", "style", "linestyle", "ls", "linewidth", "lw", "alpha", "hatch",
                   "order", "zorder", "edgecolor", "markersize", "marker"}
        for k in value:
            if k not in allowed:
                raise ValueError(f"unknown style key '{k}'{did_you_mean(k, allowed)} (keys: {', '.join(sorted(allowed))})")
        if "kind" in value and value["kind"] not in _KINDS:
            raise ValueError(f"style kind must be one of {', '.join(_KINDS)}, got {value['kind']!r}")
        if "style" in value and value["style"] not in _KINDS:
            raise ValueError(f"style must be one of {', '.join(_KINDS)}, got {value['style']!r}")
        if "alpha" in value and not 0 <= float(value["alpha"]) <= 1:
            raise ValueError(f"alpha must be between 0 and 1, got {value['alpha']!r}")
        st = dict(value)
        if "style" in st:
            st["kind"] = st.pop("style")
        if "ls" in st:
            st["linestyle"] = st.pop("ls")
        if "lw" in st:
            st["linewidth"] = st.pop("lw")
        return st
    if not isinstance(value, str):
        raise TypeError(f"a component style is a string like 'red dashed fill' or a dict, got {value!r}")
    from matplotlib import colors as mc

    st: dict = {}
    for tok in re.split(r"[\s,]+", value.strip()):
        if not tok:
            continue
        if tok in _LINESTYLES:
            st["linestyle"] = _LINESTYLES[tok]
        elif tok in _KINDS:
            st["kind"] = tok
        elif tok in _WIDTHS:
            st["linewidth"] = _WIDTHS[tok]
        elif tok.startswith("alpha="):
            try:
                a = float(tok[6:])
            except ValueError:
                raise ValueError(f"alpha must be a number between 0 and 1, got '{tok}' in '{value}'") from None
            if not 0 <= a <= 1:
                raise ValueError(f"alpha must be between 0 and 1, got {a} in '{value}'")
            st["alpha"] = a
        elif tok.startswith("hatch="):
            st["hatch"] = tok[6:]
        elif mc.is_color_like(tok):
            st["color"] = tok
        else:
            pool = [*_LINESTYLES, *_KINDS, *_WIDTHS, *mc.get_named_colors_mapping()]
            raise ValueError(f"unknown style word '{tok}' in '{value}'{did_you_mean(tok, pool)} "
                             "(words: a colour, solid/dashed/dotted/dashdot, line/fill/band, thin/thick, "
                             "alpha=0.4, hatch=//)")
    return st


def _problem(msg: str, strict: bool):
    if strict:
        raise ValueError(msg)
    warnings.warn(msg, stacklevel=4)


def _match(selector: str, names) -> list[str]:
    """Exact name, else glob ('bkg*'), else nothing."""
    if selector in names:
        return [selector]
    return [n for n in names if fnmatch.fnmatch(n, selector)]


def _check_keys(option: str, keys, names, strict: bool):
    for k in keys:
        if not _match(k, names):
            _problem(f"{option}: '{k}' matches no component{did_you_mean(k, names)} "
                     f"(detected: {', '.join(names) or 'none'})", strict)


def _wrong_context(opts, keys, where, strict):
    for k in keys:
        if k in opts:
            opts.pop(k)
            _problem(f"'{k}' applies to {where} only; ignored here", strict)


def order_given(opts) -> bool:
    return bool(opts.get("order") or opts.get("components"))


def _labels_dict(labels, entries, reordered=False) -> dict:
    """labels as a dict, or a list that names the legend entries in order (data, total, components ...)."""
    if isinstance(labels, dict):
        return dict(labels)
    if reordered:
        raise ValueError("labels as a list follows the file's legend order; with merge= or order= give a dict "
                         "such as {'sig': 'Signal'} instead")
    labels = list(labels)
    if len(labels) > len(entries):
        raise ValueError(f"labels has {len(labels)} entries but the legend has {len(entries)} "
                         f"({', '.join(entries)})")
    return dict(zip(entries, labels))


def _fit(p, items, cfg, opts, called, strict):
    _wrong_context(opts, ("ratio", "normalise", "rebin", "kind"), "histogram overlays", strict)
    names = component_names(items)
    merge = dict(opts.pop("merge", None) or {})
    valid = names + [m for m in merge if m not in names]
    if "merge" in called or merge:
        for label, members in merge.items():
            _check_keys(f"merge['{label}']", [members] if isinstance(members, str) else members, names, strict)
    labels, colors = _labels_dict(cfg["labels"], ["data", "total", *names], merge or order_given(opts)), dict(cfg["colors"])
    data_label = labels.pop("data", cfg["data_label"])
    total_label = labels.pop("total", cfg["total_label"])
    styles = {k: dict(v) for k, v in (opts.pop("styles", None) or {}).items()}
    order = opts.pop("order", None)
    comp = opts.pop("components", None) or {}
    if "labels" in called:
        _check_keys("labels", labels, valid, strict)
    if "colors" in called:
        _check_keys("colors", colors, valid, strict)
    _check_keys("styles", styles, valid, strict)
    _check_keys("components", comp, valid, strict)
    for sel, val in comp.items():
        st = parse_style(val)
        for t in _match(sel, valid):
            if "label" in st:
                labels[t] = st["label"]
            if "color" in st:
                colors[t] = st["color"]
            rest = {k: v for k, v in st.items() if k not in ("label", "color", "order")}
            if rest:
                styles.setdefault(t, {}).update(rest)
    if comp and order is None:  # an 'order' entry in a component style sorts the components
        ranked = sorted(((parse_style(v).get("order"), s) for s, v in comp.items() if isinstance(v, dict)
                         and "order" in v), key=lambda x: x[0])
        order = [t for _, s in ranked for t in _match(s, valid)] or None
    hide = opts.pop("hide", None)
    hide = [hide] if isinstance(hide, str) else hide
    for h in hide or []:
        try:
            re.compile(h)
        except re.error as e:
            raise ValueError(f"hide: '{h}' is not a valid regular expression ({e})") from None
        if not any(re.search(h, n) for n in valid) and not any(re.search(h, k) for k in items):
            _problem(f"hide: '{h}' matches no component{did_you_mean(h, valid)} "
                     f"(detected: {', '.join(valid) or 'none'})", strict)
    if order:
        _check_keys("order", order, valid, strict)
    if opts.get("stack") and opts.get("pull", True) is not False:
        pass  # stacked fits keep their pull panel
    p.add_roofit(items, labels=labels, colors=colors, styles=styles, hide=hide,
                 stack=opts.pop("stack", False), data_label=data_label,
                 total_label=total_label, order=order, merge=merge or None,
                 comp_kind=opts.pop("comp_kind", "line"), root_colors=cfg["root_colors"])
    if cfg["checks"]:
        from .checks import fit_warnings

        for w in fit_warnings(items, cfg["nparams"]):
            _problem(w, strict)
    pv = opts.pop("pull", True)
    if pv is not False and ("total" not in p._roles or "data" not in p._roles):
        _problem("pull panel skipped: it needs the data and the total curve (was the total hidden?)", strict)
    elif pv is not False:
        n = cfg["nparams"]
        kw = {"chi2": n is not None, "nparams": n or 0, "ylabel": cfg["pull_label"]}
        kw.update(pv if isinstance(pv, dict) else {})
        p.pull(**kw)


COMPARE_COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]
COMPARE_STYLES = ["-", "--", "-.", ":", (0, (6, 2, 1, 2)), (0, (2, 2))]


def _compare(p, runs, cfg, opts, strict):
    """Several fits of the same data: the data once, every total curve, and a ratio panel of each total to the
    first, zoomed in on how much they differ."""
    import numpy as np

    _wrong_context(opts, ("stack", "components", "merge", "styles", "comp_kind", "order", "hide", "pull",
                          "normalise", "rebin", "kind"), "a single fit", strict)
    names = [n for n, _ in runs]
    labels = _labels_dict(cfg["labels"], ["data", *names])
    data = [[o for k, o in items.items() if isinstance(o, D.G) and o.classname == "RooHist"
             and not k.startswith(("pull_", "resid_"))] for _, items in runs]
    totals = []
    for n, items in runs:
        t = next((o for k, o in items.items() if isinstance(o, D.G) and o.classname == "RooCurve"
                  and not D.parse_roofit_name(k)["components"]), None)
        if t is None:
            raise ValueError(f"compare: '{n}' has no total curve")
        totals.append(t)
    if not data[0]:
        raise ValueError(f"compare: '{names[0]}' has no data points")
    for (n, _), d in zip(runs[1:], data[1:]):
        if not d or len(d[0].y) != len(data[0][0].y) or not np.allclose(d[0].y, data[0][0].y):
            _problem(f"compare: the data in '{n}' differ from those in '{names[0]}'; the data of '{names[0]}' are shown",
                     strict)
    data_label = labels.pop("data", cfg["data_label"])
    p.add(data[0][0], data_label, "points", "black", zorder=5, in_ratio=False)
    p._roles["data"] = len(p.series) - 1
    for i, ((n, _), t) in enumerate(zip(runs, totals)):
        p.add(t, labels.get(n, n), "line", COMPARE_COLORS[i % len(COMPARE_COLORS)],
              linestyle=COMPARE_STYLES[i % len(COMPARE_STYLES)], linewidth=2.6 if i == 0 else 2.2, zorder=4)
        if i == 0:
            p._roles["total"] = len(p.series) - 1
    p._leg_order = [data_label, *[labels.get(n, n) for n in names]]
    ratio = opts.pop("ratio", True)
    if ratio is not False:
        p.ratio(ref=p._roles["total"], ylabel=f"vs {labels.get(names[0], names[0])}", zoom=not isinstance(ratio, tuple),
                **({"ylim": ratio} if isinstance(ratio, tuple) else {}))


def _overlay(p, objs, cfg, opts, strict=False):
    _wrong_context(opts, ("stack", "components", "merge", "styles", "comp_kind", "order", "hide", "pull"),
                   "RooFit frames", strict)
    h2 = [o for _, o in objs if isinstance(o, D.H2)]
    if h2:
        p.add(h2[0])
        return
    pat = re.compile(cfg["data_pattern"], re.IGNORECASE)
    labels_map = _labels_dict(cfg["labels"], [n for n, _ in objs])
    name_of = lambda n: labels_map.get(n) or n
    is_data = [bool(pat.search(n)) and isinstance(o, D.H1) for n, o in objs]
    h1 = [o for _, o in objs if isinstance(o, D.H1)]
    multi = len(objs) > 1
    norm = opts.pop("normalise", None)
    chose_automatically = norm is None
    if norm is None:  # compare shapes when yields differ by more than 5 %
        norm = multi and len(h1) > 1 and h1[0].integral > 0 and any(
            abs(o.integral / h1[0].integral - 1) > 0.05 for o in h1)
    if norm and chose_automatically and cfg["checks"]:
        _problem("the histograms were normalised to unit area because their yields differ "
                 f"({', '.join(f'{o.integral:.6g}' for o in h1)}); pass normalise=True or False to decide", strict)
    forced = opts.pop("kind", None)
    rebin = opts.pop("rebin", None)
    seen_model = False
    for (n, o), d in zip(objs, is_data):
        col = cfg["colors"].get(n) or ("black" if d else None)
        if isinstance(o, D.H1):
            kind = forced or ("points" if d else ("fill" if not seen_model and not multi else
                                                   "fill" if not seen_model and any(is_data) else "step"))
            seen_model = seen_model or not d
            p.add(o, name_of(n), kind, col, normalise=norm, rebin=rebin)
        else:
            p.add(o, name_of(n), forced, col)
    ratio = opts.pop("ratio", True)
    ref = next((i for i, ((_, o), d) in enumerate(zip(objs, is_data)) if isinstance(o, D.H1) and not d), None)
    if ratio and any(is_data) and ref is not None:
        p.ratio(ref=ref, ylabel=cfg["ratio_label"], **({"ylim": ratio} if isinstance(ratio, tuple) else {}))


def _canvas_lines(texts, setting, panel=1):
    """The text written on the canvas, edited as asked: True (as is), False (hidden), {old: new} replacements,
    a text or list of texts (instead), or a function f(text, panel) -> text or None."""
    if setting is True or setting is None:
        return list(texts)
    if setting is False:
        return []
    if isinstance(setting, str):
        return [setting]
    if isinstance(setting, (list, tuple)):
        return [str(x) for x in setting]
    if isinstance(setting, dict):
        out = []
        for t in texts:
            for old, new in setting.items():
                t = t.replace(old, new)
            out.append(t)
        return out
    if callable(setting):
        out = []
        for t in texts:
            try:
                new = setting(t, panel)
            except TypeError:
                new = setting(t)
            if new:
                out.append(new)
        return out
    raise TypeError(f"canvas_text must be True, False, a dict, a text or a function, got {setting!r}")


def _decorate(p, first, cfg, opts, scaled=False, texts=(), panel=1):
    xl, unit = title_label(getattr(first, "xtitle", ""))
    unit = cfg["unit"] or (None if scaled else unit)  # a rescaled axis must not keep the old unit
    if xl:
        p.xlabel(xl, unit)
    elif cfg["unit"]:
        p.unit(cfg["unit"])
    if isinstance(first, D.H2):
        yl, yu = title_label(first.ytitle)
        if yl:
            p.ylabel(f"{yl} [{yu}]" if yu else yl)
        if first.ztitle:
            p.zaxis(label=root_tex(first.ztitle))
    if cfg["label"] is not None:
        p.label(cfg["label"], exp=cfg["exp"], data=cfg["data"], com=cfg["com"], lumi=cfg["lumi"])
    as_list = lambda v: [v] if isinstance(v, str) else list(v or ())
    lines = as_list(cfg["info"]) + as_list(opts.pop("info", ()))
    lines += [root_tex(t) for t in _canvas_lines(texts, cfg["canvas_text"], panel)]
    if cfg["ylabel_prefix"] != "Candidates":
        p.ylabel(prefix=cfg["ylabel_prefix"])
    if lines:
        p.info(*lines)


_MULTI = {"vline", "hline", "span", "text"}


def _unique(names) -> list:
    """Make run names distinct ('fit', 'fit' -> 'fit', 'fit_2'), so each gets its own legend entry."""
    seen: dict = {}
    out = []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}_{seen[n]}")
    return out


def _run_name(spec, res, names_in, k) -> str:
    """The legend name of one fit in a comparison: given by the caller, else the file name."""
    if names_in:
        return names_in[k]
    return Path(split_spec(spec)[0]).stem if isinstance(spec, str) else res[0]


def _plot_pads(specs, resl, out, save, cfg, orig, combine=None):
    """Canvases with several panels (e.g. one fit per mass bin): one figure per panel, or one combined figure.
    Several such canvases are compared panel by panel."""
    names = _unique([_run_name(sp, r, None, k) for k, (sp, r) in enumerate(zip(specs, resl))])
    lists = [r[2] for r in resl]
    n = min(len(x) for x in lists)
    if len({len(x) for x in lists}) > 1:
        warnings.warn(f"the canvases have different numbers of panels ({', '.join(str(len(x)) for x in lists)}); "
                      f"comparing the first {n}", stacklevel=3)
    first = Path(split_spec(specs[0])[0]) if isinstance(specs[0], str) else Path(".")
    stem = "_vs_".join(Path(split_spec(s)[0]).stem if isinstance(s, str) else r[0] for s, r in zip(specs, resl))
    stem = f"{stem}_{resl[0][0]}" if len(resl) == 1 else f"{stem}_{resl[0][0]}"
    run_names = names if len(resl) > 1 else None
    if combine:
        return _combine_panels(lists, n, first, stem, out, save, cfg, orig, combine, run_names)
    results = []
    for k in range(n):
        kw = dict(orig)
        if out:
            o = Path(out)
            ext = o.suffix if o.suffix.lower() in KNOWN_EXT else ""
            kw["out"] = o.with_name(f"{o.stem if ext else o.name}_{k + 1}{ext}")
        else:
            kw["_where"] = (first.parent / cfg["outdir"], f"{stem}_{k + 1}")
        results.append(plot(*[pl[k][1] for pl in lists], save=save, _texts=lists[0][k][2], _panel=k + 1,
                            _names=run_names, **kw))
    return results


def _combine_panels(lists, n, first, stem, out, save, cfg, orig, combine, run_names):
    """All panels of a canvas in one figure: combine=True, (rows, cols) or dict(shape=, panel_size=, legend=)."""
    import math

    import matplotlib.pyplot as plt

    spec = combine if isinstance(combine, dict) else ({"shape": combine} if isinstance(combine, tuple) else {})
    shape = spec.get("shape")
    ncols = shape[1] if shape else min(3, n)
    nrows = shape[0] if shape else math.ceil(n / ncols)
    if nrows * ncols < n:
        raise ValueError(f"combine: {n} panels do not fit a {nrows} x {ncols} grid")
    pw, ph = spec.get("panel_size", (5.2, 4.2))
    legend_mode = spec.get("legend", "first")
    fig = plt.figure(figsize=(pw * ncols, ph * nrows))
    cells = list(fig.subfigures(nrows, ncols, wspace=0.01, hspace=0.01).ravel())
    scale = max(min(pw / 11.0, 1.3), 0.3)
    plots = []
    for k in range(n):
        kw = dict(orig)
        if k > 0:
            kw["label"] = None  # the label belongs on the first panel only
        if legend_mode == "none" or (legend_mode == "first" and k > 0):
            kw["legend"] = False
        p = plot(*[pl[k][1] for pl in lists], save=False, _texts=lists[0][k][2], _panel=k + 1, _names=run_names,
                 _target=cells[k], **kw)
        p._sscale, p._lscale, p._eff_rc = scale, max(min(scale, 1.3), 0.45), None
        p.draw()
        plots.append(p)
    panels = Panels(plots, fig)
    if save:
        target = Path(out) if out else first.parent / cfg["outdir"] / f"{stem}_panels"
        has_ext = target.suffix.lower() in KNOWN_EXT
        panels.save(target, formats=None if has_ext else cfg["formats"], dpi=cfg["dpi"], transparent=cfg["transparent"])
        print("wrote", target if has_ext else f"{target}.{{{','.join(cfg['formats'])}}}")
        if cfg["view"]:
            _view(target if has_ext else Path(f"{target}.{cfg['formats'][0]}"))
        plt.close(fig)
    return panels


def _windows(blind):
    """blind=(lo, hi) or [(lo, hi), ...] -> list of (lo, hi) pairs."""
    if blind is None:
        return []
    num = lambda x: isinstance(x, (int, float))
    if isinstance(blind, (tuple, list)) and len(blind) in (2, 3) and num(blind[0]) and num(blind[1]):
        return [tuple(blind)]
    if isinstance(blind, (tuple, list)) and all(isinstance(w, (tuple, list)) and len(w) in (2, 3) for w in blind):
        return [tuple(w) for w in blind]
    raise TypeError(f"blind expects (lo, hi) or a list of (lo, hi) pairs, got {blind!r}")


def _call(f, v):
    if isinstance(v, dict):
        return f(**v)
    if isinstance(v, (tuple, list)):
        return f(*v)
    return f(v)


def _canonical(opts: dict) -> dict:
    """Resolve aliases (figsize, xrange, yrange, log=) and refuse contradictory duplicates."""
    out = dict(opts)
    for alias, name in ALIASES.items():
        if alias in out:
            if name in out:
                raise TypeError(f"both '{alias}' and '{name}' given; they mean the same thing, use one")
            out[name] = out.pop(alias)
    if "log" in out:
        v = str(out.pop("log")).lower()
        bad = set(v) - set("xy")
        if bad or not v:
            raise ValueError(f"log must be 'x', 'y' or 'xy', got {v!r}")
        for ax in v:
            out[f"log{ax}"] = True
    return out


def valid_keywords() -> list[str]:
    methods = [m for m in dir(Plot) if not m.startswith("_") and callable(getattr(Plot, m))]
    return sorted({*BY_NAME, *DEFAULTS, *methods, *ALIASES})


def _apply(p, opts):
    """Forward the remaining keywords to Plot methods: logy=True, xlim=(a, b), size="column" ..."""
    for k, v in opts.items():
        f = getattr(p, k, None)
        if k.startswith("_") or not callable(f):
            raise TypeError(f"unknown option '{k}'{did_you_mean(k, valid_keywords())}; "
                            "list all options with fg.options()")
        if k == "legend" and v is False:
            f(False)
        elif v is True:
            f()
        elif v is False or v is None:
            continue
        elif k in _MULTI and isinstance(v, list):
            for item in v:
                _call(f, item)
        else:
            _call(f, v)


def _is_root_object(o) -> bool:
    """A live PyROOT object (TCanvas, TH1, TGraph, RooPlot, TFile ...): it has ClassName() and Write()."""
    return (not isinstance(o, (str, Path, dict, D.H1, D.H2, D.G))
            and callable(getattr(o, "ClassName", None)) and callable(getattr(o, "Write", None)))


def _plot_root_objects(specs, out, save, opts):
    """Plot live PyROOT objects: ROOT itself writes them to a temporary file, which is then read like any
    other ROOT file, so every feature (panels, colours, pulls ...) works the same."""
    import tempfile

    try:
        import ROOT
    except ImportError:
        raise ImportError("fg.plot() was given a ROOT object, which needs PyROOT (`import ROOT`). "
                          "Without ROOT, save the canvas to a file (canvas.SaveAs('c.root')) and pass the file name.") from None
    outdir = Path(opts.pop("outdir", None) or CONFIG["outdir"]).resolve()  # relative to the current folder
    with tempfile.TemporaryDirectory() as tmp:
        path, resolved, names = Path(tmp) / "objects.root", [], []
        to_write = []
        for k, o in enumerate(specs):
            if not _is_root_object(o):
                resolved.append(o)
            elif o.ClassName() == "TFile":  # an open file: plot it by name
                resolved.append(str(o.GetName()))
            else:
                name = str(o.GetName() or f"object{k}")
                while name in names:
                    name += "_"
                names.append(name)
                to_write.append((name, o))
                resolved.append(f"{path}:{name}")
        if to_write:
            f = ROOT.TFile(str(path), "RECREATE")
            for name, o in to_write:
                o.Write(name)
            f.Close()
        if out is None and names:
            out = outdir / "+".join(names)[:80]
        return plot(*resolved, out=out, save=save, outdir=str(outdir), **opts)


BUILTIN_PRESETS: dict = {
    "thesis": {"size": "double", "formats": ("pdf", "png")},
    "paper": {"size": "column", "formats": ("pdf",)},
    "slides": {"size": "slide", "formats": ("png",), "dpi": 200},
    "poster": {"size": (16, 11), "font": 1.3, "formats": ("pdf",)},
}


def _preset_options(names, cfg_presets) -> dict:
    """Merge the options of one or several presets ('thesis', 'thesis+mine', ['thesis', 'mine'])."""
    if names is None:
        return {}
    names = [n for part in ([names] if isinstance(names, str) else names) for n in str(part).split("+") if n]
    known = {**BUILTIN_PRESETS, **(cfg_presets or {})}
    for n in names:
        if n in known:
            _check_preset(n, known[n], "preset")
    out: dict = {}
    for n in names:
        if n not in known:
            raise ValueError(f"unknown preset '{n}'{did_you_mean(n, known)} (presets: {', '.join(known)})")
        out.update(known[n])
    return out


def _expand_globs(spec):
    """'Helicity*.root' or '*.root:c2' -> the matching files (one plot each); None if there is no pattern."""
    import glob

    if not isinstance(spec, str):
        return None
    head, key = split_spec(spec)
    if not any(ch in head for ch in "*?[") or Path(head).exists():
        return None
    files = sorted(glob.glob(head))
    if not files:
        raise FileNotFoundError(f"no file matches '{head}'")
    return [f if key is None else f"{f}:{key}" for f in files]


def _view(path):
    """Open a saved figure in the default viewer."""
    import os
    import subprocess
    import sys

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except OSError as e:
        warnings.warn(f"view: could not open {path} ({e})", stacklevel=3)


def plot(*specs, out=None, save=True, **opts) -> Plot | list:
    """Plot anything from ROOT with one call and no boilerplate.

    plot("f.root:canvas")              RooFit frame: data, total, components, pulls
    plot("f.root:h_data", "f.root:h_mc")   data vs MC overlay with ratio panel
    plot("f.root:h2")                  2D histogram
    plot("f.root")                     every histogram / graph / canvas in the file

    Customise with keywords (the full list: ``fg.options()``). Examples::

        fg.plot(f, logy=True, xlim=(1800, 1900), size="column")
        fg.plot(f, components={"sig": "red dashed fill"}, merge={"Backgrounds": ["comb", "bkg*"]})
        fg.plot(f, blind=(1840, 1890), vline=[(1865, "$m_{D^0}$")], span=(1850, 1880, "signal"))

    Not sure what is in a canvas? ``fg.inspect(f)`` lists it and prints a call you can edit.
    Inside PyROOT you can pass live objects: ``fg.plot(canvas)``, ``fg.plot(hist_data, hist_mc)``.
    Returns the Plot (still customisable) or a list of them for whole files.
    """
    if not _state["loaded"]:
        _state["loaded"] = True
        if load_config():
            print(f"figuratively: using settings from {_state['path']}")
    if len(specs) == 1 and isinstance(specs[0], (list, tuple)):  # a list of files: one plot each
        return [plot(s, save=save, **opts) for s in specs[0]]
    expanded = _expand_globs(specs[0]) if len(specs) == 1 else None
    if expanded is not None:
        done = []
        for f in expanded:
            try:
                done.append(plot(f, save=save, **opts))
            except Exception as e:  # one bad file must not stop the rest
                warnings.warn(f"skipped {f}: {type(e).__name__}: {e}", stacklevel=2)
        return done
    if any(_is_root_object(s) for s in specs):
        return _plot_root_objects(specs, out, save, opts)
    if len(specs) == 1 and isinstance(specs[0], str) and split_spec(specs[0])[1] is None:
        done = []
        for k, v in D.list_objects(specs[0]).items():
            if not v.startswith(DRAWABLE):
                continue
            try:
                done.append(plot(f"{specs[0]}:{k}", save=save, **opts))
            except Exception as e:  # one bad object must not stop the whole file
                warnings.warn(f"skipped {k}: {type(e).__name__}: {e}", stacklevel=2)
        return done
    opts = _canonical(opts)
    named = opts.pop("preset", CONFIG["preset"])
    for k, v in _canonical(_preset_options(named, opts.get("presets", CONFIG["presets"]))).items():
        opts.setdefault(k, v)  # a preset fills in what the call did not say
    where = opts.pop("_where", None)
    panel = opts.pop("_panel", 1)
    texts_in = opts.pop("_texts", None)
    texts_in = D.Texts() if texts_in is None else texts_in
    names_in = opts.pop("_names", None)
    target = opts.pop("_target", None)
    combine = opts.pop("combine", None)
    orig = dict(opts)
    strict = bool(opts.pop("strict", False))
    called = {k for k in opts if k in DEFAULTS}
    cfg = dict(CONFIG)
    for k in [k for k in opts if k in DEFAULTS]:
        cfg[k] = opts.pop(k)
    sx = opts.pop("scale_x", None)
    if sx is not None:
        try:
            sx = float(sx)
        except (TypeError, ValueError):
            raise TypeError(f"scale_x must be a number such as 1e-3, got {sx!r}") from None
    blind = _windows(opts.pop("blind", None))
    res = [_resolve(s) for s in specs]
    if sx:
        res = [(n, kind, ({k: D.scale_x(o, sx) for k, o in pl.items()} if kind == "frame"
                          else D.scale_x(pl, sx) if kind == "obj" else pl), t) for n, kind, pl, t in res]
        if not cfg["unit"]:
            warnings.warn("scale_x changes the axis values; pass unit='GeV' (or similar) to label them",
                          stacklevel=2)
    if all(r[1] == "pads" for r in res):
        return _plot_pads(specs, res, out, save, cfg, orig, combine)
    if combine:
        _problem("combine applies to canvases with several panels; ignored here", False)
    texts = res[0][3] if (res[0][3] or getattr(res[0][3], "attrs", None)) else texts_in
    attrs = getattr(texts, "attrs", None) or {}
    for flag, key in (("logy", "logy"), ("logx", "logx")):  # what the canvas says, unless the call says otherwise
        if attrs.get(flag):
            opts.setdefault(key, True)
    if attrs.get("xrange") and "xlim" not in opts:
        opts["xlim"] = attrs["xrange"]
    if attrs.get("skipped") and cfg["checks"]:
        from collections import Counter

        shown = ", ".join(f"{c} x{n}" if n > 1 else c for c, n in Counter(attrs["skipped"]).items())
        _problem(f"the canvas holds objects that are not drawn: {shown} (add their text with info=, labels= or text=)",
                 strict)
    p = Plot(style=cfg["style"])
    p._target = target
    if cfg["palette"] != "figuratively":
        p.palette(cfg["palette"])
    comparing = len(res) >= 2 and all(r[1] == "frame" and _is_roofit(r[2]) for r in res)
    if comparing:
        runs = [(n, r[2]) for n, r in zip(_unique([_run_name(sp, r, names_in, k) for k, (sp, r)
                                                    in enumerate(zip(specs, res))]), res)]
        first = next(iter(res[0][2].values()))
        _compare(p, runs, cfg, opts, strict)
    elif res[0][1] == "frame" and _is_roofit(res[0][2]):
        first = next(iter(res[0][2].values()))
        _fit(p, res[0][2], cfg, opts, called, strict)
    else:
        objs = [(n, o) for n, kind, payload, _t in res
                for n, o in (payload.items() if kind == "frame" else [(n, payload)])]
        first = objs[0][1]
        _overlay(p, objs, cfg, opts, strict)
    _decorate(p, first, cfg, opts, scaled=bool(sx), texts=texts, panel=panel)
    if blind and not cfg["blind_curves"] and cfg["checks"] and res[0][1] == "frame":
        _problem("blind: the model curves are still drawn inside the blinded window; if the fit used those events, "
                 "blind_curves=True hides them", strict)
    for win in blind:
        lo, hi, *text = win
        p.blind(lo, hi, label=text[0] if text else cfg["blind_label"], curves=bool(cfg["blind_curves"]))
    _apply(p, opts)
    if save:
        names = "+".join(r[0].replace("/", "_") for r in res)[:80]
        s0 = specs[0]
        fpath = Path(split_spec(s0)[0]) if isinstance(s0, str) else None
        stem = (f"{fpath.stem}_{names}" if fpath else names) + str(cfg["suffix"] or "")
        if where:
            target = Path(where[0]) / (where[1] + str(cfg["suffix"] or ""))
        else:
            target = Path(out) if out else ((fpath.parent if fpath else Path(".")) / cfg["outdir"] / stem)
        has_ext = target.suffix.lower() in KNOWN_EXT
        existed = [t for t in ([target] if has_ext else [Path(f"{target}.{f}") for f in cfg["formats"]]) if t.exists()]
        p.save(target, formats=None if has_ext else cfg["formats"], dpi=cfg["dpi"],
               transparent=cfg["transparent"])
        print("wrote", target if has_ext else f"{target}.{{{','.join(cfg['formats'])}}}",
              "(replaced an existing file)" if existed else "")
        if cfg["view"]:
            _view(target if has_ext else Path(f"{target}.{cfg['formats'][0]}"))
        p.close()  # free the matplotlib figure (important for whole-file runs)
    return p

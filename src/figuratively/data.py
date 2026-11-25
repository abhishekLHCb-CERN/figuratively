"""Plain containers for ROOT objects and the uproot readers that fill them."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

import numpy as np
import uproot


@dataclass
class H1:
    values: np.ndarray
    edges: np.ndarray
    errors: np.ndarray
    name: str = ""
    xtitle: str = ""
    ytitle: str = ""
    classname: str = "TH1D"
    normalised: bool = False
    root: dict = field(default_factory=dict)  # ROOT line/fill/marker attributes (colour indices, styles)

    @property
    def centers(self) -> np.ndarray:
        return 0.5 * (self.edges[1:] + self.edges[:-1])

    @property
    def widths(self) -> np.ndarray:
        return np.diff(self.edges)

    @property
    def uniform(self) -> bool:
        return bool(np.allclose(self.widths, self.widths[0], rtol=1e-6))

    @property
    def integral(self) -> float:
        return float(self.values.sum())

    def scaled(self, f: float) -> H1:
        return replace(self, values=self.values * f, errors=self.errors * abs(f))

    def normalised_to(self, total: float = 1.0, density: bool = False) -> H1:
        norm = float((self.values * (self.widths if density else 1.0)).sum())
        if norm == 0:
            raise ValueError(f"cannot normalise empty histogram '{self.name}'")
        return replace(self.scaled(total / norm), normalised=True)

    def rebinned(self, n: int) -> H1:
        nb = len(self.values)
        if nb % n:
            raise ValueError(f"cannot rebin {nb} bins by {n}")
        return replace(
            self,
            values=self.values.reshape(-1, n).sum(1),
            errors=np.sqrt((self.errors**2).reshape(-1, n).sum(1)),
            edges=self.edges[::n],
        )

    def cropped(self, lo: float | None, hi: float | None) -> H1:
        """Keep the bins that lie entirely inside [lo, hi]."""
        lo = -np.inf if lo is None else lo
        hi = np.inf if hi is None else hi
        tol = 1e-9 * (self.edges[-1] - self.edges[0])
        idx = np.flatnonzero((self.edges[:-1] >= lo - tol) & (self.edges[1:] <= hi + tol))
        if idx.size == 0:
            raise ValueError(f"no bins of '{self.name}' inside [{lo}, {hi}]")
        a, b = idx[0], idx[-1] + 1
        return replace(self, values=self.values[a:b], errors=self.errors[a:b],
                       edges=self.edges[a:b + 1])


@dataclass
class H2:
    values: np.ndarray  # shape (nx, ny)
    xedges: np.ndarray
    yedges: np.ndarray
    name: str = ""
    xtitle: str = ""
    ytitle: str = ""
    ztitle: str = ""

    def scaled(self, f: float) -> H2:
        return replace(self, values=self.values * f)


@dataclass
class G:
    """TGraph family (TGraph, TGraphErrors, TGraphAsymmErrors, RooHist, RooCurve)."""
    x: np.ndarray
    y: np.ndarray
    exl: np.ndarray
    exh: np.ndarray
    eyl: np.ndarray
    eyh: np.ndarray
    name: str = ""
    xtitle: str = ""
    ytitle: str = ""
    classname: str = "TGraph"
    root: dict = field(default_factory=dict)

    @property
    def has_xerr(self) -> bool:
        return bool(np.any(self.exl) or np.any(self.exh))

    @property
    def has_yerr(self) -> bool:
        return bool(np.any(self.eyl) or np.any(self.eyh))

    def scaled(self, f: float) -> G:
        return replace(self, y=self.y * f, eyl=self.eyl * abs(f), eyh=self.eyh * abs(f))

    def trimmed(self) -> G:
        """Drop the zero-height closing points RooFit adds at both ends of a RooCurve."""
        if self.classname == "RooCurve" and len(self.x) > 3 and self.y[0] == 0 and self.y[-1] == 0:
            sl = slice(1, -1)
            return replace(self, x=self.x[sl], y=self.y[sl], exl=self.exl[sl], exh=self.exh[sl],
                           eyl=self.eyl[sl], eyh=self.eyh[sl])
        return self

    def cropped(self, lo: float | None, hi: float | None) -> G:
        m = np.ones(len(self.x), bool)
        if lo is not None:
            m &= self.x >= lo
        if hi is not None:
            m &= self.x <= hi
        return replace(self, x=self.x[m], y=self.y[m], exl=self.exl[m], exh=self.exh[m],
                       eyl=self.eyl[m], eyh=self.eyh[m])


# ---------------------------------------------------------------- readers

def _title(obj, i: int) -> str:
    try:
        return str(obj.axis(i).member("fTitle"))
    except Exception:
        return ""


def _name(obj) -> str:
    try:
        return str(obj.member("fName"))
    except Exception:
        return ""


def _errors(obj) -> np.ndarray:
    try:
        return np.asarray(obj.errors(), float)
    except Exception:
        return np.sqrt(np.asarray(obj.variances(), float))


def _members(obj) -> dict:
    return getattr(obj, "all_members", {}) or {}


def _root_attrs(obj) -> dict:
    """ROOT drawing attributes stored with an object (TAttLine / TAttFill / TAttMarker)."""
    m = _members(obj)
    out = {}
    for key, name in (("line_color", "fLineColor"), ("line_style", "fLineStyle"), ("line_width", "fLineWidth"),
                      ("fill_color", "fFillColor"), ("fill_style", "fFillStyle"), ("marker_color", "fMarkerColor")):
        try:
            out[key] = int(m[name])
        except (KeyError, TypeError, ValueError):
            out[key] = None
    return out


def convert(obj):
    """uproot object -> H1 / H2 / G, or None when the class is not drawable data."""
    cn = getattr(obj, "classname", "")
    if cn.startswith("TH1") or cn == "TProfile":
        return H1(np.asarray(obj.values(), float), np.asarray(obj.axis(0).edges(), float),
                  _errors(obj), _name(obj), _title(obj, 0), "", cn,
                  root=_root_attrs(obj))
    if cn.startswith("TH2") or cn == "TProfile2D":
        return H2(np.asarray(obj.values(), float), np.asarray(obj.axis(0).edges(), float),
                  np.asarray(obj.axis(1).edges(), float), _name(obj), _title(obj, 0),
                  _title(obj, 1), _title(obj, 2))
    if cn.startswith("TGraph") or cn in ("RooHist", "RooCurve"):
        m = _members(obj)
        x = np.asarray(m["fX"], float)
        y = np.asarray(m["fY"], float)

        def get(*keys):
            for k in keys:
                if k in m:
                    return np.asarray(m[k], float)
            return np.zeros_like(x)

        ey = get("fEY")
        ex = get("fEX")
        return G(x, y, get("fEXlow") if "fEXlow" in m else ex,
                 get("fEXhigh") if "fEXhigh" in m else ex,
                 get("fEYlow") if "fEYlow" in m else ey,
                 get("fEYhigh") if "fEYhigh" in m else ey,
                 _name(obj), "", "", cn, root=_root_attrs(obj))
    return None


class Texts(list):
    """The text labels of a panel; ``.attrs`` carries the other things the canvas says: log scales,
    the frame's x range and the classes of objects that figuratively does not draw."""

    def __init__(self, items=(), attrs=None):
        super().__init__(items)
        self.attrs = attrs or {}


def _is_pad(o) -> bool:
    return getattr(o, "classname", "") in ("TCanvas", "TPad")


def _dedupe(items) -> dict:
    out: dict = {}
    for c in items:
        key, n = c.name or type(c).__name__, 1
        while key in out:
            n += 1
            key = f"{c.name}_{n}"
        out[key] = c
    return out


def _direct(pad):
    """Drawable objects, text labels and axis titles that belong directly to one pad (not its sub-pads)."""
    prims = [p for p in pad.member("fPrimitives") if p is not None]
    xt = yt = ""
    for p in prims:
        if _is_frame(p):
            xt, yt = xt or _title(p, 0), yt or _title(p, 1)
    def flag(name):
        try:
            return bool(pad.member(name))
        except Exception:
            return False

    attrs: dict = {"logx": flag("fLogx"), "logy": flag("fLogy"), "xrange": None, "skipped": []}
    for p in prims:
        if _is_frame(p):
            try:
                e = p.axis(0).edges()
                attrs["xrange"] = (float(e[0]), float(e[-1]))
            except Exception:
                pass
            break
    items, texts = [], []
    for p in prims:
        if _is_pad(p) or _is_frame(p):
            continue
        cn = getattr(p, "classname", None)
        if cn in ("TLatex", "TText"):
            t = str(p.member("fTitle")).strip()
            if t:
                texts.append(t)
            continue
        got = list(expand(p))
        if not got and cn != "TFrame":
            attrs["skipped"].append(cn or "unreadable object")
        for c in got:
            c.xtitle = getattr(c, "xtitle", "") or xt
            if hasattr(c, "ytitle"):
                c.ytitle = c.ytitle or yt
            items.append(c)
    return items, Texts(texts, attrs)


def leaf_pads(obj) -> list:
    """The panels of a canvas: [(pad name, {name: object}, [text labels])] for every pad that directly
    holds data. Pull pads (only pull histograms) and empty pads are left out."""
    if not _is_pad(obj):
        items = list(expand(obj))
        return [(_name(obj), _dedupe(items), [])] if items else []
    out = []
    items, texts = _direct(obj)
    if any(not re.match(r"(pull|resid)_", c.name or "") for c in items):
        out.append((_name(obj), _dedupe(items), texts))
    for p in obj.member("fPrimitives"):
        if p is not None and _is_pad(p):
            out += leaf_pads(p)
    return out


def parse_roofit_name(name: str) -> dict:
    """'model_Norm[m]_Comp[sig,bkg]' -> {'pdf': 'model', 'components': ('sig', 'bkg')}."""
    m = re.search(r"_Comp\[(.*?)\]", name)
    pdf = re.split(r"_(?:Norm|Comp|Range|NormRange|Int)\[", name)[0]
    return {"pdf": pdf, "components": tuple(m.group(1).split(",")) if m else ()}


def _is_frame(obj) -> bool:
    """RooFit/ROOT axis-frame histogram that only carries axis titles."""
    return getattr(obj, "classname", "").startswith("TH1") and _name(obj).startswith("frame_")


def expand(obj):
    """Yield every drawable object inside a TCanvas, TPad or RooPlot."""
    cn = getattr(obj, "classname", "")
    if cn in ("TCanvas", "TPad"):
        prims = list(obj.member("fPrimitives"))
        xt = yt = ""
        for p in prims:
            if _is_frame(p):
                xt, yt = xt or _title(p, 0), yt or _title(p, 1)
        for p in prims:
            if _is_frame(p):
                continue
            for c in expand(p):
                c.xtitle = getattr(c, "xtitle", "") or xt
                if hasattr(c, "ytitle"):
                    c.ytitle = c.ytitle or yt
                yield c
    elif cn == "RooPlot":
        try:
            frame = obj.member("_hist")
            xt, yt = _title(frame, 0), _title(frame, 1)
        except Exception:
            xt = yt = ""
        for p in obj.member("_items"):
            for c in expand(p):
                c.xtitle, c.ytitle = c.xtitle or xt, c.ytitle or yt
                yield c
    else:
        c = convert(obj)
        if c is not None:
            yield c


class _NoBytesBase:
    """Stand-in model for ROOT bases that write no data (TQObject), which uproot cannot parse."""


def _tolerant(orig):
    """Wrap uproot's object reader: if one object inside a canvas cannot be deserialised (an exotic class,
    a version mismatch), skip it using its byte count and carry on, instead of losing the whole canvas."""
    import struct

    from uproot.deserialization import DeserializationError

    def read(chunk, cursor, context, file, selffile, parent, *a, **k):
        start = cursor.index
        try:
            return orig(chunk, cursor, context, file, selffile, parent, *a, **k)
        except DeserializationError:
            cursor.move_to(start)
            (count,) = cursor.fields(chunk, struct.Struct(">I"), context)
            if not count & 0x40000000:  # no byte count: cannot skip safely
                raise
            cursor.move_to(start + 4 + (count & ~0x40000000))
            return None

    return read


def _canvas_fallback(f, key):
    """uproot cannot read TCanvas (no streamer in the file). A canvas is a TPad plus a few extra
    members, so skip the TCanvas header and read the TPad part; TQObject, a base that writes
    nothing, is stubbed out."""
    import uproot.model

    class Model_TQObject(uproot.model.Model):
        def read_numbytes_version(self, chunk, cursor, context):
            self._num_bytes = None
            self._instance_version = None

        def read_members(self, chunk, cursor, context, file):
            pass

        def check_numbytes(self, chunk, cursor, context):
            pass

    import uproot.deserialization as ds

    _ = f.file.streamers  # must be loaded before the stub is registered
    f.file._custom_classes = {**(f.file._custom_classes or {}), "TQObject": Model_TQObject}
    chunk, cursor = f.key(key).get_uncompressed_chunk_cursor()
    cursor.skip(6)  # TCanvas version header
    original = ds.read_object_any
    ds.read_object_any = _tolerant(original)
    try:
        return f.file.class_named("TPad").read(
            chunk, cursor, {"breadcrumbs": (), "in_TBranch": False}, f.file, f.file.detached, None)
    finally:
        ds.read_object_any = original


def split_spec(spec: str):
    """'f.root:name' -> ('f.root', 'name'); a bare file (also C:\\f.root, root://host//f.root)
    gives ('...root', None). The part before the last ':' must end in '.root' to name an object."""
    spec = str(spec)
    head, sep, key = spec.rpartition(":")
    if sep and head.lower().endswith(".root") and key:
        return head, key
    return spec, None


_DRAWABLE = ("TH1", "TH2", "TProfile", "TGraph", "TCanvas", "RooPlot")


def _open_keyed(spec: str):
    """Open 'file.root:name' and return (object, actual key).

    If the name is not in the file but the file holds exactly one drawable object, that object is used and
    a note says so; otherwise the error lists close matches."""
    import difflib
    import warnings

    path, key = split_spec(spec)
    if key is None:
        raise ValueError(f"expected 'file.root:object', got '{spec}'")
    try:
        f = uproot.open(path)
    except FileNotFoundError:
        raise
    except (OSError, ValueError) as e:
        raise ValueError(f"'{path}' is not a readable ROOT file ({e})") from None
    with f:
        try:
            obj = f[key]
        except (KeyError, uproot.KeyInFileError):
            names = [k.split(";")[0] for k in f.keys()]
            drawable = [k.split(";")[0] for k, c in f.classnames().items() if c.startswith(_DRAWABLE)]
            if len(drawable) == 1:
                key = drawable[0]
                warnings.warn(f"'{split_spec(spec)[1]}' not found in {path}; using the only object in the file: "
                              f"'{key}'. (Plot a whole file with just the file name.)", stacklevel=3)
                obj = f[key]
            else:
                near = difflib.get_close_matches(key, names, n=3, cutoff=0.5)
                hint = f"; did you mean {', '.join(repr(n) for n in near)}?" if near else ""
                shown = ", ".join(repr(n) for n in drawable[:8]) + (" ..." if len(drawable) > 8 else "")
                raise KeyError(f"'{key}' not found in {path}{hint} (the file holds: {shown or 'nothing drawable'}; "
                               f"list them with `figuratively ls {path}`)") from None
        if getattr(obj, "classname", "") == "TCanvas" and "fPrimitives" not in _members(obj):
            try:
                obj = _canvas_fallback(f, key)
            except Exception as e:  # uproot internals differ between versions
                raise RuntimeError(
                    f"could not read canvas '{key}' with uproot {uproot.__version__} ({type(e).__name__}: {e}). "
                    "Workaround: save the RooPlot/histograms themselves instead of the canvas, or report "
                    "this with your uproot version.") from e
        return obj, key


def _open(spec: str):
    return _open_keyed(spec)[0]


def load(spec):
    """Load 'file.root:path/to/hist' (or pass through an H1/H2/G)."""
    if isinstance(spec, (H1, H2, G)):
        return spec
    obj = _open(spec)
    c = convert(obj)
    if c is None:
        raise TypeError(f"'{spec}' is a {obj.classname}; use load_all() for canvases/RooPlots")
    return c


def load_all(spec) -> dict:
    """Every drawable object inside a canvas/RooPlot, keyed by its ROOT name."""
    out: dict = {}
    for c in expand(_open(spec) if isinstance(spec, str) else spec):
        key, n = c.name or type(c).__name__, 1
        while key in out:
            n += 1
            key = f"{c.name}_{n}"
        out[key] = c
    return out


def list_objects(path: str) -> dict:
    """{object path: ROOT class} for everything in a file."""
    with uproot.open(path) as f:
        return {k.split(";")[0]: v for k, v in f.classnames().items()}


def scale_x(obj, f: float):
    """Multiply the x axis of a histogram or graph by f (unit conversion, e.g. MeV -> GeV)."""
    if isinstance(obj, H1):
        return replace(obj, edges=obj.edges * f)
    if isinstance(obj, H2):
        return replace(obj, xedges=obj.xedges * f)
    return replace(obj, x=obj.x * f, exl=obj.exl * abs(f), exh=obj.exh * abs(f))


def mask_window(obj, lo: float, hi: float):
    """Remove data in [lo, hi]: graph points are dropped, histogram bins become NaN."""
    if isinstance(obj, H1):
        m = (obj.centers >= lo) & (obj.centers <= hi)
        v, e = obj.values.copy(), obj.errors.copy()
        v[m] = np.nan
        e[m] = np.nan
        return replace(obj, values=v, errors=e)
    if isinstance(obj, G):
        k = ~((obj.x >= lo) & (obj.x <= hi))
        return replace(obj, x=obj.x[k], y=obj.y[k], exl=obj.exl[k], exh=obj.exh[k],
                       eyl=obj.eyl[k], eyh=obj.eyh[k])
    return obj


def blank_window(obj, lo: float, hi: float):
    """Blank (NaN) the values inside [lo, hi] while keeping the arrays aligned (used to hide curves)."""
    if isinstance(obj, H1):
        m = (obj.centers >= lo) & (obj.centers <= hi)
        v, e = obj.values.copy(), obj.errors.copy()
        v[m] = np.nan
        e[m] = np.nan
        return replace(obj, values=v, errors=e)
    if isinstance(obj, G):
        m = (obj.x >= lo) & (obj.x <= hi)
        y, a, b = obj.y.copy(), obj.eyl.copy(), obj.eyh.copy()
        y[m] = np.nan
        a[m] = np.nan
        b[m] = np.nan
        return replace(obj, y=y, eyl=a, eyh=b)
    return obj

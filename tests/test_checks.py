"""Safeguards: pad attributes, sanity checks, summaries, pull conventions, silent-normalisation warnings."""
import dataclasses
import warnings

import numpy as np
import pytest
from _toy import histogram_file, roofit_frame

import figuratively as fg
from figuratively import data as D
from figuratively.checks import panel_numbers


@pytest.fixture(scope="module")
def frame():
    return roofit_frame()


def scaled(frame, factor):
    return {k: (dataclasses.replace(o, y=o.y * factor) if o.classname == "RooCurve" else o) for k, o in frame.items()}


# ------------------------------------------------------------------ what the canvas says
class FakeObj:
    def __init__(self, classname, members=None, axis_edges=None):
        self.classname, self.all_members, self._edges = classname, members or {}, axis_edges

    def member(self, name):
        if name == "fPrimitives":
            return self.prims
        if name in self.all_members:
            return self.all_members[name]
        raise KeyError(name)

    def axis(self, i):
        outer = self
        return type("Ax", (), {"edges": lambda s: outer._edges, "member": lambda s, n: ""})()


def test_pad_attributes_are_read_and_skipped_objects_listed():
    frame_hist = FakeObj("TH1D", {"fName": "frame_abc"}, axis_edges=np.array([1750.0, 1850.0, 1950.0]))
    legend = FakeObj("TLegend", {"fName": "leg"})
    pad = FakeObj("TPad", {"fName": "p", "fLogy": 1, "fLogx": 0})
    pad.prims = [frame_hist, legend, legend]
    ((name, items, texts),) = [(n, i, t) for n, i, t in D.leaf_pads(pad)] or [("p", {}, D.Texts())]
    # a pad with no data is not a panel; read its attributes directly
    items, texts = D._direct(pad)
    assert texts.attrs["logy"] is True and texts.attrs["logx"] is False
    assert texts.attrs["xrange"] == (1750.0, 1950.0)
    assert texts.attrs["skipped"] == ["TLegend", "TLegend"]


def test_plot_applies_canvas_settings_and_reports_skipped(frame):
    attrs = {"logy": True, "logx": False, "xrange": (1750.0, 1950.0), "skipped": ["TLegend", "TLegend", "TPaveStats"]}
    with pytest.warns(UserWarning, match=r"not drawn: TLegend x2, TPaveStats"):
        p = fg.plot(frame, save=False, _texts=D.Texts(["bin 1"], attrs))
    p.draw()
    assert p.ax.get_yscale() == "log" and p.ax.get_xlim() == pytest.approx((1750, 1950))
    q = fg.plot(frame, save=False, logy=False, xlim=(1700, 2000), _texts=D.Texts([], {"logy": True, "xrange": (1750, 1950)}))
    q.draw()                                    # the call wins over the canvas
    assert q.ax.get_yscale() == "linear" and q.ax.get_xlim() == pytest.approx((1700, 2000))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fg.plot(frame, save=False, checks=False, _texts=D.Texts([], {"skipped": ["TLegend"]}))


# ------------------------------------------------------------------ sanity checks
def test_a_consistent_fit_passes_quietly(frame):
    n = panel_numbers(frame, nparams=10)
    assert abs(n["ratio"] - 1) < 0.03 and not n["warnings"]
    assert n["ndf"] == n["used"] - 10 and set(n["components"]) >= {"sig", "comb"}


def test_a_mis_scaled_curve_is_caught(frame):
    bad = scaled(frame, 1.3)
    assert any("normalisation" in w for w in panel_numbers(bad)["warnings"])
    with pytest.warns(UserWarning, match="disagree in normalisation"):
        fg.plot(bad, save=False)
    with pytest.raises(ValueError, match="disagree in normalisation"):
        fg.plot(bad, save=False, strict=True)


def test_large_pulls_are_flagged_and_the_pull_panel_grows(frame):
    bad = scaled(frame, 1.3)
    assert any("|pull| above 5" in w for w in panel_numbers(bad)["warnings"])
    with pytest.warns(UserWarning):
        p = fg.plot(bad, save=False)
    p.draw()
    assert p.rax.get_ylim()[1] > 5                     # no solid blocks at +-5
    q = fg.plot(frame, save=False)
    q.draw()
    assert q.rax.get_ylim() == pytest.approx((-5, 5))  # normal fits keep +-5


def test_check_and_summary(frame, capsys):
    rows = fg.check(frame, nparams=10)
    out = capsys.readouterr().out
    assert len(rows) == 1 and "chi2/ndf" in out and "empty bins" in out
    from figuratively import checks

    monkey = lambda spec: ("toy", [(frame, ["bin 1"]), (scaled(frame, 1.0), ["bin 2"])])
    orig, orig_expand = checks._panels, checks._expand
    checks._panels, checks._expand = monkey, lambda spec: [spec]
    try:
        t = fg.summary("toy.root", nparams=10, show=False)
        csv = fg.summary("toy.root", nparams=10, fmt="csv", show=False)
        tex = fg.summary("toy.root", fmt="latex", show=False)
        with pytest.raises(ValueError, match="fmt must be"):
            fg.summary("toy.root", fmt="xml", show=False)
    finally:
        checks._panels, checks._expand = orig, orig_expand
    assert t.splitlines()[0].split()[:4] == ["file", "panel", "label", "entries"] and "chi2/ndf" in t
    assert csv.splitlines()[0].startswith("file,panel,label,entries,chi2/ndf,sig") and len(csv.splitlines()) == 3
    assert r"\begin{tabular}" in tex and r"\hline" in tex and "bkg\\_a" in tex


# ------------------------------------------------------------------ pull conventions
def test_pulls_follow_roofit_by_default_and_centre_on_request():
    steep = roofit_frame(nb=40)
    p = fg.plot(steep, save=False)
    q = fg.plot(steep, save=False, pull={"mode": "centre"})
    p.draw(); q.draw()
    bars = lambda plot: np.array([b.get_height() for b in plot.rax.patches])
    assert np.max(np.abs(bars(p) - bars(q))) > 0.2     # the conventions differ on a steep, coarsely binned peak
    with pytest.raises(ValueError, match="pull mode"):
        fg.plot(steep, save=False, pull={"mode": "average"})


# ------------------------------------------------------------------ silent behaviour made visible
def test_automatic_normalisation_is_announced(tmp_path):
    f = histogram_file(str(tmp_path / "t.root"))
    with pytest.warns(UserWarning, match="normalised to unit area"):
        fg.plot(f"{f}:data", f"{f}:mc", save=False)
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        fg.plot(f"{f}:data", f"{f}:mc", save=False, normalise=True)      # decided by the user: no warning


def test_blind_window_with_visible_curves_warns(frame):
    with pytest.warns(UserWarning, match="model curves are still drawn"):
        fg.plot(frame, save=False, blind=(1850, 1880))
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        fg.plot(frame, save=False, blind=(1850, 1880), blind_curves=True)


def test_text_follows_an_explicit_figure_width(frame):
    big, small = fg.plot(frame, save=False), fg.plot(frame, save=False, size=(5, 4))
    big.draw(); small.draw()
    assert small.ax.yaxis.label.get_fontsize() < 0.6 * big.ax.yaxis.label.get_fontsize()


# ------------------------------------------------------------------ the checks must not cry wolf
def test_low_statistics_noise_is_not_a_warning():
    from _toy import roofit_frame as rf

    tiny = rf(nb=33)                                   # then thin the data to about 80 entries in total
    data = next(o for o in tiny.values() if o.classname == "RooHist")
    rng = np.random.default_rng(2)
    mod = np.interp(data.x, next(o for k, o in tiny.items() if k == "model_Norm[m]").x,
                    next(o for k, o in tiny.items() if k == "model_Norm[m]").y)
    k = 80 / mod.sum()
    for key, o in list(tiny.items()):
        if o.classname == "RooCurve":
            tiny[key] = dataclasses.replace(o, y=o.y * k)
    y = rng.poisson(mod * k).astype(float)
    tiny[next(kk for kk, o in tiny.items() if o.classname == "RooHist")] = dataclasses.replace(
        data, y=y, eyl=np.where(y > 0, np.sqrt(y), 1.84), eyh=np.where(y > 0, np.sqrt(y), 1.84))
    n = panel_numbers(tiny, nparams=5)
    assert not n["warnings"], n["warnings"]            # a 5-10 % wobble on ~80 entries is just Poisson
    assert any("low statistics" in note for note in n["notes"])


def test_far_too_many_empty_bins_still_warn(frame):
    data = next(o for o in frame.values() if o.classname == "RooHist")
    zeros = dataclasses.replace(data, y=np.where(np.arange(len(data.y)) % 2 == 0, 0.0, data.y))
    broken = {k: (zeros if o is data else o) for k, o in frame.items()}
    assert any("bins are empty, but the curve predicts" in w for w in panel_numbers(broken)["warnings"])


def test_check_and_summary_accept_a_bare_file(tmp_path):
    f = histogram_file(str(tmp_path / "t.root"))         # histograms only: no canvases, nothing to check
    assert fg.check(f) == []                              # no canvases in it: nothing to check, and no crash
    assert fg.summary(f, show=False).split()[:4] == ["file", "panel", "label", "entries"]

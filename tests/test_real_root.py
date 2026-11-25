"""Regressions found with real ROOT. CI has no ROOT, so these read data/roofit_toy.root, a toy-data file
written by ROOT with data/make_roofit_toy.py."""
import shutil
import warnings
from pathlib import Path

import numpy as np
import pytest
import uproot

import figuratively as fg
from figuratively import data as D
from figuratively.cli import main

FIXTURE = Path(__file__).parent / "data" / "roofit_toy.root"


@pytest.fixture
def toy(tmp_path):
    return shutil.copy(FIXTURE, tmp_path / "roofit_toy.root")


def labels(plot):
    return sorted(s.label for s in plot.series)


def total_name(plot):
    return next(s.obj.name for s in plot.series if s.label == "Total fit")


# ------------------------------------------------------------------ canvases beside a RooPlot
@pytest.mark.parametrize("key", ["c_auto", "c_named"])
def test_canvas_reads_when_the_file_also_holds_rooplots(toy, key):
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*unreadable.*")
        p = fg.plot(f"{toy}:{key}", save=False)
    assert len(p.series) == 4


# ------------------------------------------------------------------ components named with RooFit.Name()
def test_custom_named_components_are_drawn(toy):
    p = fg.plot(f"{toy}:c_named", save=False)
    assert labels(p) == ["Data", "Total fit", "background", "signal"]
    assert total_name(p) == "total"


def test_custom_names_work_in_options_checks_and_inspect(toy):
    p = fg.plot(f"{toy}:c_named", save=False, strict=False, labels={"signal": "S"},
                components={"background": "dotted"}, hide=["signal"])
    assert labels(p) == ["Data", "Total fit", "background"]
    panel = fg.check(f"{toy}:c_named", show=False)[0]
    assert set(panel["components"]) == {"signal", "background"}
    assert [c["name"] for c in D_inspect(f"{toy}:c_named")] == ["signal", "background"]


def D_inspect(spec):
    from figuratively.explore import _frame_info

    return _frame_info(D.load_all(spec))[2]


def test_hiding_the_total_does_not_promote_a_component(toy):
    with pytest.warns(UserWarning, match="pull panel skipped"):
        p = fg.plot(f"{toy}:c_named", save=False, hide=["^total$"])
    assert labels(p) == ["Data", "background", "signal"]


def test_automatic_roofit_names_are_unchanged(toy):
    p = fg.plot(f"{toy}:c_auto", save=False)
    assert labels(p) == ["Data", "Total fit", "bkg", "sig"]
    assert total_name(p) == "model_Norm[x]"


# ------------------------------------------------------------------ error bands
def test_error_band_is_not_mistaken_for_the_total(toy):
    with pytest.warns(UserWarning, match="error bands are not drawn"):
        p = fg.plot(f"{toy}:c_band", save=False)
    assert total_name(p) == "model_Norm[x]"
    assert labels(p) == ["Data", "Total fit", "bkg", "sig"]
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*error bands.*")
        fg.plot(f"{toy}:c_band", save=False, hide=["errorband"])


# ------------------------------------------------------------------ a RooPlot saved directly
def test_saved_rooplot_matches_the_canvas(toy):
    frame, canvas = D.load_all(f"{toy}:frame"), D.load_all(f"{toy}:c_auto")
    assert list(frame) == list(canvas)
    for key in frame:
        assert len(frame[key].x) > 1
    p = fg.plot(f"{toy}:frame", save=False)
    assert labels(p) == ["Data", "Total fit", "bkg", "sig"]
    assert np.isclose(D.load_all(f"{toy}:frame")["h_modelData"].y.sum(), 3000, atol=200)


def test_saved_rooplot_leaves_out_invisible_curves(toy):
    assert list(D.load_all(f"{toy}:frame_named")) == ["h_modelData", "total", "signal", "background"]


def test_rooplot_in_a_subfolder_with_a_parameter_box(toy):
    p = fg.plot(f"{toy}:fits/with_params", save=False)
    assert labels(p) == ["Data", "Total fit", "bkg", "sig"]
    assert len(fg.check(f"{toy}:fits/with_params", show=False)) == 1


def test_empty_rooplot_gives_a_clear_error(toy):
    with pytest.raises(ValueError, match="nothing to draw"):
        fg.plot(f"{toy}:frame_empty", save=False)


def test_damaged_rooplot_gives_a_clear_error(toy, monkeypatch):
    monkeypatch.setattr(D, "_rooplot_fallback", lambda f, k: (_ for _ in ()).throw(ValueError("boom")))
    with pytest.raises(RuntimeError, match="could not read RooPlot"):
        D.load_all(f"{toy}:frame")


def test_whole_file_mode_includes_the_rooplots(toy, tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fg.plot(str(toy), outdir=str(tmp_path / "all"), formats=("png",))
    made = sorted(p.name for p in (tmp_path / "all").glob("*.png"))
    assert len(made) == 7, made  # every object except the empty frame


# ------------------------------------------------------------------ scale_x on a canvas
@pytest.mark.parametrize("key", ["c_auto", "frame"])
def test_scale_x_scales_the_canvas_range_with_the_data(toy, key):
    p = fg.plot(f"{toy}:{key}", save=False, scale_x=1e-3, unit="GeV")
    _fig, ax, _rax = p.draw()
    assert ax.get_xlim() == pytest.approx((1.75, 1.98), abs=0.01)
    lo, hi = ax.get_xlim()
    data = next(s.obj for s in p.series if s.label == "Data")
    assert ((data.x >= lo) & (data.x <= hi)).all()


def test_a_negative_scale_keeps_the_range_in_order(toy):
    _fig, ax, _rax = fg.plot(f"{toy}:c_auto", save=False, scale_x=-1.0, unit="MeV").draw()
    assert ax.get_xlim() == pytest.approx((-1980, -1750))


def test_an_explicit_xlim_is_taken_in_the_new_units(toy):
    _fig, ax, _rax = fg.plot(f"{toy}:c_auto", save=False, scale_x=1e-3, unit="GeV", xlim=(1.8, 1.9)).draw()
    assert ax.get_xlim() == pytest.approx((1.8, 1.9))


# ------------------------------------------------------------------ strict= on an ordinary RooFit canvas
@pytest.mark.parametrize("key", ["c_auto", "c_named"])
def test_strict_accepts_a_correct_roofit_canvas(toy, key):
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*not drawn.*")
        fg.plot(f"{toy}:{key}", save=False, strict=True)


def test_strict_reports_a_misspelt_component_with_a_suggestion(toy):
    with pytest.raises(ValueError, match="did you mean 'sig'"):
        fg.plot(f"{toy}:c_auto", save=False, strict=True, labels={"sgi": "x"})


class _Line:
    def __init__(self, text):
        self.text = text

    def member(self, _name):
        return self.text


class _Box:
    def __init__(self, name, lines=()):
        self.members = {"fName": name, "fLines": [_Line(t) for t in lines]}

    def member(self, name):
        return self.members[name]


def test_only_what_root_adds_by_itself_is_ignored():
    assert D._added_by_root(_Box("title", ['A RooPlot of "x"']), "TPaveText")
    assert D._added_by_root(_Box("ListOfColors"), "TObjArray")
    assert not D._added_by_root(_Box("title", ["My own title"]), "TPaveText")
    assert not D._added_by_root(_Box("model_paramBox", ["mean = 1865"]), "TPaveText")
    assert not D._added_by_root(_Box("mine"), "TObjArray")


# ------------------------------------------------------------------ which curve is the total
def _curve(name, height):
    x = np.linspace(0.0, 1.0, 20)
    z = np.zeros_like(x)
    return D.G(x, np.full_like(x, height), z, z, z, z, name, classname="RooCurve")


def test_total_is_the_largest_curve_whatever_the_order():
    items = {n: _curve(n, h) for n, h in (("part", 1.0), ("everything", 5.0), ("rest", 4.0))}
    assert D.roofit_curves(items) == ("everything", {"part": "part", "rest": "rest"}, [])


def test_of_equal_curves_the_first_is_the_total():
    items = {n: _curve(n, 3.0) for n in ("nominal", "alternative")}
    assert D.roofit_curves(items) == ("nominal", {"alternative": "alternative"}, [])


# ------------------------------------------------------------------ figly tree file names
def test_tree_expression_with_a_slash_writes_one_file_not_a_folder(tmp_path, monkeypatch):
    path = tmp_path / "t.root"
    with uproot.recreate(path) as f:
        f["T"] = {"pt": np.arange(100.0)}
    monkeypatch.chdir(tmp_path)
    main(["tree", f"{path}:T", "pt/1000"])
    assert (tmp_path / "plots" / "t_pt_over_1000.png").exists()
    assert not [p for p in (tmp_path / "plots").iterdir() if p.is_dir()]

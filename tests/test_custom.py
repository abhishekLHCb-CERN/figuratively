"""Tests for the customisation layer: every option is documented, wired and typo-safe."""
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest
from _toy import histogram_file, roofit_frame

import figuratively as fg
from figuratively import auto
from figuratively.options import BY_NAME, OPTIONS

README = (Path(__file__).resolve().parents[1] / "README.md").read_text()


@pytest.fixture(scope="module")
def frame():
    return roofit_frame()


@pytest.fixture(scope="module")
def hist_file(tmp_path_factory):
    return histogram_file(str(tmp_path_factory.mktemp("h") / "toy.root"))


@pytest.fixture
def clean_config():
    saved, loaded = dict(auto.CONFIG), auto._state["loaded"]
    yield
    auto.CONFIG.clear()
    auto.CONFIG.update(saved)
    auto._state["loaded"] = loaded


def texts(p):
    fig, _, _ = p.draw()
    return [t.get_text() for t in fig.findobj(plt.Text)]


# ------------------------------------------------------------------ registry
def test_registry_is_complete():
    assert len({o.name for o in OPTIONS}) == len(OPTIONS)
    for o in OPTIONS:
        assert o.doc and len(o.doc) > 8, o.name
        assert o.ctx in ("fit", "hist", "any")


def test_readme_option_tables_match_registry():
    from figuratively.options import options_markdown

    block = README.split("<!-- options:start -->")[1].split("<!-- options:end -->")[0]
    assert block.strip() == options_markdown().strip(), "run: python tools/update_readme.py"


@pytest.mark.parametrize("opt", OPTIONS, ids=lambda o: o.name)
def test_every_option_is_wired(opt, frame, hist_file, tmp_path):
    spec = frame if opt.ctx in ("fit", "any") else [f"{hist_file}:data", f"{hist_file}:mc"]
    specs = [spec] if not isinstance(spec, list) else spec
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        p = fg.plot(*specs, out=tmp_path / "o.png", **{opt.name: opt.example})
        p.draw()
    bad = [str(x.message) for x in w if "matches no component" in str(x.message) or "unknown" in str(x.message)]
    assert not bad, bad
    p.close()


# ------------------------------------------------------------------ typos
def test_unknown_option_suggests(frame):
    with pytest.raises(TypeError, match="did you mean 'logy'"):
        fg.plot(frame, save=False, lgy=True)


def test_component_typo_warns_with_suggestion(frame):
    with pytest.warns(UserWarning, match="did you mean 'sig'"):
        fg.plot(frame, save=False, labels={"sgi": "x"})
    with pytest.raises(ValueError, match="matches no component"):
        fg.plot(frame, save=False, labels={"sgi": "x"}, strict=True)


def test_hide_regex_matching_nothing_warns(frame):
    with pytest.warns(UserWarning, match="hide"):
        fg.plot(frame, save=False, hide=["zzz"])


def test_alias_conflict(frame):
    with pytest.raises(TypeError, match="same thing"):
        fg.plot(frame, save=False, xlim=(1, 2), xrange=(1, 2))


def test_configure_unknown_key_suggests():
    with pytest.raises(KeyError, match="did you mean 'label'"):
        fg.configure(lable="x")


# ------------------------------------------------------------------ component styling
def test_style_grammar():
    assert auto.parse_style("red dashed fill thick") == {
        "color": "red", "linestyle": "--", "kind": "fill", "linewidth": 3.0}
    assert auto.parse_style({"style": "fill", "ls": ":", "lw": 2, "hatch": "//"}) == {
        "kind": "fill", "linestyle": ":", "linewidth": 2, "hatch": "//"}
    with pytest.raises(ValueError, match="did you mean 'red'"):
        auto.parse_style("reed dashed")


def test_components_applied_and_globs(frame):
    p = fg.plot(frame, save=False, components={"sig": "red dashed", "bkg*": {"alpha": 0.3, "label": "Bkg"}})
    by_label = {s.label: s for s in p.series}
    assert by_label["sig"].color == "red" and by_label["sig"].style["linestyle"] == "--"
    assert {s.label for s in p.series if s.label == "Bkg"} == {"Bkg"}
    assert sum(1 for s in p.series if s.label == "Bkg") == 3  # the three bkg_* components


def test_merge_sums_components(frame):
    p = fg.plot(frame, save=False, merge={"Backgrounds": ["comb", "bkg*"]})
    labels = [s.label for s in p.series]
    assert "Backgrounds" in labels and not {"comb", "bkg_a", "bkg_b", "bkg_c"} & set(labels)
    merged = next(s for s in p.series if s.label == "Backgrounds").obj
    parts = [o for k, o in frame.items() if "Comp[comb]" in k or "Comp[bkg" in k]
    x0 = 1865.0
    assert merged.y[np.argmin(abs(merged.x - x0))] == pytest.approx(
        sum(float(np.interp(x0, o.x, o.y)) for o in parts), rel=1e-2)


def test_order_and_hatch(frame):
    p = fg.plot(frame, save=False, order=["comb", "sig"], components={"comb": {"style": "fill", "hatch": "//"}})
    labels = [s.label for s in p.series if s.label in ("comb", "sig")]
    assert labels == ["comb", "sig"]
    p.draw()


# ------------------------------------------------------------------ regions and lines
def test_blind_masks_data_and_pulls(frame):
    p = fg.plot(frame, save=False, blind=(1840, 1890))
    data = next(s.obj for s in p.series if s.kind == "points")
    assert not ((data.x >= 1840) & (data.x <= 1890)).any()
    p.draw()
    assert any(getattr(a, "get_hatch", lambda: None)() == "////" for a in p.ax.patches)
    assert "Blinded" in texts(p)


def test_blind_on_histograms_keeps_limits_finite(hist_file):
    p = fg.plot(f"{hist_file}:data", f"{hist_file}:mc", save=False, blind=[(1860, 1870)])
    p.draw()
    assert np.isfinite(p.ax.get_ylim()).all()


def test_labelled_lines_and_lists(frame):
    p = fg.plot(frame, save=False, vline=[1865, (1840, "cut")], span=(1850, 1880, "signal"), hline=(100, "thr"))
    t = texts(p)
    assert {"cut", "signal", "thr"} <= set(t)
    assert sum(1 for line in p.ax.lines if line.get_xdata()[0] in (1865, 1840) and len(line.get_xdata()) == 2) >= 2


# ------------------------------------------------------------------ figure
def test_size_presets_scale_text(frame):
    big = fg.plot(frame, save=False)
    small = fg.plot(frame, save=False, size="column")
    big.draw(); small.draw()
    assert tuple(small.fig.get_size_inches()) == pytest.approx((3.4, 2.8))
    assert small.ax.yaxis.label.get_fontsize() < 0.6 * big.ax.yaxis.label.get_fontsize()
    with pytest.raises(ValueError, match="did you mean 'column'"):
        fg.plot(frame, save=False, size="colum")


def test_legend_forms(frame):
    off = fg.plot(frame, save=False, legend=False)
    off.draw()
    assert off.ax.get_legend() is None
    loc = fg.plot(frame, save=False, legend="lower left")
    loc.draw()
    assert loc.ax.get_legend() is not None


def test_scale_x_changes_axis(frame):
    p = fg.plot(frame, save=False, scale_x=1e-3, unit="GeV")
    p.draw()
    assert p.ax.get_xlim()[1] < 3
    with pytest.warns(UserWarning, match="scale_x"):
        fg.plot(frame, save=False, scale_x=1e-3)


def test_log_alias_and_figsize_alias(frame):
    p = fg.plot(frame, save=False, log="y", figsize=(6, 5))
    p.draw()
    assert p.ax.get_yscale() == "log" and tuple(p.fig.get_size_inches()) == pytest.approx((6, 5))


def test_dpi_and_transparent_reach_savefig(frame, tmp_path):
    fg.plot(frame, out=tmp_path / "lo.png", dpi=40)
    fg.plot(frame, out=tmp_path / "hi.png", dpi=160)
    assert (tmp_path / "hi.png").stat().st_size > 2 * (tmp_path / "lo.png").stat().st_size


# ------------------------------------------------------------------ config, inspect, init
def test_toml_config_is_found_and_used(tmp_path, monkeypatch, clean_config):
    (tmp_path / "figuratively.toml").write_text('label = "Draft"\nunit = "MeV"\n[labels]\nsig = "Signal"\n')
    monkeypatch.chdir(tmp_path)
    found = auto.load_config()
    assert found == tmp_path / "figuratively.toml"
    assert auto.CONFIG["label"] == "Draft" and auto.CONFIG["labels"]["sig"] == "Signal"


def test_toml_unknown_key_warns(tmp_path, clean_config):
    f = tmp_path / "figuratively.toml"
    f.write_text('lable = "x"\n')
    with pytest.warns(UserWarning, match="did you mean 'label'"):
        auto.load_config(f)


def test_inspect_lists_components_and_call(frame):
    info = fg.inspect(frame, show=False)
    names = [c["name"] for c in info["components"]]
    assert names == ["sig", "tail", "comb", "bkg_a", "bkg_b", "bkg_c"]
    assert 'labels={"sig": "sig"' in info["call"]
    assert info["components"][0]["share"] > 0.1


def test_init_writes_and_roundtrips(frame, tmp_path, clean_config):
    f = fg.init(frame, tmp_path / "figuratively.toml")
    assert "[labels]" in f.read_text() and 'sig = "sig"' in f.read_text()
    with pytest.raises(FileExistsError):
        fg.init(frame, f)
    fg.init(frame, f, force=True)
    auto.load_config(f)
    assert auto.CONFIG["labels"]["comb"] == "comb"


def test_options_listing(capsys):
    rows = fg.options()
    out = capsys.readouterr().out
    assert len(rows) == len(OPTIONS) and "merge" in out and "[components]" in out
    assert BY_NAME["blind"].group == "annotations"

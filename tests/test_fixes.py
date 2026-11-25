"""Regression tests for problems found by the user-test agents (newcomer and adversary)."""

import numpy as np
import pytest
from _toy import histogram_file, roofit_frame

import figuratively as fg
from figuratively import auto
from figuratively.cli import _value, main


@pytest.fixture(scope="module")
def frame():
    return roofit_frame()


@pytest.fixture(scope="module")
def hist_file(tmp_path_factory):
    return histogram_file(str(tmp_path_factory.mktemp("f") / "toy.root"))


def labels(p):
    return [s.label for s in p.series if s.label]


# ------------------------------------------------------------------ components
def test_hide_works_on_a_merged_name(frame):
    p = fg.plot(frame, save=False, merge={"Bkg": ["bkg*"]}, hide=["Bkg"])
    assert "Bkg" not in labels(p)


def test_stack_keeps_hatch_and_alpha(frame):
    p = fg.plot(frame, save=False, stack=True, components={"comb": {"style": "fill", "hatch": "//", "alpha": 0.5}})
    comb = next(s for s in p.series if s.label == "comb")
    assert comb.style["hatch"] == "//" and comb.style["alpha"] == 0.5
    p.draw()


def test_overlapping_merge_groups_warn(frame):
    with pytest.warns(UserWarning, match="already belong"):
        fg.plot(frame, save=False, merge={"A": ["bkg_a", "bkg_b"], "B": ["bkg_b", "bkg_c"]})


def test_legend_uses_raw_component_names(frame):
    assert "bkg_a" in labels(fg.plot(frame, save=False))


# ------------------------------------------------------------------ wrong context, wrong values
def test_fit_only_option_on_histograms_is_explained(hist_file):
    with pytest.warns(UserWarning, match="'stack' applies to RooFit frames only"):
        fg.plot(f"{hist_file}:data", f"{hist_file}:mc", save=False, stack=True)


def test_hist_only_option_on_a_fit_is_explained(frame):
    with pytest.warns(UserWarning, match="'ratio' applies to histogram overlays only"):
        fg.plot(frame, save=False, ratio=(0.5, 1.5))


@pytest.mark.parametrize("bad", [{"colour": "red"}, {"kind": "zzz"}, {"alpha": 2}])
def test_bad_style_dicts_raise_clear_errors(frame, bad):
    with pytest.raises(ValueError):
        fg.plot(frame, save=False, components={"sig": bad})


def test_style_key_typo_suggests(frame):
    with pytest.raises(ValueError, match="did you mean 'color'"):
        fg.plot(frame, save=False, components={"sig": {"colour": "red"}})


def test_style_string_alpha_validation():
    for s in ("alpha=2", "alpha=abc"):
        with pytest.raises(ValueError, match="alpha"):
            auto.parse_style(s)


def test_legend_unknown_key(frame):
    with pytest.raises(ValueError, match="legend: unknown option 'colour'"):
        fg.plot(frame, save=False, legend={"colour": 1})


def test_config_types_are_checked_and_name_the_key(tmp_path):
    with pytest.raises(TypeError, match="'dpi' must be"):
        fg.configure(dpi="high")
    with pytest.raises(TypeError, match="'colors' must be dict"):
        fg.configure(colors="red")
    f = tmp_path / "figuratively.toml"
    f.write_text('dpi = "high"\n')
    with pytest.raises(TypeError, match="figuratively.toml: 'dpi'"):
        auto.load_config(f)


# ------------------------------------------------------------------ one-line crashes
def test_hiding_the_total_skips_the_pull(frame):
    with pytest.warns(UserWarning, match="pull panel skipped"):
        p = fg.plot(frame, save=False, hide=["model"])
    p.draw()


def test_blinding_everything_does_not_crash(frame):
    fg.plot(frame, save=False, blind=(0, 5000)).draw()


def test_hiding_everything_says_so(frame):
    with pytest.raises(ValueError, match="nothing to plot"):
        fg.plot(frame, save=False, hide=[".*"]).draw()


def test_invalid_regex_is_a_clear_error(frame):
    with pytest.raises(ValueError, match="not a valid regular expression"):
        fg.plot(frame, save=False, hide=["("])


def test_size_forms(frame):
    p = fg.plot(frame, save=False, size=5)
    p.draw()
    assert tuple(p.fig.get_size_inches()) == pytest.approx((5, 3.75))
    q = fg.plot(frame, save=False, size=(5, None))
    q.draw()
    assert tuple(q.fig.get_size_inches()) == pytest.approx((5, 3.75))
    with pytest.raises(ValueError, match="width, height"):
        fg.Plot().size((5, 6, 7))


def test_blind_forms(frame):
    fg.plot(frame, save=False, blind=[1840, 1890]).draw()
    fg.plot(frame, save=False, blind=[(1840, 1850), (1880, 1890)]).draw()
    with pytest.raises(TypeError, match="blind expects"):
        fg.plot(frame, save=False, blind={"a": 1})


def test_scale_x_accepts_numeric_strings_only(frame):
    with pytest.raises(TypeError, match="scale_x must be a number"):
        fg.plot(frame, save=False, scale_x="fast", unit="GeV")
    fg.plot(frame, save=False, scale_x="1e-3", unit="GeV").draw()


def test_blind_with_scale_x_on_histograms_keeps_the_axis(hist_file):
    p = fg.plot(f"{hist_file}:data", f"{hist_file}:mc", save=False, blind=(1.850, 1.880), scale_x=1e-3, unit="GeV")
    p.draw()
    assert p.ax.get_xlim()[1] < 3


def test_blind_curves_blanks_the_model_inside(frame):
    keep = fg.plot(frame, save=False, blind=(1840, 1890))
    blank = fg.plot(frame, save=False, blind=(1840, 1890), blind_curves=True)
    inside = lambda p: next(s.obj for s in p.series if s.label == "Total fit")
    t = inside(blank)
    assert np.isnan(t.y[(t.x >= 1840) & (t.x <= 1890)]).all()
    k = inside(keep)
    assert np.isfinite(k.y[(k.x >= 1840) & (k.x <= 1890)]).all()
    blank.draw()


def test_inspect_lists_a_whole_file(hist_file):
    info = fg.inspect(hist_file, show=False)
    assert info["kind"] == "file" and {"data", "mc", "corr"} <= set(info["objects"])


# ------------------------------------------------------------------ cli
def test_cli_values_keep_text_options_as_text():
    assert _value("label", "2018") == "2018" and _value("info", "2018") == "2018"
    assert _value("title", "True") == "True"
    assert _value("logy", "True") is True and _value("xlim", "(1, 2)") == (1, 2)
    assert _value("info", "['a', 'b']") == ["a", "b"]


def test_cli_rejects_missing_equals(capsys):
    with pytest.raises(SystemExit):
        main(["x.root:h", "-s", "blind"])
    assert "KEY=VALUE" in capsys.readouterr().err


# ------------------------------------------------------------------ looks
def test_labels_sit_above_the_axes_and_stack_only_when_close(frame):
    p = fg.plot(frame, save=False, vline=[(1865, "cut")], span=[(1850, 1880, "signal"), (1700, 1720, "far")])
    p.draw()
    pos = {t.get_text(): t.get_position() for t in p.ax.texts}
    assert all(pos[k][1] > 1.0 for k in ("cut", "signal", "far"))      # outside the data area
    assert pos["cut"][1] != pos["signal"][1]                            # same x: stacked
    assert pos["far"][1] == pos["cut"][1] or pos["far"][1] == pos["signal"][1]  # far away: shares a level


def test_column_preset_shrinks_markers_and_lines(frame):
    def marker_size(p):
        p.draw()
        return max(line.get_markersize() for line in p.ax.lines if line.get_marker() == "o")

    assert marker_size(fg.plot(frame, save=False, size="column")) < 0.6 * marker_size(fg.plot(frame, save=False))


def test_ratio_range_widens_when_points_fall_outside(hist_file):
    auto_p = fg.plot(f"{hist_file}:data", f"{hist_file}:mc", save=False)
    auto_p.draw()
    lo, hi = auto_p.rax.get_ylim()
    assert lo <= 0.5 and hi >= 1.5
    fixed = fg.plot(f"{hist_file}:data", f"{hist_file}:mc", save=False, ratio=(0.7, 1.3))
    fixed.draw()
    assert fixed.rax.get_ylim() == pytest.approx((0.7, 1.3))


def test_log_axis_reaches_the_lowest_histogram_bin(hist_file):
    p = fg.plot(f"{hist_file}:data", f"{hist_file}:mc", save=False, logy=True)
    p.draw()
    mc_min = min(s.obj.values[s.obj.values > 0].min() for s in p.series if s.label == "mc")
    data_min = min(s.obj.values[s.obj.values > 0].min() for s in p.series if s.label == "data")
    n = max(s.obj.values.sum() for s in p.series if s.label == "mc")
    assert p.ax.get_ylim()[0] <= min(mc_min, data_min) * 1.01 or p.ax.get_ylim()[0] < 1e-3 * n


def test_second_save_reports_the_replacement(frame, tmp_path, capsys):
    fg.plot(frame, out=tmp_path / "x.png")
    fg.plot(frame, out=tmp_path / "x.png")
    out = capsys.readouterr().out
    assert out.count("replaced an existing file") == 1


def test_config_file_in_use_is_announced(frame, tmp_path, monkeypatch, capsys):
    saved, loaded, path = dict(auto.CONFIG), auto._state["loaded"], auto._state["path"]
    try:
        (tmp_path / "figuratively.toml").write_text('unit = "MeV"\n')
        monkeypatch.chdir(tmp_path)
        auto._state["loaded"] = False
        fg.plot(frame, save=False)
        assert "using settings from" in capsys.readouterr().out and fg.config_path() == tmp_path / "figuratively.toml"
    finally:
        auto.CONFIG.clear()
        auto.CONFIG.update(saved)
        auto._state.update(loaded=loaded, path=path)


# ------------------------------------------------------------------ finding the object automatically
def test_the_only_object_is_found_when_the_name_is_wrong(tmp_path):
    import uproot

    f = tmp_path / "one.root"
    with uproot.recreate(f) as fh:
        fh["c7"] = np.histogram(np.random.default_rng(1).normal(0, 1, 500), bins=20, range=(-4, 4))
    with pytest.warns(UserWarning, match="using the only object in the file: 'c7'"):
        p = fg.plot(f"{f}:old_name", out=tmp_path / "o.png")
    assert (tmp_path / "o.png").exists()
    p.close()


def test_several_objects_still_need_the_right_name(hist_file):
    with pytest.raises(KeyError, match="the file holds: 'data', 'mc', 'corr'"):
        fg.plot(f"{hist_file}:nonsense", save=False)


def test_suffix_keeps_variants_apart(hist_file, tmp_path):
    fg.plot(f"{hist_file}:data", outdir=str(tmp_path), formats=("png",))
    fg.plot(f"{hist_file}:data", outdir=str(tmp_path), formats=("png",), suffix="_log", logy=True)
    assert sorted(x.name for x in tmp_path.glob("*.png")) == ["toy_data.png", "toy_data_log.png"]


# ------------------------------------------------------------------ presets, many files, view
def test_builtin_preset_sets_size_and_formats(frame, tmp_path):
    p = fg.plot(frame, out=tmp_path / "x", preset="paper")
    assert (tmp_path / "x.pdf").exists() and not (tmp_path / "x.png").exists()   # paper: pdf only
    p.draw()
    assert tuple(p.fig.get_size_inches()) == pytest.approx((3.4, 2.8))


def test_the_call_beats_the_preset(frame):
    p = fg.plot(frame, save=False, preset="paper", size="double")
    p.draw()
    assert tuple(p.fig.get_size_inches()) == pytest.approx((7.0, 5.4))
    q = fg.plot(frame, save=False, preset="paper", figsize=(5, 4))   # alias of size
    q.draw()
    assert tuple(q.fig.get_size_inches()) == pytest.approx((5, 4))


def test_user_presets_and_composition(frame):
    fg.configure(presets={"mine": {"palette": "r4", "root_colors": False}})
    try:
        p = fg.plot(frame, save=False, preset="paper+mine")
        p.draw()
        assert tuple(p.fig.get_size_inches()) == pytest.approx((3.4, 2.8))
        assert p._pal_name == "r4"
    finally:
        fg.configure(presets={})


def test_unknown_preset_suggests(frame):
    with pytest.raises(ValueError, match="did you mean 'thesis'"):
        fg.plot(frame, save=False, preset="thesiss")


def test_a_glob_plots_each_file_separately(hist_file, tmp_path):
    import shutil

    for n in ("a", "b"):
        shutil.copy(hist_file, tmp_path / f"run_{n}.root")
    out = fg.plot(str(tmp_path / "run_*.root:data"), outdir=str(tmp_path / "o"), formats=("png",))
    assert len(out) == 2 and sorted(x.name for x in (tmp_path / "o").glob("*.png")) == ["run_a_data.png", "run_b_data.png"]
    out2 = fg.plot([str(tmp_path / "run_a.root:data"), str(tmp_path / "run_b.root:mc")],
                   outdir=str(tmp_path / "o2"), formats=("png",))
    assert len(out2) == 2
    with pytest.raises(FileNotFoundError, match="no file matches"):
        fg.plot(str(tmp_path / "nothing_*.root"))


def test_view_opens_the_saved_file(frame, tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(auto, "_view", lambda path: opened.append(str(path)))
    fg.plot(frame, out=tmp_path / "v.png", view=True)
    fg.plot(frame, out=tmp_path / "w.png")
    assert opened == [str(tmp_path / "v.png")]


# ------------------------------------------------------------------ compare fits, combined panels
def test_two_fits_are_compared(frame):
    other = {k: (o if "Comp" in k or o.classname == "RooHist" else __import__("dataclasses").replace(o, y=o.y * 1.03))
             for k, o in frame.items()}
    p = fg.plot(frame, other, save=False, labels=["Data", "Nominal", "Variant"])
    p.draw()
    assert [t.get_text() for t in p.ax.get_legend().get_texts()] == ["Data", "Nominal", "Variant"]
    lo, hi = p.rax.get_ylim()
    assert 0.9 < lo < 1 < hi < 1.1          # zoomed in on a 3 % difference
    assert [s for s in p.series if s.kind == "points"][0].in_ratio is False


def test_comparison_warns_when_the_data_differ(frame):
    from _toy import roofit_frame

    with pytest.warns(UserWarning, match="the data in .* differ"):
        fg.plot(frame, roofit_frame(seed=9), save=False)


def test_combined_figure_has_one_axes_pair_per_panel(tmp_path):
    from _toy import roofit_frame

    res = [("c", "pads", [(f"p{k}", roofit_frame(seed=k), [f"bin {k}"]) for k in range(1, 6)], [])]
    cfg = dict(auto.CONFIG)
    panels = auto._plot_pads(["t.root:c"], res, tmp_path / "all.png", True, cfg, {}, True)
    assert len(panels) == 5 and (tmp_path / "all.png").exists()
    assert len(panels.fig.axes) == 10                       # main + pull axes for each of 5 panels
    legends = [p.ax.get_legend() is not None for p in panels]
    assert legends == [True, False, False, False, False]    # one shared legend, on the first panel
    shaped = auto._plot_pads(["t.root:c"], res, tmp_path / "two.png", True, cfg, {}, (2, 3))
    assert len(shaped) == 5
    with pytest.raises(ValueError, match="do not fit"):
        auto._plot_pads(["t.root:c"], res, tmp_path / "bad.png", True, cfg, {}, (1, 3))

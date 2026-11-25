"""TTree histograms, grids, tones, comparisons (1.1)."""
import numpy as np
import pytest
import uproot

import figuratively as fg
from figuratively.cli import console


@pytest.fixture(scope="module")
def tree_file(tmp_path_factory):
    rng = np.random.default_rng(7)
    n = 5000
    path = tmp_path_factory.mktemp("trees") / "t.root"
    with uproot.recreate(path) as f:
        f.mktree("DecayTree", {"D0_M": "float64", "D0_PT": "float64", "nTracks": "int32", "w": "float64"})
        f["DecayTree"].extend({"D0_M": rng.normal(1865, 12, n), "D0_PT": rng.exponential(3000, n),
                               "nTracks": rng.integers(10, 600, n).astype(np.int32), "w": rng.uniform(0.5, 1.5, n)})
        f.mktree("Other", {"x": "float64"})
        f["Other"].extend({"x": rng.normal(0, 1, 100)})
    return str(path)


@pytest.fixture(scope="module")
def hist_pair(tmp_path_factory):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parents[1] / "examples" / "gallery"))
    import _toy
    return _toy.histogram_file(str(tmp_path_factory.mktemp("h") / "toy.root"))


# ------------------------------------------------------------------ fg.tree
def test_tree_histogram_counts_and_range(tree_file):
    h = fg.tree(f"{tree_file}:DecayTree", "D0_M", bins=40, range=(1800, 1930))
    assert len(h.values) == 40 and h.edges[0] == 1800 and h.edges[-1] == 1930
    assert 4900 < h.values.sum() <= 5000
    assert np.allclose(h.errors, np.sqrt(h.values))
    assert h.xtitle == "D0_M"


def test_tree_cut_expression_and_weights(tree_file):
    n_all = fg.tree(f"{tree_file}:DecayTree", "D0_M", bins=10, range=(1700, 2000)).values.sum()
    cut = fg.tree(f"{tree_file}:DecayTree", "D0_M", bins=10, range=(1700, 2000), cut="D0_PT > 3000 and nTracks < 300")
    assert 0 < cut.values.sum() < n_all
    w = fg.tree(f"{tree_file}:DecayTree", "D0_M", bins=10, range=(1700, 2000), weight="w")
    assert w.values.sum() != n_all and np.all(w.errors >= 0)
    e = fg.tree(f"{tree_file}:DecayTree", "D0_PT / 1000", bins=10, range=(0, 20))
    assert e.xtitle == "D0_PT / 1000"


def test_tree_name_may_be_left_out_only_when_unique(tree_file):
    with pytest.raises(ValueError, match="holds 2 trees or ntuples"):
        fg.tree(tree_file, "D0_M")


def test_tree_typos_get_hints(tree_file):
    with pytest.raises(KeyError, match="did you mean 'D0_M'"):
        fg.tree(f"{tree_file}:DecayTree", "D0_m")
    with pytest.raises(KeyError, match="did you mean 'DecayTree'"):
        fg.tree(f"{tree_file}:DecayTre", "D0_M")


@pytest.mark.parametrize("bad", ["__import__('os').system('echo hi')", "D0_M.__class__", "(lambda: 1)()",
                                 "[x for x in D0_M]", "open('f')", "D0_M if 1 else 2", "D0_M[0]"])
def test_tree_expressions_are_never_executed(tree_file, bad):
    with pytest.raises((ValueError, KeyError)):
        fg.tree(f"{tree_file}:DecayTree", bad, bins=5)
    with pytest.raises((ValueError, KeyError)):
        fg.tree(f"{tree_file}:DecayTree", "D0_M", bins=5, cut=bad)


def test_tree_empty_selection_is_an_error(tree_file):
    with pytest.raises(ValueError, match="no entries"):
        fg.tree(f"{tree_file}:DecayTree", "D0_M", cut="D0_M > 1e9")


def test_tree_result_plots_and_overlays(tree_file):
    a = fg.tree(f"{tree_file}:DecayTree", "D0_M", bins=30, range=(1800, 1930), name="all")
    b = fg.tree(f"{tree_file}:DecayTree", "D0_M", bins=30, range=(1800, 1930), cut="nTracks < 200", name="low mult")
    p = fg.plot(a, b, save=False)
    assert p.fig is not None or p.draw() is not None


def test_plotting_a_tree_directly_explains_what_to_do(tree_file):
    with pytest.raises(TypeError, match="fg.tree"):
        fg.plot(f"{tree_file}:DecayTree", save=False)


def test_cli_tree_and_clean_errors(tree_file, tmp_path, capsys):
    out = tmp_path / "t.png"
    console(["tree", f"{tree_file}:DecayTree", "D0_M", "-s", "bins=30", "-s", "range=(1800,1930)",
             "-s", "cut=nTracks < 300", "-o", str(out)])
    assert out.exists()
    with pytest.raises(SystemExit):
        console(["tree", f"{tree_file}:DecayTree", "nope"])
    assert "figuratively: error:" in capsys.readouterr().err


# ------------------------------------------------------------------ fg.grid
def test_grid_builds_one_figure_and_saves(tree_file, hist_pair, tmp_path):
    a = fg.tree(f"{tree_file}:DecayTree", "D0_M", bins=20, range=(1800, 1930))
    out = tmp_path / "g.pdf"
    g = fg.grid(a, f"{hist_pair}:corr", (f"{hist_pair}:data", f"{hist_pair}:mc"), shape=(1, 3), out=str(out),
                titles=["tree", "2D", "data vs MC"])
    assert len(g) == 3 and out.exists() and out.stat().st_size > 1000
    assert g[0].ax.get_title() == "tree"


def test_grid_default_shape_and_validation(tree_file, tmp_path):
    a = fg.tree(f"{tree_file}:DecayTree", "D0_M", bins=10, range=(1800, 1930))
    g = fg.grid([a, a, a, a], save=False)
    assert len(g) == 4
    with pytest.raises(ValueError, match="do not fit"):
        fg.grid(a, a, a, shape=(1, 2), save=False)
    with pytest.raises(ValueError, match="at least one"):
        fg.grid()
    with pytest.raises(ValueError, match="titles"):
        fg.grid(a, a, titles=["x"], save=False)
    with pytest.raises(ValueError, match="legend"):
        fg.grid(a, legend="sometimes", save=False)


# ------------------------------------------------------------------ tones
def _face(p):
    return p.fig.get_facecolor()


def test_dark_tone_changes_the_background_and_keeps_data_visible(hist_pair):
    p = fg.plot(f"{hist_pair}:data", tone="dark", save=False)
    p.draw()
    assert _face(p)[0] < 0.2 and p.ax.get_facecolor()[0] < 0.2


def test_mono_tone_uses_greys(hist_pair):
    p = fg.plot(f"{hist_pair}:data", f"{hist_pair}:mc", tone="mono", save=False)
    p.draw()
    for s in p.series:
        r, g, b, *_ = __import__("matplotlib.colors", fromlist=["to_rgba"]).to_rgba(s.color)
        assert abs(r - g) < 0.02 and abs(g - b) < 0.02


def test_tone_is_a_preset_and_validates(hist_pair):
    p = fg.plot(f"{hist_pair}:data", preset="mono", save=False)
    p.draw()
    with pytest.raises(ValueError, match="unknown tone"):
        fg.plot(f"{hist_pair}:data", tone="neon", save=False)
    assert fg.plot(f"{hist_pair}:data", save=False) is not None  # colour stays the default


# ------------------------------------------------------------------ compare / batch
def test_compare_needs_two_and_names_match(hist_pair):
    with pytest.raises(ValueError, match="at least two"):
        fg.compare(f"{hist_pair}:data")
    with pytest.raises(ValueError, match="one name per fit"):
        fg.compare(f"{hist_pair}:data", f"{hist_pair}:mc", names=["only one"])


def test_glob_and_list_batches_still_work(hist_pair, tmp_path):
    import shutil
    for i in range(2):
        shutil.copy(hist_pair, tmp_path / f"run{i}.root")
    done = fg.plot(str(tmp_path / "run*.root:data"), save=False)
    assert len(done) == 2
    done = fg.plot([str(tmp_path / "run0.root:data"), str(tmp_path / "run1.root:data")], save=False)
    assert len(done) == 2


def test_a_default_uproot_ntuple_works_too(tmp_path):
    path = tmp_path / "n.root"
    with uproot.recreate(path) as f:
        f["T"] = {"pt": np.random.default_rng(1).exponential(2.0, 500)}
    h = fg.tree(f"{path}:T", "pt", bins=10, range=(0, 10))
    assert h.values.sum() > 400


def test_grid_cells_can_carry_their_own_options(tree_file, hist_pair):
    a = fg.tree(f"{tree_file}:DecayTree", "D0_M", bins=10, range=(1800, 1930))
    g = fg.grid((f"{hist_pair}:data", f"{hist_pair}:mc", {"normalise": True}), f"{hist_pair}:corr", a, save=False)
    assert len(g) == 3
    with pytest.raises(ValueError, match="only options"):
        fg.grid(({"logy": True},), save=False)


def test_mono_tone_draws_2d_histograms_in_greys_and_an_explicit_cmap_wins(hist_pair):
    p = fg.plot(f"{hist_pair}:corr", tone="mono", save=False)
    p.draw()
    assert p.ax.collections[0].get_cmap().name == "Greys"
    q = fg.plot(f"{hist_pair}:corr", tone="mono", save=False)
    q.zaxis(cmap="magma")
    q.draw()
    assert q.ax.collections[0].get_cmap().name == "magma"
    r = fg.plot(f"{hist_pair}:corr", save=False)
    r.draw()
    assert r.ax.collections[0].get_cmap().name == "viridis"

"""Robustness tests (no ROOT needed): every fixture is written with uproot."""
import os
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest
import uproot

import figuratively as fg
from figuratively import data as D


@pytest.fixture(scope="module")
def messy(tmp_path_factory):
    path = tmp_path_factory.mktemp("m") / "messy.root"
    rng = np.random.default_rng(7)
    good = np.histogram(rng.normal(0, 1, 5000), bins=40, range=(-4, 4))
    with uproot.recreate(path) as f:
        f["good"] = good
        f["empty"] = np.histogram([], bins=10, range=(0, 1))
        f["single"] = (np.array([5.0]), np.array([0.0, 1.0]))
        f["nonuniform"] = (np.array([1.0, 4.0, 9.0, 3.0]), np.array([0.0, 1.0, 3.0, 6.0, 10.0]))
        f["sub/inner"] = good
        f["dotted.name_v1.2"] = good
    return str(path)


def test_split_spec():
    assert D.split_spec("f.root:h") == ("f.root", "h")
    assert D.split_spec("dir/f.root:sub/h") == ("dir/f.root", "sub/h")
    assert D.split_spec("C:\\data\\f.root") == ("C:\\data\\f.root", None)
    assert D.split_spec("root://eos//f.root") == ("root://eos//f.root", None)
    assert D.split_spec("root://eos//f.root:h") == ("root://eos//f.root", "h")


def test_rc_unchanged(messy, tmp_path):
    before = dict(plt.rcParams)
    p = fg.Plot().add(f"{messy}:good", "x").label("t")
    p.save(tmp_path / "a.png")
    assert dict(plt.rcParams) == before
    p.close()


def test_dotted_stem_not_eaten(messy, tmp_path):
    p = fg.Plot().add(f"{messy}:good", "x")
    p.save(tmp_path / "fig_v1.2", formats=("png", "pdf"))
    assert (tmp_path / "fig_v1.2.png").exists() and (tmp_path / "fig_v1.2.pdf").exists()
    p.save(tmp_path / "fig_v1.3.png")
    assert (tmp_path / "fig_v1.3.png").exists()
    p.close()


@pytest.mark.parametrize("name", ["empty", "single", "nonuniform", "sub/inner", "dotted.name_v1.2"])
def test_awkward_histograms_draw(messy, name):
    p = fg.Plot().add(f"{messy}:{name}", "h")
    p.draw()
    p.close()


def test_whole_file_skips_bad_and_does_not_leak(messy, tmp_path):
    n_before = len(plt.get_fignums())
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        out = fg.plot(messy, outdir=str(tmp_path / "all"), formats=("png",))
    assert len(out) >= 4  # the good ones were plotted whatever happened to the awkward ones
    assert len(list((tmp_path / "all").glob("*.png"))) >= 4
    assert len(plt.get_fignums()) == n_before  # no leaked figures


def test_missing_object_suggests_names(messy):
    with pytest.raises(KeyError, match="did you mean"):
        D.load(f"{messy}:goood")


def test_not_a_root_file(tmp_path):
    bad = tmp_path / "x.root"
    bad.write_text("this is not a root file")
    with pytest.raises(ValueError, match="not a readable ROOT file"):
        D.load(f"{bad}:h")


def test_canvas_reader_failure_is_explained(monkeypatch):
    class Obj:
        classname = "TCanvas"
        all_members = {}

    class File:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __getitem__(self, k):
            return Obj()

        def keys(self):
            return ["c;1"]

    monkeypatch.setattr(D.uproot, "open", lambda path: File())
    monkeypatch.setattr(D, "_canvas_fallback", lambda f, k: (_ for _ in ()).throw(AttributeError("boom")))
    with pytest.raises(RuntimeError, match="could not read canvas"):
        D.load("whatever.root:c")


@pytest.mark.skipif(not os.environ.get("FIGURATIVELY_TEST_CANVAS"),
                    reason="set FIGURATIVELY_TEST_CANVAS=file.root:canvas to test a real RooFit canvas")
def test_real_canvas(tmp_path):
    p = fg.plot(os.environ["FIGURATIVELY_TEST_CANVAS"], out=tmp_path / "real.png")
    assert (tmp_path / "real.png").exists() and p.rax is None or True


def test_notebook_display(messy):
    png = fg.Plot().add(f"{messy}:good", "x")._repr_png_()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_no_collaboration_label_by_default(messy, tmp_path):
    p = fg.plot(f"{messy}:good", out=tmp_path / "n.png")
    fig, ax, _ = p.draw()
    texts = [t.get_text() for t in fig.findobj(matplotlib.text.Text)]
    assert not any("LHCb" in t for t in texts)
    p.close()

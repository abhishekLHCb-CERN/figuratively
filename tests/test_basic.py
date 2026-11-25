import matplotlib

matplotlib.use("Agg")
import numpy as np
import pytest
import uproot

import figuratively as rp


@pytest.fixture(scope="module")
def rootfile(tmp_path_factory):
    path = tmp_path_factory.mktemp("d") / "t.root"
    rng = np.random.default_rng(1)
    with uproot.recreate(path) as f:
        f["data"] = np.histogram(rng.normal(1865, 8, 20000), bins=60, range=(1800, 1920))
        f["mc"] = np.histogram(rng.normal(1865, 8.5, 40000), bins=60, range=(1800, 1920))
        f["h2"] = np.histogram2d(rng.normal(0, 1, 5000), rng.normal(0, 1, 5000), bins=(20, 20))
    return str(path)


def test_list_and_load(rootfile):
    assert rp.list_objects(rootfile)["data"].startswith("TH1")
    h = rp.load(f"{rootfile}:data")
    assert h.values.sum() == 20000 and len(h.edges) == 61
    assert np.allclose(h.errors, np.sqrt(h.values))


def test_ops(rootfile):
    h = rp.load(f"{rootfile}:data")
    assert h.rebinned(2).values.sum() == h.values.sum()
    assert h.cropped(1840, 1890).edges[0] >= 1840
    assert np.isclose(h.normalised_to(1).values.sum(), 1)
    with pytest.raises(ValueError):
        h.rebinned(7)


@pytest.mark.parametrize("panel", [None, "ratio", "pull"])
def test_render(rootfile, tmp_path, panel):
    p = (rp.Plot().add(f"{rootfile}:data", "Data", kind="points")
         .add(f"{rootfile}:mc", "MC", normalise=False, scale=0.5)
         .xlabel("$m$", unit="MeV/$c^2$").label("Thesis").text(0.05, 0.8, "x"))
    {"ratio": p.ratio, "pull": p.pull, None: p.no_panel}[panel]()
    p.save(tmp_path / "o", formats=("pdf", "png"))
    assert (tmp_path / "o.pdf").stat().st_size > 0 and (tmp_path / "o.png").exists()
    assert p.ax.get_ylabel().startswith("Candidates / (2 MeV/$c^2$)")


def test_2d(rootfile, tmp_path):
    rp.Plot().add(f"{rootfile}:h2").zaxis(log=True, label="N").save(tmp_path / "h2.png")


def test_function_overlay(rootfile, tmp_path):
    p = rp.Plot().add(f"{rootfile}:data", "Data", kind="points")
    p.add_function(lambda x: 20000 * 2 * np.exp(-0.5 * ((x - 1865) / 8) ** 2) / (8 * 2.5066), (1800, 1920), "Fit")
    p.pull(data=0, model=1).logy().save(tmp_path / "f.png")


def _fake_frame(n_comp=8):
    from figuratively import G
    x = np.linspace(1700, 2000, 200)
    z = np.zeros_like(x)
    edges = np.linspace(1700, 2000, 61); c = 0.5 * (edges[1:] + edges[:-1]); w = np.full(60, 2.5)
    y = np.full(60, 100.0)
    objs = {"h_data": G(c, y, w, w, np.sqrt(y), np.sqrt(y), "h_data", classname="RooHist"),
            "m_Norm[x]": G(x, np.full_like(x, 100.0), z, z, z, z, "m", classname="RooCurve")}
    for i in range(n_comp):
        objs[f"m_Norm[x]_Comp[c{i}]"] = G(x, np.full_like(x, 100.0 / n_comp), z, z, z, z, f"c{i}",
                                          classname="RooCurve")
    return objs


def test_parse_roofit_name():
    assert rp.data.parse_roofit_name("pdf_Norm[m]_Comp[a,b]")["components"] == ("a", "b")
    assert rp.data.parse_roofit_name("pdf_Norm[m]")["components"] == ()


@pytest.mark.parametrize("stack", [False, True])
def test_roofit_many_components(tmp_path, stack):
    p = rp.Plot().add_roofit(_fake_frame(12), stack=stack, hide=["c3$"]).pull(chi2=True)
    p.save(tmp_path / "f.png")
    labels = [t.get_text() for t in p.ax.get_legend().get_texts()]
    assert labels[:2] == ["Data", "Total fit"] and len(labels) == 2 + 11  # c3 hidden
    assert p.ax.get_ylabel() == "Candidates / (5 )".replace(" )", ")") or "Candidates" in p.ax.get_ylabel()


def test_add_stack_histograms(rootfile, tmp_path):
    rp.Plot().add_stack({"a": f"{rootfile}:data", "b": f"{rootfile}:mc"}).logy().save(tmp_path / "s.png")


def test_one_call_overlay_and_batch(rootfile, tmp_path):
    p = rp.plot(f"{rootfile}:data", f"{rootfile}:mc", out=tmp_path / "ov", formats=("png",))
    assert (tmp_path / "ov.png").exists() and p.rax is not None  # ratio added automatically
    ps = rp.plot(rootfile, outdir=str(tmp_path / "all"), formats=("png",))
    assert len(ps) == 3 and len(list((tmp_path / "all").glob("*.png"))) == 3


def test_one_call_fit_and_options(tmp_path):
    p = rp.plot(_fake_frame(5), out=tmp_path / "fit.png", logy=True, xlim=(1750, 1950),
                info="test", label="Preliminary")
    assert p.ax.get_yscale() == "log" and p.rax is not None


def test_titles():
    assert rp.root_tex("m(K^{+}K^{-}#gamma)") == r"$m(K^{+}K^{-}\gamma)$"
    from figuratively.auto import title_label
    assert title_label("mass [MeV/c^{2}]") == ("mass", "MeV/$c^2$")
    assert title_label("m(KK#gamma)")[1] is None


def test_unknown_option_is_loud(rootfile, tmp_path):
    with pytest.raises(TypeError):
        rp.plot(f"{rootfile}:data", out=tmp_path / "x.png", nonsense=1)

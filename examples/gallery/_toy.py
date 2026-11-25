"""Toy data for the gallery: fixed seed, no real analysis data anywhere."""
import numpy as np
import uproot

from figuratively import G


def roofit_frame(lo=1700.0, hi=2000.0, nb=75, seed=5, root=False):
    """A RooFit-style frame (data points, total curve, components) as a dict of G objects.

    root=True also stores ROOT colour attributes, like a real canvas written by a ROOT macro.
    """
    colour = {"sig": (900, 9), "tail": (910, 9), "comb": (419, 9), "bkg_a": (810, 9), "bkg_b": (805, 9),
              "bkg_c": (886, 9)}
    rng = np.random.default_rng(seed)
    comps = {
        "sig": lambda x: 9000 * np.exp(-0.5 * ((x - 1865) / 9) ** 2) / (9 * 2.5066),
        "tail": lambda x: 3000 * np.exp(-0.5 * ((x - 1862) / 22) ** 2) / (22 * 2.5066),
        "comb": lambda x: 35 * 4 * np.exp(-(x - lo) / 140),
        "bkg_a": lambda x: 4000 * np.exp(-0.5 * ((x - 1770) / 35) ** 2) / (35 * 2.5066),
        "bkg_b": lambda x: 1500 * np.exp(-0.5 * ((x - 1800) / 25) ** 2) / (25 * 2.5066),
        "bkg_c": lambda x: 1200 * np.exp(-0.5 * ((x - 1930) / 30) ** 2) / (30 * 2.5066),
    }
    x = np.linspace(lo, hi, 400)
    z = np.zeros_like(x)
    edges = np.linspace(lo, hi, nb + 1)
    c = 0.5 * (edges[1:] + edges[:-1])
    w = edges[1] - edges[0]
    y = rng.poisson(sum(f(c) for f in comps.values()) * w).astype(float)
    pad = lambda a: np.r_[0, a, 0]
    padx = lambda a: np.r_[a[0] - 1e-3, a, a[-1] + 1e-3]
    h = np.full(nb, w / 2)
    attrs = lambda col, sty: ({"line_color": col, "line_style": sty, "fill_color": 0, "fill_style": 1000,
                              "marker_color": 1} if root else {})
    objs = {"h_data": G(c, y, h, h, np.sqrt(y), np.sqrt(y), "h_data", classname="RooHist", root=attrs(1, 1))}
    objs["model_Norm[m]"] = G(padx(x), pad(sum(f(x) for f in comps.values()) * w), *(pad(z),) * 4,
                              "model", classname="RooCurve", root=attrs(600, 1))
    for n, f in comps.items():
        objs[f"model_Norm[m]_Comp[{n}]"] = G(padx(x), pad(f(x) * w), *(pad(z),) * 4, n, classname="RooCurve",
                                              root=attrs(*colour[n]))
    return objs


def histogram_file(path="toy.root", seed=3):
    rng = np.random.default_rng(seed)
    with uproot.recreate(path) as f:
        f["data"] = np.histogram(rng.normal(1865, 7, 20000), bins=60, range=(1800, 1920))
        f["mc"] = np.histogram(rng.normal(1865, 6.5, 50000), bins=60, range=(1800, 1920))
        f["corr"] = np.histogram2d(rng.normal(0, 1, 20000), rng.normal(0, 1, 20000) * 0.6 + 0.4, bins=(30, 30))
    return path

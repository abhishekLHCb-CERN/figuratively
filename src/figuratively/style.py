"""Style handling: mplhep experiment styles plus a thesis design layer."""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import mplhep as hep
from cycler import cycler
from matplotlib.font_manager import FontProperties

# Colour-blind safe, print friendly (Okabe-Ito based). Index 0-7 is the default series cycle.
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#6A3D9A", "#8C564B"]
DATA_COLOR = "black"
TOTAL_COLOR = "#C0392B"  # total fit curve
COMP_PALETTE = ["#0072B2", "#009E73", "#E69F00", "#CC79A7", "#56B4E9", "#6A3D9A", "#8C564B",
                "#7F7F7F", "#B8860B", "#17BECF"]
COMP_DASHES = ["--", "-.", ":", (0, (6, 2, 1, 2)), (0, (2, 2))]
PULL_COLOR = "#5B8DB8"

# Applied on top of the mplhep style. Edit here to change every plot at once.
THESIS_RC: dict = {
    "figure.figsize": (11, 8.2),
    "font.size": 20,
    "axes.labelsize": 26,
    "xtick.labelsize": 22,
    "ytick.labelsize": 22,
    "legend.fontsize": 17,
    "axes.linewidth": 1.6,
    "lines.linewidth": 2.2,
    "xtick.major.size": 10,
    "ytick.major.size": 10,
    "xtick.minor.size": 5,
    "ytick.minor.size": 5,
    "axes.prop_cycle": cycler(color=PALETTE),
    "axes.labelpad": 8,
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
    "pdf.fonttype": 42,  # editable, embedded TrueType text in PDFs
    "ps.fonttype": 42,
    "legend.frameon": False,
    "legend.handlelength": 1.5,
    "legend.columnspacing": 1.0,
    "legend.handletextpad": 0.6,
    "legend.labelspacing": 0.35,
}

DEFAULT_STYLE = "LHCb2"
_LINE_KEYS = ("lines.linewidth", "axes.linewidth", "xtick.major.size", "ytick.major.size",
              "xtick.minor.size", "ytick.minor.size", "xtick.major.width", "ytick.major.width",
              "xtick.minor.width", "ytick.minor.width")
_FONT_KEYS = ("font.size", "axes.labelsize", "xtick.labelsize", "ytick.labelsize", "legend.fontsize")


def use_style(name: str | None = DEFAULT_STYLE, font_scale: float = 1.0, **rc) -> None:
    """Activate an mplhep style name (LHCb2, LHCb, ATLAS, CMS, ROOT, ...) or a .mplstyle file.

    ``font_scale`` multiplies all text sizes; ``rc`` entries override everything else.
    """
    if name and re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", str(name)):
        raise ValueError("style: URLs are not accepted (a style is an mplhep name or a local .mplstyle file)")
    if name:
        if Path(str(name)).suffix == ".mplstyle":
            plt.style.use(str(name))
        else:
            hep.style.use(name)
        plt.rcParams.update(THESIS_RC)
    else:
        plt.rcParams.update(THESIS_RC)
    plt.rcParams.update(rc)
    if font_scale != 1.0:
        for k in _FONT_KEYS:
            plt.rcParams[k] = FontProperties(size=plt.rcParams[k]).get_size_in_points() * font_scale
        for k in _LINE_KEYS:  # keep lines and ticks in proportion with the text
            plt.rcParams[k] = plt.rcParams[k] * max(min(font_scale, 1.5), 0.5)

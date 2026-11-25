"""Figuratively: publication-quality plots straight from ROOT files (uproot only, no ROOT needed)."""
from .auto import config_path, configure, plot, root_tex
from .checks import check, summary
from .colors import palette, root_color
from .data import H1, H2, G, list_objects, load, load_all
from .explore import init, inspect
from .options import options
from .plot import Plot
from .style import THESIS_RC, use_style

__all__ = [
    "H1",
    "H2",
    "THESIS_RC",
    "G",
    "Plot",
    "check",
    "config_path",
    "configure",
    "init",
    "inspect",
    "list_objects",
    "load",
    "load_all",
    "options",
    "palette",
    "plot",
    "root_color",
    "root_tex",
    "summary",
    "use_style",
]
__version__ = "1.0.0"
__author__ = "Abhishek Bohare"

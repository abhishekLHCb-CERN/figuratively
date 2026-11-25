"""Colours: translate ROOT colour indices into well-behaved colours and build R-style palettes.

ROOT's colours are the saturated primaries of the 1990s (pure red, green and blue). R hit the same
problem and replaced its default palette in version 4.0 with tamed tones, and builds its palettes in
perceptual HCL space (``hcl.colors``) so that hues are evenly spaced and equally bright. We follow both ideas
in OKLCH, a modern perceptually uniform space:

* ``root_color(index)`` keeps the **hue** of the ROOT colour (so a red curve in the macro is still a red
  curve), compresses the lightness into a readable band and caps the chroma, so no colour screams and none
  vanishes on a white page. The light-to-dark order of ROOT's shades (kRed-4 ... kRed+3) is preserved.
* ``palette(name, n)`` offers named palettes (R 4.x default, Okabe-Ito, Tableau, Dark 2) and extends any
  of them with evenly spaced HCL hues, so 30 components never repeat a colour.
"""
from __future__ import annotations

import math

from ._rootcolor_table import BASIC, BLOCKS
from .style import COMP_PALETTE

# ---------------------------------------------------------------- ROOT colour table
_TABLE: dict[int, str] = {}
for _i, _h in enumerate(BASIC):
    _TABLE[_i] = _h
for _start, _s in BLOCKS:
    for _k in range(len(_s) // 6):
        _TABLE[_start + _k] = _s[6 * _k: 6 * _k + 6]
# ROOT 6 names (TColor.h): family base + offset, offset in [-10, +4] (lighter ... darker)
ROOT_NAMES = {"kWhite": 0, "kBlack": 1, "kGray": 920, "kRed": 632, "kGreen": 416, "kBlue": 600,
              "kYellow": 400, "kMagenta": 616, "kCyan": 432, "kOrange": 800, "kSpring": 820,
              "kTeal": 840, "kAzure": 860, "kViolet": 880, "kPink": 900}


def root_rgb(index: int) -> str | None:
    """Exact ROOT colour for an index as '#rrggbb' (None if unknown, e.g. a custom TColor)."""
    h = _TABLE.get(int(index))
    return f"#{h}" if h else None


def describe(index: int) -> str:
    """Human name of a ROOT colour index, e.g. 910 -> 'kPink+10'."""
    best = None
    for name, base in ROOT_NAMES.items():
        off = int(index) - base
        if -10 <= off <= 10 and (best is None or abs(off) < abs(best[1])):
            best = (name, off)
    if best is None:
        return str(index)
    name, off = best
    return name if off == 0 else f"{name}{off:+d}"


# ---------------------------------------------------------------- OKLab / OKLCH
def _to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _from_lin(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_to_oklch(hexcol: str) -> tuple[float, float, float]:
    if not (isinstance(hexcol, str) and hexcol.startswith("#") and len(hexcol) == 7):
        from matplotlib.colors import to_hex  # named colours ('red'), 'C0', rgb tuples ...

        hexcol = to_hex(hexcol)
    h = hexcol.lstrip("#")
    r, g, b = (_to_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def _oklch_to_lin(L: float, C: float, hdeg: float):
    a, b = C * math.cos(math.radians(hdeg)), C * math.sin(math.radians(hdeg))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def oklch_to_hex(L: float, C: float, hdeg: float) -> str:
    """OKLCH -> '#rrggbb', reducing the chroma until the colour fits the sRGB gamut."""
    lo, hi = 0.0, C
    rgb = _oklch_to_lin(L, C, hdeg)
    if not all(-1e-4 <= v <= 1 + 1e-4 for v in rgb):
        for _ in range(24):
            mid = 0.5 * (lo + hi)
            if all(-1e-4 <= v <= 1 + 1e-4 for v in _oklch_to_lin(L, mid, hdeg)):
                lo = mid
            else:
                hi = mid
        rgb = _oklch_to_lin(L, lo, hdeg)
    return "#" + "".join(f"{round(_from_lin(v) * 255):02x}" for v in rgb)


# ---------------------------------------------------------------- translation of ROOT colours
def _nudge_hue(h: float) -> float:
    """Yellow-greens look olive once darkened; pull them towards amber, which stays clean and visible."""
    if 85.0 <= h <= 125.0:
        return 85.0 + (h - 85.0) * 0.25
    return h



def refine(hexcol: str, *, l_lo: float = 0.38, l_span: float = 0.40, c_scale: float = 0.85,
           c_floor: float = 0.02, c_max: float = 0.17) -> str:
    """Tame a saturated colour: same hue, lightness squeezed into a readable band, capped chroma."""
    L, C, h = hex_to_oklch(hexcol)
    if C < 0.02:  # neutral greys stay neutral, a little lighter than black
        return oklch_to_hex(0.20 + 0.55 * L, 0.0, 0.0)
    h = _nudge_hue(h)
    return oklch_to_hex(l_lo + l_span * L, min(c_max, C * c_scale + c_floor), h)


_cache: dict[int, str | None] = {}


def root_color(index) -> str | None:
    """ROOT colour index -> refined '#rrggbb' (the translation described in the module docstring).

    Black stays black and white is dropped (None), because both usually mean "default / invisible".
    Unknown indices (custom TColor objects) return None so the caller falls back to a palette.
    """
    try:
        idx = int(index)
    except (TypeError, ValueError):
        return None
    if idx in _cache:
        return _cache[idx]
    raw = root_rgb(idx)
    out = None if (raw is None or idx == 0) else ("#000000" if idx == 1 else refine(raw))
    _cache[idx] = out
    return out


def distance(c1: str, c2: str) -> float:
    """Perceptual distance between two colours (Euclidean in OKLab; about 0.02 is just noticeable)."""
    (L1, C1, h1), (L2, C2, h2) = hex_to_oklch(c1), hex_to_oklch(c2)
    a1, b1 = C1 * math.cos(math.radians(h1)), C1 * math.sin(math.radians(h1))
    a2, b2 = C2 * math.cos(math.radians(h2)), C2 * math.sin(math.radians(h2))
    return math.sqrt((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)


_NUDGES = [(0.0, 14), (0.10, 0), (-0.10, 0), (0.0, -14), (0.12, 22), (-0.12, -22), (0.16, 0), (-0.16, 0),
           (0.0, 30), (0.0, -30), (0.14, 35), (-0.14, -35)]


def separate(color: str, others, min_distance: float = 0.10) -> str:
    """Keep a colour if it is clearly different from every colour in ``others``; otherwise move it
    (lighter, darker or a few degrees of hue) until it is. R's palettes do this by construction: evenly spaced
    hues at fixed lightness. Here it rescues palettes whose hues were chosen by hand, e.g. kPink, kOrange+10
    and kOrange+5 in one canvas."""
    others = list(others)
    if not others or min(distance(color, o) for o in others) >= min_distance:
        return color
    L, C, h = hex_to_oklch(color)
    best, best_d = color, min(distance(color, o) for o in others)
    for dl, dh in _NUDGES:
        cand = oklch_to_hex(min(0.88, max(0.30, L + dl)), C, (h + dh) % 360)
        d = min(distance(cand, o) for o in others)
        if d >= min_distance:
            return cand
        if d > best_d:
            best, best_d = cand, d
    return best


# ROOT line styles (TAttLine) -> matplotlib linestyles
ROOT_LINESTYLES = {1: "-", 2: "--", 3: ":", 4: "-.", 5: (0, (9, 3, 2, 3)), 6: (0, (9, 3, 2, 3, 2, 3)),
                   7: (0, (6, 3)), 8: (0, (9, 3)), 9: (0, (11, 4)), 10: (0, (11, 4, 2, 4))}
# ROOT fill styles: solid, and the common hatch patterns -> matplotlib hatch strings
ROOT_HATCH = {3004: "///", 3005: "\\\\\\", 3006: "|||", 3007: "---", 3003: "xxx", 3002: "...", 3001: "..."}


# ---------------------------------------------------------------- R-style palettes
PALETTES: dict[str, list[str]] = {
    "mono": ["#1A1A1A", "#5C5C5C", "#8A8A8A", "#B0B0B0", "#3A3A3A", "#747474", "#9C9C9C", "#C4C4C4"],
    "figuratively": list(COMP_PALETTE),
    # R >= 4.0 default palette()
    "r4": ["#DF536B", "#2297E6", "#61D04F", "#F5C710", "#CD0BBC", "#28E2E5", "#9E9E9E"],
    # R: palette.colors() default, Okabe and Ito (colour-blind safe)
    "okabe-ito": ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#999999"],
    # R: palette.colors("Tableau 10")
    "tableau10": ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948", "#B07AA1",
                  "#FF9DA7", "#9C755F", "#BAB0AC"],
    # R: RColorBrewer "Dark2"
    "dark2": ["#1B9E77", "#D95F02", "#7570B3", "#E7298A", "#66A61E", "#E6AB02", "#A6761D", "#666666"],
}


def hcl_palette(n: int, l: float = 0.62, c: float = 0.12, start: float = 25.0) -> list[str]:
    """n colours with evenly spaced hues at equal lightness and chroma, like R's hcl.colors / ggplot2's hue."""
    return [oklch_to_hex(l, c, (start + 360.0 * i / max(n, 1)) % 360) for i in range(n)]


def palette(name: str = "figuratively", n: int | None = None) -> list[str]:
    """Named palette (figuratively, r4, okabe-ito, tableau10, dark2, hcl), extended with HCL hues to n colours."""
    key = name.lower().replace("_", "-").replace(" ", "")
    if key == "hcl":
        return hcl_palette(n or 8)
    if key not in PALETTES:
        from .options import did_you_mean

        raise ValueError(f"unknown palette '{name}'{did_you_mean(key, [*PALETTES, 'hcl'])} "
                         f"(available: {', '.join([*PALETTES, 'hcl'])})")
    base = list(PALETTES[key])
    if n is None or n <= len(base):
        return base[:n] if n else base
    # more components than colours: add evenly spaced HCL hues instead of repeating
    return base + hcl_palette(n - len(base), start=57.0)

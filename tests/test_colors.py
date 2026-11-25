"""ROOT colour translation, R-style palettes and perceptual separation."""
import itertools

import pytest
from _toy import roofit_frame

import figuratively as fg
from figuratively import colors as C
from figuratively.style import TOTAL_COLOR


def test_root_table_matches_known_definitions():
    assert C.root_rgb(632) == "#ff0000" and C.root_rgb(600) == "#0000ff" and C.root_rgb(416) == "#00ff00"
    assert C.root_rgb(400) == "#ffff00" and C.root_rgb(1) == "#000000"
    assert C.root_rgb(10**6) is None
    assert C.describe(632) == "kRed" and C.describe(601) == "kBlue+1" and C.describe(628) == "kRed-4"


def test_translation_keeps_hue_and_tames_the_colour():
    for idx in (632, 600, 416, 616, 432, 880, 900):
        _, C0, h0 = C.hex_to_oklch(C.root_rgb(idx))
        L, Cc, h = C.hex_to_oklch(C.root_color(idx))
        assert abs((h - h0 + 180) % 360 - 180) < 12, idx  # same hue family
        assert 0.36 <= L <= 0.80 and Cc <= 0.19, (idx, L, Cc)  # readable on white, not screaming
    assert C.root_color(1) == "#000000" and C.root_color(0) is None and C.root_color(10**6) is None
    assert C.root_color(None) is None and C.root_color("x") is None


def test_shade_order_survives_translation():
    light = C.hex_to_oklch(C.root_color(628))[0]   # kRed-4
    dark = C.hex_to_oklch(C.root_color(635))[0]    # kRed+3
    assert light > dark


def test_separate_moves_only_clashing_colours():
    a = "#de5756"
    assert C.separate("#2297e6", [a]) == "#2297e6"
    moved = C.separate("#df5c43", [a])
    assert moved != "#df5c43" and C.distance(moved, a) >= 0.10
    assert C.separate(a, []) == a


@pytest.mark.parametrize("name", ["figuratively", "r4", "okabe-ito", "tableau10", "dark2", "hcl"])
def test_palettes_extend_without_repeating(name):
    cols = C.palette(name, 30)
    assert len(cols) == 30 and len({c.lower() for c in cols}) == 30


def test_unknown_palette_suggests():
    with pytest.raises(ValueError, match="did you mean 'okabe-ito'"):
        C.palette("okabe-itoo")


# ------------------------------------------------------------------ in plots
def comps(p):
    return {s.label: s for s in p.series if s.kind != "points" and s.label != "Total fit"}


def test_root_colours_are_used_translated_and_apart():
    p = fg.plot(roofit_frame(root=True), save=False)
    cs = comps(p)
    assert cs["sig"].color != C.PALETTES["figuratively"][0]
    assert C.root_color(419) == cs["comb"].color            # kGreen+3 -> its refined colour
    assert cs["comb"].style["linestyle"] == C.ROOT_LINESTYLES[9]   # ROOT line style 9 honoured
    total = next(s for s in p.series if s.label == "Total fit")
    assert total.color == C.root_color(600)
    cols = [s.color for s in cs.values()] + [total.color]
    assert min(C.distance(a, b) for a, b in itertools.combinations(cols, 2)) >= 0.09


def test_root_colours_can_be_switched_off_or_limited():
    frame = roofit_frame(root=True)
    off = fg.plot(frame, save=False, root_colors=False)
    assert comps(off)["sig"].color == C.PALETTES["figuratively"][0]
    assert next(s for s in off.series if s.label == "Total fit").color == TOTAL_COLOR
    only = fg.plot(frame, save=False, root_colors="components")
    assert next(s for s in only.series if s.label == "Total fit").color == TOTAL_COLOR
    assert comps(only)["comb"].color == C.root_color(419)


def test_explicit_colour_beats_root_and_palette_applies():
    p = fg.plot(roofit_frame(root=True), save=False, colors={"sig": "black"})
    assert comps(p)["sig"].color == "black"
    q = fg.plot(roofit_frame(), save=False, palette="r4")
    assert comps(q)["sig"].color == C.PALETTES["r4"][0]


def test_solid_root_fill_becomes_a_filled_component():
    frame = roofit_frame(root=True)
    key = next(k for k in frame if k.endswith("Comp[comb]"))
    frame[key].root.update(fill_style=1001, fill_color=632)
    p = fg.plot(frame, save=False)
    assert comps(p)["comb"].kind == "fill"
    assert C.distance(comps(p)["comb"].color, C.root_color(632)) < 0.2  # a red, possibly nudged apart


def test_thirty_components_never_repeat_a_colour():
    frame = roofit_frame()
    base = next(k for k in frame if k.endswith("Comp[comb]"))
    for i in range(30):
        frame[f"model_Norm[m]_Comp[extra{i}]"] = frame[base]
    p = fg.plot(frame, save=False, root_colors=False)
    cols = [s.color for s in p.series if s.kind == "line" and s.label not in ("Total fit",)]
    assert len(cols) == len(set(c.lower() for c in cols))

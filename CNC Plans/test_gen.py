#!/usr/bin/env python3
"""
Headless acceptance test for the live modular generator (cnc_generator.py).

M7 FIX: previously this imported the abandoned "CNC GENERATOR - CARBIDE-OPTIMIZED v1.26.py"
monolith. It now drives the live module directly and asserts the fixes from the
fable-review pass (C1 rail overlap, C2 hatch shelf routing, C3 nested-hatch crash,
H2 countersink routing). Runs anywhere — no display/GUI required.

Run:  ../venv/bin/python3 test_gen.py     (from the "CNC Plans" folder)
"""
import os, re, json, copy, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
import cnc_generator as C

# A representative CONFIG (14x14x2.5", 15.2mm stock, 13x13 window). Mirrors the v134 output.
BASE = {
    "STOCK_THICKNESS": 15.19936, "TOOL_D_PRIMARY": 3.175, "FIT_TOLERANCE": 0.0,
    "TARGET_FINGER_WIDTH": 15.2, "TOTAL_WIDTH": 355.6, "TOTAL_HEIGHT": 355.6, "BOX_DEPTH": 63.5,
    "WINDOW_ENABLED": True, "WINDOW_WIDTH_IN": 13.0, "WINDOW_HEIGHT_IN": 13.0,
    "FRONT_RABBET_WIDTH": 0.0, "BACK_RABBET_WIDTH": 0.0,
    "FRONT_RABBET_DEPTH": 0.2992, "BACK_RABBET_DEPTH": 0.2992,
    "MOTOR_POCKET_ENABLED": False, "CLEATS_ENABLED": False,
    "HATCH_ENABLED": False, "BOTTOM_HATCH_ENABLED": False,
}


def build(cfg):
    C.CONFIG.clear(); C.CONFIG.update(cfg)
    v = "TEST"
    ff, gf = C.generate_front_bezel_parts(v)
    f_top, _ = C.generate_rail_parts("TOP_RAIL", True, False, v)
    f_bot, _ = C.generate_rail_parts("BOTTOM_RAIL", True, True, v)
    f_left, _ = C.generate_rail_parts("LEFT_RAIL", False, False, v)
    f_right, _ = C.generate_rail_parts("RIGHT_RAIL", False, False, v)
    fb, gb = C.generate_back_panel_parts(v)
    fc, cd = C.generate_french_cleats(v)
    master = C.generate_master_carbide_layout(v, ff, fb, f_top, f_bot, f_left, f_right, gb, cd)
    return master["MASTER_LAYOUT_COMBINED_vTEST.svg"]


def part_boxes(svg, suffix="_OUTSIDE_CUTS"):
    out = {}
    for d, tf, pid in re.findall(r'<path d="([^"]*)" [^>]*transform="([^"]*)" id="(\w+' + suffix + r')"', svg):
        n = [float(x) for x in re.findall(r'-?\d+\.?\d*', d)]
        t = re.findall(r'translate\(([-\d.]+),\s*([-\d.]+)\)', tf); rot = 'rotate(90)' in tf
        (a, b), (c, e) = map(lambda p: (float(p[0]), float(p[1])), t)
        pts = [(x + c, y + e) for x, y in zip(n[0::2], n[1::2])]
        if rot: pts = [(-y, x) for x, y in pts]
        pts = [(x + a, y + b) for x, y in pts]
        out[pid] = (min(p[0] for p in pts), min(p[1] for p in pts),
                    max(p[0] for p in pts), max(p[1] for p in pts))
    return out


def assert_no_overlap(svg, label):
    parts = part_boxes(svg)
    assert parts, f"[{label}] no parts parsed"
    for k, v in parts.items():
        assert v[0] >= -1e-6 and v[1] >= -1e-6, f"[{label}] {k} off-sheet at ({v[0]:.3f},{v[1]:.3f})"
    ks = list(parts)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            A, B = parts[ks[i]], parts[ks[j]]
            assert (A[2] <= B[0] + 1e-6 or B[2] <= A[0] + 1e-6 or
                    A[3] <= B[1] + 1e-6 or B[3] <= A[1] + 1e-6), f"[{label}] overlap {ks[i]} x {ks[j]}"
    print(f"  PASS [{label}] C1: {len(parts)} parts, on-sheet, no overlap")


def run_test():
    # C1: exact repro of the shipped v134 configuration.
    assert_no_overlap(build(copy.deepcopy(BASE)), "v134-repro")

    # C2/C3/H2: cleats + rear hatch on (nested lid path + mixed-content routing).
    cfg = copy.deepcopy(BASE)
    cfg.update({"CLEATS_ENABLED": True, "HATCH_ENABLED": True,
                "HATCH_WIDTH_PCT": 50.0, "HATCH_HEIGHT_PCT": 33.0, "HATCH_RAISE_IN": 0.0})
    svg = build(cfg)  # C3: must not raise NameError
    print("  PASS [hatch+cleats] C3: generation completed")
    assert_no_overlap(svg, "hatch+cleats")

    # C2: the back-panel hatch opening -> INSIDE WINDOW (through); shelf -> RABBET (pocket).
    assert any("BACK" in k for k in part_boxes(svg, "_INSIDE_WINDOW")), "C2: no BACK through-cut path"
    assert any("BACK" in k for k in part_boxes(svg, "_RABBET")), "C2: no BACK rabbet path"
    print("  PASS [hatch+cleats] C2: back hatch opening and shelf routed to distinct toolpaths")

    # H2: cleat countersinks route to a pocket (RABBET) path, not the through-HOLE path.
    assert any("CLEAT" in k for k in part_boxes(svg, "_RABBET")), "H2: no cleat pocket path"
    print("  PASS [hatch+cleats] H2: cleat countersinks in a pocket path")

    # M1: the real layout verifier agrees the master is clean.
    ok, report = C.verify_dimensions(svg, C.CONFIG)
    assert ok, f"M1: verify_dimensions failed: {report}"
    print(f"  PASS [M1] verify_dimensions: {report}")

    test_cnc01_no_lid_in_back_panel()
    test_cnc02_flush_fingers()
    test_cnc02_rear_hatch()
    test_cnc02_bottom_hatch()
    test_cnc04_nested_lid_routing()

    print("ALL ACCEPTANCE TESTS PASSED")


def back_outside_d(svg):
    return re.search(r'<path d="([^"]*)"[^>]*id="BACK_OUTSIDE_CUTS"', svg).group(1)


def test_cnc01_no_lid_in_back_panel():
    # CNC-01: the rear-hatch lid must not also be drawn inside the BACK panel's cell,
    # whether the lid nests in the front window or is packed as its own part.
    cfg = copy.deepcopy(BASE)
    cfg.update({"HATCH_ENABLED": True, "HATCH_WIDTH_PCT": 50.0, "HATCH_HEIGHT_PCT": 33.0, "HATCH_RAISE_IN": 0.0})
    for win in (True, False):
        cfg["WINDOW_ENABLED"] = win
        svg = build(cfg)
        assert back_outside_d(svg).count("M ") == 1, f"CNC-01: stray outline inside the back panel (window={win})"
        ok, report = C.verify_dimensions(svg, C.CONFIG)
        assert ok, f"CNC-01: layout check failed (window={win}): {report}"
    # The guard itself: a second outline planted on the back panel's outside cut must fail.
    d = back_outside_d(svg)
    bad = svg.replace(f'd="{d}"', f'd="{d} M 3 3 h 1 v 1 h -1 z"', 1)
    ok, report = C.verify_dimensions(bad, C.CONFIG)
    assert not ok and "separate outlines" in report, f"CNC-01: guard did not fire: {report}"
    print("  PASS [CNC-01] back panel holds one outline (lid nested and packed); guard rejects a second")



def test_cnc02_flush_fingers():
    # CNC-02 port of the January v1.26 flush fit: finger length is the full stock thickness
    # (the glue gap comes off the finger width only), and the C1 packing overhang matches it.
    cfg = copy.deepcopy(BASE)
    cfg["FIT_TOLERANCE"] = 0.4
    C.CONFIG.clear(); C.CONFIG.update(cfg)
    _, top_d = C.generate_rail_parts("TOP_RAIL", True, False, "T")
    xs = [float(x) for x in re.findall(r'-?\d+\.?\d*', top_d)][0::2]
    stock_in = cfg["STOCK_THICKNESS"] / 25.4
    assert abs(min(xs) - (2.0 - stock_in)) < 1e-4, f"finger tip at {min(xs):.4f}, expected {2.0 - stock_in:.4f}"
    svg = build(cfg)
    assert_no_overlap(svg, "glue gap 0.4 mm")
    x0, y0, x1, y1 = part_boxes(svg)["TOP_OUTSIDE_CUTS"]
    span = max(x1 - x0, y1 - y0)
    assert abs(span - cfg["TOTAL_WIDTH"] / 25.4) < 1e-3, f"packed TOP rail spans {span:.4f} in"
    print("  PASS [CNC-02 fingers] finger ends flush at a 0.4 mm glue gap; packed rail spans the outer width")



def rects(svg):
    return [tuple(float(v) for v in m) for m in re.findall(
        r'<rect x="([-\d.]+)" y="([-\d.]+)" width="([-\d.]+)" height="([-\d.]+)"', svg)]


def circles(svg):
    return [tuple(float(v) for v in m) for m in re.findall(
        r'<circle cx="([-\d.]+)" cy="([-\d.]+)" r="([-\d.]+)"', svg)]


def test_cnc02_rear_hatch():
    # CNC-02 port of the January v1.26 rear access panel: 0.64" lip, four 9/32" holes centred
    # in the back panel's lip, 0.2" lid holes on the same centres, lid file named HATCH_LID;
    # the July H7 lid fit clearance is kept.
    cfg = copy.deepcopy(BASE)
    cfg.update({"HATCH_ENABLED": True, "HATCH_WIDTH_PCT": 50.0, "HATCH_HEIGHT_PCT": 33.0,
                "HATCH_RAISE_IN": 0.0, "FIT_TOLERANCE": 0.4})
    C.CONFIG.clear(); C.CONFIG.update(cfg)
    fb, _ = C.generate_back_panel_parts("T")
    assert "HATCH_LID.vT.svg" in fb and "BACK_PANEL_HATCH_LID.vT.svg" not in fb, sorted(fb)
    (ox, oy, ow, oh), (sx, sy, sw, sh) = rects(fb["BACK_PANEL_HATCH_CUT.vT.svg"])
    assert abs((ox - sx) - 0.64) < 2e-4 and abs((sw - ow) / 2 - 0.64) < 2e-4, "lip is not 0.64 in"
    holes = circles(fb["BACK_PANEL_HATCH_CUT.vT.svg"])
    assert len(holes) == 4 and all(abs(r - 0.140625) < 2e-4 for _, _, r in holes), holes
    assert abs(holes[0][0] - (sx + 0.32)) < 2e-4 and abs(holes[0][1] - (sy + 0.32)) < 2e-4
    (lx, ly, lw, lh), (px, py, pw, ph) = rects(fb["HATCH_LID.vT.svg"])
    fit = 0.4 / 25.4
    assert abs(lw - (sw - fit)) < 2e-4 and abs(pw - (ow - fit)) < 2e-4 and abs((px - lx) - 0.64) < 2e-4
    lid_holes = circles(fb["HATCH_LID.vT.svg"])
    assert len(lid_holes) == 4 and all(abs(r - 0.1) < 2e-4 for _, _, r in lid_holes), lid_holes
    dx, dy = sx + fit / 2 - lx, sy + fit / 2 - ly      # lid centred in the shelf
    for (hx, hy, _), (qx, qy, _) in zip(holes, lid_holes):
        assert abs(hx - (qx + dx)) < 3e-4 and abs(hy - (qy + dy)) < 3e-4, "lid and panel holes not concentric"
    svg = build(cfg)
    hole_d = re.search(r'<path d="([^"]*)"[^>]*id="BACK_HOLE"', svg).group(1)
    assert hole_d.count("M ") == 4, "the four lip holes did not reach the back panel's hole path"
    print("  PASS [CNC-02 rear hatch] 0.64 in lip, 9/32 in panel holes, concentric 0.2 in lid holes, routed to HOLE")



def path_of(svg, pid):
    m = re.search(r'<path d="([^"]*)"[^>]*id="' + pid + '"', svg)
    return m.group(1) if m else ""


def test_cnc02_bottom_hatch():
    # CNC-02 port of the January v1.27-v1.28 bottom access panel: opening fixed at 3.395"
    # high, 0.6" lip, 9/32" rail holes 1/4" in from the lip edge, 0.2" lid holes on the same
    # centres, NEMA 17 mount in the lid; the July H7 lid fit clearance is kept.
    cfg = copy.deepcopy(BASE)
    cfg.update({"BOX_DEPTH": 6.1 * 25.4, "FIT_TOLERANCE": 0.4, "BOTTOM_HATCH_ENABLED": True,
                "BOTTOM_HATCH_WIDTH": 3.0 * 25.4, "BOTTOM_HATCH_HEIGHT": 76.12, "BOTTOM_HATCH_X_PCT": 50.0})
    C.CONFIG.clear(); C.CONFIG.update(cfg)
    fbot, _ = C.generate_rail_parts("BOTTOM_RAIL", True, True, "T")
    cut, lid = fbot["BOTTOM_RAIL_HATCH_CUT.vT.svg"], fbot["BOTTOM_RAIL_HATCH_LID.vT.svg"]
    (ox, oy, ow, oh), (sx, sy, sw, sh) = rects(cut)
    stock_in = cfg["STOCK_THICKNESS"] / 25.4
    rail_w = cfg["TOTAL_WIDTH"] / 25.4 - 2 * stock_in
    assert abs(oh - 3.395) < 2e-4 and abs(ow - 3.0) < 2e-4, (ow, oh)
    assert abs((ox + ow / 2) - (2.0 + rail_w * 0.5)) < 2e-4, "opening not centred on the rail body"
    assert abs((ox - sx) - 0.6) < 2e-4 and abs((sh - oh) / 2 - 0.6) < 2e-4, "lip is not 0.6 in"
    holes = circles(cut)
    assert len(holes) == 4 and all(abs(r - 0.140625) < 2e-4 for _, _, r in holes), holes
    assert abs(holes[0][0] - (sx + 0.390625)) < 2e-4 and abs(holes[0][1] - (sy + 0.390625)) < 2e-4
    fit = 0.4 / 25.4
    (lx, ly, lw, lh), (px, py, pw, ph) = rects(lid)
    assert abs(lw - (sw - fit)) < 2e-4 and abs(lh - (sh - fit)) < 2e-4 and abs((px - lx) - 0.6) < 2e-4
    lid_c = circles(lid)
    lid_holes = [c for c in lid_c if abs(c[2] - 0.1) < 2e-4]
    mount = [c for c in lid_c if abs(c[2] - 1.75 / 25.4) < 2e-4]
    assert len(lid_holes) == 4 and len(mount) == 4, lid_c
    dx, dy = sx + fit / 2 - lx, sy + fit / 2 - ly      # lid centred in the shelf
    for (hx, hy, _), (qx, qy, _) in zip(holes, lid_holes):
        assert abs(hx - (qx + dx)) < 3e-4 and abs(hy - (qy + dy)) < 3e-4, "lid and rail holes not concentric"
    cx, cy = lx + lw / 2, ly + lh / 2
    assert all(abs(abs(mx - cx) - 15.5 / 25.4) < 2e-4 and abs(abs(my - cy) - 15.5 / 25.4) < 2e-4 for mx, my, _ in mount)
    nema = re.findall(r'<path d="([^"]*)" fill="none" stroke="' + C.COLOR_POCKETS + '"', lid)
    assert len(nema) == 1 and nema[0].count("A ") == 4, "NEMA 17 pocket path missing"
    svg = build(cfg)
    assert path_of(svg, "BOTTOM_HATCH_LID_OUTSIDE_CUTS").count("M ") == 1
    assert path_of(svg, "BOTTOM_HATCH_LID_RABBET").count("M ") == 2, "lid step + motor pocket should be pockets"
    assert path_of(svg, "BOTTOM_HATCH_LID_HOLE").count("M ") == 8, "4 lid holes + 4 motor holes"
    assert path_of(svg, "BOTTOM_HOLE").count("M ") == 4, "the rail's four lip holes"
    ok, report = C.verify_dimensions(svg, C.CONFIG)
    assert ok, report
    print("  PASS [CNC-02 bottom hatch] 3.395 in opening, 0.6 in lip, rail/lid holes concentric, NEMA 17 mount routed")



def test_cnc04_nested_lid_routing():
    # CNC-04: a rear-hatch lid nested in the front window keeps its toolpath types:
    # one outside cut (the lid outline), one pocket (its step) and four holes.
    cfg = copy.deepcopy(BASE)
    cfg.update({"HATCH_ENABLED": True, "HATCH_WIDTH_PCT": 50.0, "HATCH_HEIGHT_PCT": 33.0,
                "HATCH_RAISE_IN": 0.0, "WINDOW_ENABLED": True})
    svg = build(cfg)
    names = [re.search(r'data-name="([^"]*)"', l).group(1)
             for l in svg.splitlines() if re.search(r'id="FRONT_\w+_\d+"', l)]
    assert names.count("OUTSIDE CUTS") == 1 and names.count("RABBET") == 1 and names.count("HOLE") == 4, names
    print("  PASS [CNC-04] nested lid: 1 outside cut, 1 pocket step, 4 holes")


if __name__ == "__main__":
    run_test()

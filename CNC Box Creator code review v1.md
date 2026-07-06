# Code Review — CNC Box Creator (cnc_generator.py + blender_generator.py)

**Verdict:** FIX-FIRST — the master CAM layout (the file actually milled from) provably overlaps parts and mislabels cut types in the current shipped output, and two realistic config combinations crash generation outright.
**Counts:** Critical 3 · High 7 · Medium 7 · Low 4
**Basis:** Intent inferred from code + `USER_SPECIFICATIONS.md`: a parametric shadowbox generator emitting per-part SVGs, a combined `MASTER_LAYOUT_COMBINED_v*.svg` for Carbide Create CAM (color/name = toolpath type), and Blender/TriVision visualization scripts. Stack inferred: Python 3 (venv), Tkinter + matplotlib GUI, Blender 4.x target. **Live-lineage assumption:** the review target is `Gemini McTell CNC Plans/cnc_generator.py` (header v1.25, modular) + `blender_generator.py` + `utils.py` + `generate_headless.py` — evidence: the newest output (`McTell SVGs v134`) embeds v1.25 markers, `generate_headless.py` imports `cnc_generator`, and `cnc_generator_settings.json` (newest mtime) matches its settings schema. The higher-numbered monoliths (`CNC GENERATOR - CARBIDE-OPTIMIZED v1.26–v1.29.py`, Jan 27–28) and `cnc_v1_11/12.py` are treated as abandoned parallel tracks. No code was executed; the GUI was not run — every runtime claim below is either traced statically or verified against the shipped v134 artifacts, and is tagged accordingly.
**Scope:** Reviewed in full: `cnc_generator.py` (3,330 lines), `blender_generator.py` (1,979), `utils.py`, `generate_headless.py`, `verify_encasement.py`, `test_gen.py`, `test_layout.py`, plus `McTell SVGs v134/` outputs (`MASTER_LAYOUT_COMBINED_v134.svg`, `OPEN_ME_IN_BLENDER.v134.py`, `config.json`) as ground truth. Deliberately skipped: `ARCHIVED PYTHON CODE/`, the v1.26–v1.29 monoliths, `cnc_v1_11/12.py`, `PROJECT CLOSET/`, the frozen `.app`, binary assets (`.c2d`, `.ai`, `.STEP`), and generated output folders other than v134 — superseded, frozen, or non-source.

All paths below are relative to `Gemini McTell CNC Plans/` unless noted.

## Triage (fix in this order)
- [C1] CRITICAL — Master layout packs rails without finger overhang: parts overlap and go off-sheet — cnc_generator.py:1514–1524
- [C2] CRITICAL — Hatch shelf pockets classified as through-cuts in master layout — cnc_generator.py:1703, 1789
- [C3] CRITICAL — `element_counts` NameError crashes generation when hatch lid nests inside window — cnc_generator.py:1857
- [H1] HIGH — Hatch-lid rabbet step and screw holes classified as OUTSIDE CUTS in master layout — cnc_generator.py:1695
- [H2] HIGH — Countersink files classified as through-holes: `"HOLES"` rule shadows `"HOLES_CSINK"` — cnc_generator.py:1698–1700
- [H3] HIGH — Blender script: cleat/hatch sections compare bool to `'True'`, never render; `BOTTOM_HATCH_*` keys never emitted — blender_generator.py:738, 811, 912, 138–163
- [H4] HIGH — Blender script: `half_d`/`half_h` used ~200 lines before definition (crashes once H3 is fixed) — blender_generator.py:775–806, 868, 938 vs 980–982
- [H5] HIGH — `GLUE_GAP` read in 3 places but never written: bottom-hatch flange ignores the UI glue gap — cnc_generator.py:966, 1110, 1601
- [H6] HIGH — Window size never validated against the bezel plug: v134 output has a 13.0" window on a 12.803" plug — cnc_generator.py:3167–3168
- [H7] HIGH — Hatch lids are line-to-line with their recesses: zero fit clearance on both hatches — cnc_generator.py:2004–2005, 1158–1159
- [M1] MEDIUM — `verify_dimensions` is a stub that always passes, but the success dialog presents it as a verification result — cnc_generator.py:1890–1895
- [M2] MEDIUM — Dead controls: Router Bit affects nothing; Motor X has no UI input (always `0.4155 ×` interior width, ungrounded); Cable Offset never read — cnc_generator.py:3056, 3181–3188, 2705
- [M3] MEDIUM — Window enabled with empty size fields emits a degenerate zero-size window path (the GUI default state) — cnc_generator.py:3164–3170
- [M4] MEDIUM — Blender script reads `HATCH_RAISE`, app writes `HATCH_RAISE_IN`: raise always 0 in viz — blender_generator.py:160
- [M5] MEDIUM — CONFIG mixes mm and inches per key; `FRONT/BACK_RABBET_WIDTH` is a negative inches value; headless run silently uses a different rabbet default — cnc_generator.py:3079–3082, generate_headless.py
- [M6] MEDIUM — Spec drift: SPEC-004/007 (rabbets) no longer match the v48+ plug design; Blender variant violates SPEC-008 (clip 0.01 vs 0.001) and SPEC-009 (exposure 4.0 vs 2.5) — blender_generator.py:1050, 1066
- [M7] MEDIUM — Both test scripts target stale or nonexistent files: zero coverage of the live module — test_gen.py:15, test_layout.py:14
- [L1] LOW — Dead/duplicated code: two `compute_finger_layout` defs, unreachable layer-map branches, unused `BOTTOM ACCESS` buffers, marker function — cnc_generator.py:467/521, 1696/1704, 1716–1717, 1875
- [L2] LOW — BinPacker 48×96 expansion never reverts on failure; sheet stays 96" tall for all later items — cnc_generator.py:1245–1263
- [L3] LOW — UI shows "v1.24" while the header says v1.25; `BACK_PANEL_HOLES_THROUGH` file titled `BACK_PANEL_HOLES` — cnc_generator.py:2775, 1977/1981
- [L4] LOW — Auto-installer retries pip with `--break-system-packages` on system Python — cnc_generator.py:71–75

## Findings

### [C1] CRITICAL — Master layout packs rails without finger overhang: parts overlap and go off-sheet
- **Where:** cnc_generator.py:1514–1524 (`generate_master_carbide_layout` → `prepare_part` calls); root cause interaction with `generate_perimeter_with_fingers` (fingers protrude `stock_thk − fit_tol` beyond each rail end, cnc_generator.py:692–695)
- **Category:** correctness
- **Problem:** Horizontal rails are packed as `w = TOTAL_WIDTH − 2·stock` (line 1519), but their drawn geometry extends `stock − fit_tol` beyond each end (the corner fingers). The BinPacker places neighbors `GAP = 0.5"` apart based on the understated width, and the placement transform maps the part body — not its true bounding box — to the packed cell.
- **Impact:** Proven in the shipped v134 output: TOP rail occupies x −0.098→13.902; BOTTOM rail occupies x 13.205→27.205 — the two rails' red OUTSIDE-CUT paths overlap by 0.697", and TOP's left fingers sit at negative x, off the 48×48 sheet. Milling this file as-is cuts each rail's corner fingers through the neighboring rail and clips the leftmost finger off the stock. Any box whose `stock_thk > GAP/2` (i.e., any stock ≥ ~6.4 mm) with two rails on one shelf reproduces this.
- **Fix:** Pack rails with their true extents and offset content so the true bbox origin maps to the cell. Minimal version — inflate the packed dims and shift the transform:
  ```diff
  -    w_topbot = total_w - (2 * stock_thk)
  -    parts_to_pack.append(prepare_part("TOP", f_top, w_topbot, box_d))
  -    parts_to_pack.append(prepare_part("BOTTOM", f_bot, w_topbot, box_d))
  +    fit_tol_in = convert_to_inches(CONFIG.get('FIT_TOLERANCE', 0.254))
  +    overhang = stock_thk - fit_tol_in           # finger protrusion per side
  +    w_topbot = (total_w - (2 * stock_thk)) + (2 * overhang)
  +    parts_to_pack.append(prepare_part("TOP", f_top, w_topbot, box_d, extra_id={'x_shift': overhang}))
  +    parts_to_pack.append(prepare_part("BOTTOM", f_bot, w_topbot, box_d, extra_id={'x_shift': overhang}))
  ```
  and in the transform construction (lines 1678–1681), add the shift so the leftmost finger lands at `global_x`: unrotated `translate({global_x + x_shift}, {global_y}) translate(-2,-2)`, rotated `translate({global_x + part_h}, {global_y + x_shift}) rotate(90) translate(-2,-2)` where `x_shift = part.get('extra', {}).get('x_shift', 0)`. A more robust structural fix: compute each part's true bbox by scanning its path coordinates (the paths are plain `M/L` lists) and pack on that — 10 lines, immune to future geometry changes.
- **Confidence:** CONFIRMED — parse `McTell SVGs v134/MASTER_LAYOUT_COMBINED_v134.svg`, apply each `<path>`'s transform to its coordinates: TOP x-range [−0.0984, 13.9016] intersects BOTTOM x-range [13.2048, 27.2048].

### [C2] CRITICAL — Hatch shelf pockets classified as through-cuts in master layout
- **Where:** cnc_generator.py:1703 (`get_layer_type_v11`: `"HATCH_CUT"` → `CONTOUR (Inside)`), 1789 (dead special-case: `"BOTTOM_HATCH_CUT" in fname` never matches `BOTTOM_RAIL_HATCH_CUT`)
- **Category:** correctness
- **Problem:** `BACK_PANEL_HATCH_CUT` and `BOTTOM_RAIL_HATCH_CUT` files each contain two rects: the through-opening (red) and the shelf pocket (orange). In the master layout, the whole file maps by filename to `CONTOUR (Inside)` → both rects land in the `INSIDE WINDOW` bucket, same red color, one combined path. The branch meant to split them (index 0 → `BOTTOM ACCESS CUT`, index 1 → `BOTTOM ACCESS RABBET`, lines 1789–1809) tests for the substring `"BOTTOM_HATCH_CUT"`, which the actual filename `BOTTOM_RAIL_HATCH_CUT` does not contain — verified: `'BOTTOM_HATCH_CUT' in 'BOTTOM_RAIL_HATCH_CUT.v134.svg'` is `False`. The `BOTTOM ACCESS CUT`/`BOTTOM ACCESS RABBET` buffers (1716–1717) are never populated.
- **Impact:** With the rear access panel enabled — the GUI default — the master layout tells the CAM user to through-cut the shelf outline. That cuts a hole the size of the *lid* in the back panel, destroying the shelf the lid rests on; the lid then falls through. Same for the bottom hatch on the bottom rail. The per-part SVGs are correct; only the green-labeled master (the primary CAM file) is wrong.
- **Fix:** Make the split keyed on the generic hatch-cut name and drive it before the generic bucket logic:
  ```diff
  -                    if "BOTTOM_HATCH_CUT" in fname: # Actually RAIL_NAME_HATCH_CUT
  +                    if "HATCH_CUT" in fname:  # BACK_PANEL_HATCH_CUT / BOTTOM_RAIL_HATCH_CUT
  ```
  so index 0 (opening) goes to the through-cut bucket and index 1 (shelf) to the rabbet/pocket bucket, for both hatches. Also remove `"HATCH_CUT"` from `get_layer_type_v11`'s early return or keep it only as the routing key — the per-index split must decide the bucket, not the filename. `depends on [C3]` only in the sense that both live in the same render loop; fixes are independent.
- **Confidence:** CONFIRMED — code path traced; substring mismatch verified in Python. To observe: enable Rear Access Panel, generate, inspect `MASTER_LAYOUT_COMBINED_v*.svg` — the shelf rect appears in the `*_INSIDE_WINDOW` path, not a rabbet path.

### [C3] CRITICAL — `element_counts` NameError crashes generation when hatch lid nests inside window
- **Where:** cnc_generator.py:1857–1858 (`generate_master_carbide_layout`, nested-hatch render branch)
- **Category:** correctness
- **Problem:** The nested-hatch branch (taken when `WINDOW_ENABLED` and the rear-hatch lid is smaller than the window minus 0.5", lines 1541–1548) references `element_counts`, which is not defined anywhere in the module — the only two occurrences are the read at 1857 and the subscript-assign at 1858 (grep-verified). First execution raises `NameError`.
- **Impact:** The exception propagates out of `generate_master_carbide_layout` into `run_generation`'s catch-all before any file is written: the user gets an error dialog and **zero output files**. Concrete repro with Joel's current saved settings (14×14 box, 13×13 window): re-enabling the rear access panel yields a lid of ~8.1×5.2" < 12.5×12.5" → nested → crash. So the two rear-hatch paths are: not-nested → C2/H1 (silently wrong master), nested → total failure.
- **Fix:** The counter only disambiguates element ids. Initialize it at the top of the part loop:
  ```diff
       # Render Nested Hatch
       if part.get('nested_hatch'):
           h_data = part['nested_hatch']
  +        element_counts = {}
  ```
  (or drop the counter and reuse the buffered-path id scheme used ten lines above).
- **Confidence:** CONFIRMED — name never bound in any enclosing scope; Python semantics guarantee the NameError. Repro: settings above, click GENERATE, observe error dialog and empty output folder.

### [H1] HIGH — Hatch-lid rabbet step and screw holes classified as OUTSIDE CUTS in master layout
- **Where:** cnc_generator.py:1695 (`get_layer_type_v11`: `"HATCH_LID"` → `CONTOUR (Outside)`), applied to `BACK_PANEL_HATCH_LID.*.svg` (built at 2062–2093) and `BOTTOM_RAIL_HATCH_LID.*.svg` (1167–1191)
- **Category:** correctness
- **Problem:** Each lid SVG contains three element types: outer perimeter (red), inner rabbet step (orange), four corner holes (blue). The master layout classifies per *file*, so all elements — including the rabbet rect and the holes — are merged into the single magenta `OUTSIDE CUTS` path.
- **Impact:** Following the master layout's layer semantics, the lid's rabbet step is contour-cut through (severing the flange from the plug — the lid falls apart) and the corner screw holes are cut as outside profiles. Triggers on the same default-on rear-hatch path as C2.
- **Fix:** Classify per element, not per file, for lid files: route each extracted `d` by the source element's stroke color (the per-part files already encode semantics in `COLOR_PERIMETER/_RABBETS/_HOLES`). Extract `stroke="..."` in `get_d_from_tag`'s caller and map `#ff0000→OUTSIDE CUTS`, `#e09500→RABBET`, `#0000ff→HOLE` when `"HATCH_LID" in fname`. This also future-proofs any other mixed-content file.
- **Confidence:** CONFIRMED — traced; the lid file provably contains three colors and the filename rule returns one bucket. Observe by enabling the rear hatch and inspecting `*_HATCH_LID` geometry inside the `*_OUTSIDE_CUTS` path of the master.

### [H2] HIGH — Countersink files classified as through-holes: `"HOLES"` rule shadows `"HOLES_CSINK"`
- **Where:** cnc_generator.py:1698–1700 (`get_layer_type_v11`)
- **Category:** correctness
- **Problem:** The check order is `"HOLES_THROUGH"`, then `"HOLES"`, then `"HOLES_CSINK"`. `CLEAT_WALL_HOLES_CSINK.v*.svg` contains `"HOLES"`, so it returns `HOLES (Inside)` at line 1698; the CSINK→POCKET rule at 1700 is unreachable (verified: `'HOLES' in 'CLEAT_WALL_HOLES_CSINK.v134.svg'` is `True`).
- **Impact:** With cleats enabled (GUI default), the master layout puts the 0.375"-diameter countersink circles in the same cyan through-`HOLE` path as the 0.188" pilot holes. CAM per the layer drills 0.375" holes through both cleats instead of milling 0.175"-deep countersink pockets — screw heads have nothing to bear on.
- **Fix:**
  ```diff
                   if "HOLES_THROUGH" in fname: return '02_HOLES', 'HOLES (Inside)'
  -                if "HOLES" in fname: return '02_HOLES', 'HOLES (Inside)'
  -                if "RABBETS" in fname: return '03_RABBETS', 'POCKET'
                   if "HOLES_CSINK" in fname: return '04_POCKETS', 'POCKET'
  +                if "HOLES" in fname: return '02_HOLES', 'HOLES (Inside)'
  +                if "RABBETS" in fname: return '03_RABBETS', 'POCKET'
  ```
  (most-specific substring first).
- **Confidence:** CONFIRMED — substring shadowing verified; enable cleats, generate, and check that `CLEAT_*_HOLES_CSINK` geometry lands in the `*_HOLE` cyan path of the master.

### [H3] HIGH — Blender script: cleat/hatch sections compare bool to `'True'`, never render; `BOTTOM_HATCH_*` keys never emitted
- **Where:** blender_generator.py:738, 811, 912 (template conditions), 156–157 (bool emission `str(config.get('CLEATS_ENABLED', True))`), 138–163 (emitted CONFIG block omits `BOTTOM_HATCH_ENABLED/WIDTH/HEIGHT/X_PCT`)
- **Category:** correctness
- **Problem:** The emitted script's CONFIG holds Python bool literals (`'CLEATS_ENABLED': False` in the shipped v134 script), but the feature gates test `CONFIG.get('CLEATS_ENABLED', 'True') == 'True'`. `True == 'True'` is always `False`. Additionally the bottom-hatch keys are never written into the emitted CONFIG at all, so that gate reads its `'False'` default.
- **Impact:** French cleats, the rear hatch, and the bottom hatch never appear in the Blender visualization regardless of settings — the viz silently misrepresents the design (the tool's whole purpose). Verified in `McTell SVGs v134/OPEN_ME_IN_BLENDER.v134.py` lines 56–57 vs 638/711/812.
- **Fix:** In the template, test truthiness: `if CONFIG.get('CLEATS_ENABLED', False):` (same for both hatches), and add the four `BOTTOM_HATCH_*` entries to the emitted CONFIG block. `depends on [H4]` — fixing this alone exposes the NameError below.
- **Confidence:** CONFIRMED — shipped-script text shows bool literals and string comparisons.

### [H4] HIGH — Blender script: `half_d`/`half_h` used ~200 lines before definition
- **Where:** blender_generator.py:775, 785, 806 (cleats), 868, 899, 908 (bottom hatch), 938, 947 (rear hatch) — all before the definitions at 980–982 (`half_w/half_h/half_d` in section 6)
- **Category:** correctness
- **Problem:** Sections 5b/5c/5d of the generated `create_shadowbox_assembly()` compute positions from `half_d`/`half_h`, which are defined only in section 6. Currently unreachable solely because of H3's always-False gates.
- **Impact:** Once H3 is fixed, any run with cleats or a hatch enabled raises `NameError: name 'half_d' is not defined` inside Blender and aborts the assembly build.
- **Fix:** Move the three lines `half_w = total_w / 2; half_h = total_h / 2; half_d = box_d / 2` up to just after the `stock_thk/total_w/total_h/box_d` reads (template line ~672), before section 5b. The TriVision variant already defines them before use (blender_generator.py:1878–1879 region) — mirror that ordering.
- **Confidence:** CONFIRMED — definition order provable from the emitted script (first use line 675, definition line 882 in `OPEN_ME_IN_BLENDER.v134.py`). Runtime check: fix H3, enable cleats, run the script in Blender.

### [H5] HIGH — `GLUE_GAP` read in 3 places but never written: bottom-hatch flange ignores the UI glue gap
- **Where:** cnc_generator.py:966 (dead local), 1110 (bottom-hatch flange), 1601 (master-layout lid packing dims); the rear hatch uses `FIT_TOLERANCE` instead at 2001
- **Category:** correctness
- **Problem:** `run_generation` maps the GUI "Glue Gap" field to `CONFIG['FIT_TOLERANCE']` (3058). Nothing ever sets `CONFIG['GLUE_GAP']` (grep-verified across the module and `generate_headless.py`), so the bottom-hatch flange is always `stock/2 − 0.5 mm` regardless of input, while the rear-hatch flange is `stock/2 − FIT_TOLERANCE`.
- **Impact:** With Joel's saved glue gap of 0: rear-hatch flange 0.299", bottom-hatch flange 0.279" — a phantom 0.5 mm divergence between two features that the UI presents as governed by one parameter. Any glue-gap tuning the user does has no effect on the bottom hatch.
- **Fix:** Replace the three `CONFIG.get('GLUE_GAP', 0.5)` reads with `CONFIG.get('FIT_TOLERANCE', 0.5)` (and delete the dead local at 966), or set `CONFIG['GLUE_GAP'] = CONFIG['FIT_TOLERANCE']` in `run_generation`. One source of truth either way.
- **Confidence:** CONFIRMED — grep shows reads only; writes absent.

### [H6] HIGH — Window size never validated against the bezel plug: v134 output has a 13.0" window on a 12.803" plug
- **Where:** cnc_generator.py:3167–3168 (clamp only against `total − 0.5`); plug inner rect computed at 857–863
- **Category:** correctness
- **Problem:** The window may be up to `TOTAL_WIDTH − 0.5"`, but the bezel's structural plug is only `TOTAL_WIDTH − 2·(stock + glue gap)` wide. Nothing checks the window against the plug. In the shipped v134 config (14×14 box, 15.2 mm stock, gap 0): plug inner = 12.803", window = 13.0".
- **Impact:** The window cut is wider than the plug boundary, so the through-cut swallows the entire plug ring: what remains of the front bezel is a 0.5"-wide frame that lies entirely within the half-depth rabbet ring — i.e., a fragile 0.5"-wide, half-stock-thick ring with no full-thickness plug to register the bezel in the box. Silent: no warning was printed for the v134 run.
- **Fix:** After computing `w_in/h_in` (3164–3168), clamp or warn against the plug:
  ```python
  rim = stock_thk_in + convert_to_inches(CONFIG['FIT_TOLERANCE']) + fit_adj_in
  max_win_w = total_w_in - 2*rim - 0.5   # keep >=0.25" of plug per side
  if w_in > max_win_w: warn/clamp (same for height)
  ```
  Surface it in the GUI status area, not just stdout.
- **Confidence:** CONFIRMED that the shipped config produces window > plug (arithmetic from `McTell SVGs v134/config.json`); SUSPECTED on intent — if Joel deliberately wants a face-frame-only bezel, downgrade to a warning rather than a clamp. Check with him before choosing clamp vs. warn.

### [H7] HIGH — Hatch lids are line-to-line with their recesses: zero fit clearance on both hatches
- **Where:** cnc_generator.py:2004–2005 (rear lid = opening + 2·flange), 2047–2048 (shelf = same), 2066/2073 (lid outer/plug rects); bottom hatch mirrors it at 1120–1121 vs 1158–1159 and 1171/1177
- **Category:** correctness
- **Problem:** Lid outer = shelf outer exactly; lid plug = opening exactly. The glue gap is subtracted from the *flange width* (per the quoted user formula "wide = 1/2 the stock thickness − the glue gap") but no clearance is ever applied between lid and recess, unlike the finger joints which shrink males by `FIT_TOLERANCE`.
- **Impact:** CAM-accurate cuts produce a lid that cannot physically drop into its shelf recess (0.000" clearance on all four sides) and a plug that cannot enter its opening. Every hatch lid needs hand-fitting, defeating the app's measured-fit purpose.
- **Fix:** Shrink the lid, keep the recess nominal: lid outer = `shelf − FIT_TOLERANCE` per side pair, lid plug = `opening − FIT_TOLERANCE`; i.e. in the lid rect calls subtract `fit_tol` from widths/heights and add `fit_tol/2` to x/y. Apply identically to both hatches (share a helper — the two blocks are already near-duplicates drifting apart, see H5).
- **Confidence:** CONFIRMED dimensionally (expressions provably equal); the physical no-fit consequence is standard machining practice, not run-verified.

### [M1] MEDIUM — `verify_dimensions` is a stub that always passes
- **Where:** cnc_generator.py:1890–1895; consumed at 3314–3316
- **Category:** robustness
- **Problem:** Returns `(True, "Verification Skipped (Robust Mode)")` unconditionally; the success dialog then shows this string as if a check ran.
- **Impact:** The one guard that could have caught C1's overlapping rails is a no-op, while the UI implies verification happened.
- **Fix:** Either implement the minimal real check (parse each part's path extents; assert pairwise non-overlap and non-negative coordinates in the master — the same ~15 lines as the C1 acceptance check) or change the dialog to omit the report line. Prefer the former; it is the regression net for C1.
- **Confidence:** CONFIRMED.

### [M2] MEDIUM — Dead controls: Router Bit affects nothing; Motor X has no UI input; Cable Offset never read
- **Where:** cnc_generator.py:3056 (`TOOL_D_PRIMARY` written, never read anywhere — grep-verified), 2460/3181 (`motor_x_val` variable exists, no row widget created), 2461/2705 (`cable_offset` entry rendered, never consumed), 3186–3188 (fallback `0.4155 × photograph_width`)
- **Category:** grounding | robustness
- **Problem:** Three inputs the user can see (or expects) have no effect: the Router Bit diameter is stored and dumped to config.json only; Motor Pocket X can never be entered (the row was never built), so the pocket always lands at the magic fraction `0.4155` of interior width — a constant with no cited source; Cable Offset is an orphan entry.
- **Impact:** User adjusts Router Bit expecting kerf-aware geometry and gets identical output; motor pocket position is uncontrollable and unexplained. (Motor pocket size 42 mm / pattern 31 mm do trace to NEMA-17 — those are fine.)
- **Fix:** Decide per control: if SVGs are nominal-by-design (CAM applies compensation), remove the Router Bit field or label it "reference only"; add the missing `make_row_with_units` for `motor_x_val` (units: mm) or remove the motor feature from the UI; wire `cable_offset` to whatever hole it was meant to place, or delete it. Document `0.4155` with its source or replace with 50%.
- **Confidence:** CONFIRMED for all three dead paths (grep); the 0.4155 provenance is unknown by definition.

### [M3] MEDIUM — Window enabled with empty size fields emits a degenerate zero-size window path
- **Where:** cnc_generator.py:3164–3170 (`get_mm('')` → 0.0), consumed at 896–914
- **Category:** robustness
- **Problem:** GUI defaults are `window_enabled=True` with empty `window_w/window_h`. Empty parses to 0.0, passes the `min()` clamps, and `generate_front_bezel_parts` happily draws a zero-area rectangle at panel center (`M cx cy L cx cy …`).
- **Impact:** First-run-out-of-the-box output contains a degenerate `FRONT_BEZEL_WINDOW` path in both the per-part file and the master's INSIDE WINDOW layer; CAM import of a zero-area contour is at best confusing, at worst a plunge-in-place toolpath.
- **Fix:** In `run_generation`, treat `w_in <= 0 or h_in <= 0` as window-disabled for this run (and set the two CONFIG sizes to 0 as the disabled branch already does); optionally flag it in the status area.
- **Confidence:** CONFIRMED by trace; not run-verified. Check: clear both window fields, generate, inspect `FRONT_BEZEL_WINDOW.v*.svg` for a zero-area path.

### [M4] MEDIUM — Blender script reads `HATCH_RAISE`; app writes `HATCH_RAISE_IN`
- **Where:** blender_generator.py:160 (emit: `config.get('HATCH_RAISE', 0.0)`); app writes `HATCH_RAISE_IN` at cnc_generator.py:3147; generated script consumes `HATCH_RAISE_IN` at blender_generator.py:930
- **Category:** api
- **Problem:** The emitted CONFIG key `HATCH_RAISE_IN` is populated from the wrong source key, so it is always `0.0`.
- **Impact:** Once H3/H4 let the rear hatch render, it will always sit at raise 0 regardless of the user's "Raise Panel" value — a silently wrong visualization.
- **Fix:** `'HATCH_RAISE_IN': {config.get('HATCH_RAISE_IN', 0.0)},` — one token.
- **Confidence:** CONFIRMED (key written vs key read; the in-code comment even quotes a `HATCH_RAISE` line that does not exist in the app).

### [M5] MEDIUM — CONFIG mixes units per key; `FRONT/BACK_RABBET_WIDTH` is a negative inches value; headless run uses a different default
- **Where:** cnc_generator.py:3079–3082 (`FRONT_RABBET_WIDTH = stock_in − (stock_in + fit_tol + adj)` = `−(fit_tol + adj)`, in inches, in a CONFIG whose dimension keys are mm); generate_headless.py (never sets `FRONT/BACK_RABBET_WIDTH` → code default `0.3"` at cnc_generator.py:851 applies)
- **Category:** grounding | maintainability
- **Problem:** The value called "rabbet width" is actually the negated plug clearance; it goes negative whenever glue gap > 0 (the GUI default 0.0197" produces −0.0197). Downstream, `rim_width = stock − FRONT_RABBET_WIDTH` reconstructs the intended `stock + gap`, so SVG output is correct — but the persisted config.json lies about the physical rabbet, the Blender script converts the negative value to meters (unused today only because rail rabbet booleans are skipped, blender_generator.py:608–611), and the headless path silently uses `0.3"` instead, producing a plug 0.3" different per side from the GUI for identical inputs.
- **Impact:** Anyone reading config.json, the Blender CONFIG, or running headless gets geometry semantics different from the GUI; the negative value is a trap for the next consumer (a future Blender rabbet cut would invert).
- **Fix:** Store the physical quantity: `CONFIG['FRONT_RIM_WIDTH_IN'] = calc_rim_width` and derive everywhere from that (the bezel/back functions already compute `rim_width` — pass it instead of the negated field); set the same key in `generate_headless.py`. Add a `# mm` / `# in` suffix convention or `_MM`/`_IN` naming for every CONFIG key touched.
- **Confidence:** CONFIRMED for the sign/semantics and the headless divergence (code read); no runtime effect on current SVG output.

### [M6] MEDIUM — Spec drift: USER_SPECIFICATIONS.md vs current code
- **Where:** `USER_SPECIFICATIONS.md` SPEC-004/SPEC-007 (both "ACTIVE") vs cnc_generator.py:962 ("v48 UPDATE: Rails DO NOT have rabbets") and the stepped-plug design; SPEC-008 (viewport clip ≤ 0.001 m) vs blender_generator.py:1066 (`clip_start = 0.01`); SPEC-009 (exposure 2.5) vs blender_generator.py:1050 (`exposure = 4.0`)
- **Category:** grounding
- **Problem:** The spec log — explicitly maintained as the conflict-check authority — no longer matches the implementation: rails have no receiving rabbets, the bezel rabbet is `stock+gap` wide (not 5/16"), the Blender viewport clip is 10× the spec, exposure is 4.0 vs 2.5. The TriVision variant sets clip 0.001 correctly (blender_generator.py:1840 region), showing which side drifted.
- **Impact:** The next "verify against previous specifications" pass (the file's stated workflow) will either falsely flag correct code or bless violations; close-up joinery inspection in Blender clips 10 mm early.
- **Fix:** Set `clip_start = 0.001` and `exposure = 2.5` in the Blender template (or record why 4.0 superseded 2.5); update SPEC-004/007 to SUPERSEDED with a pointer to the v48 plug design, or mark them so with dates.
- **Confidence:** CONFIRMED (text vs code); which side is authoritative for exposure is a user decision — flag, don't silently pick.

### [M7] MEDIUM — Both test scripts target stale or nonexistent files
- **Where:** test_gen.py:15 (loads `CNC GENERATOR - CARBIDE-OPTIMIZED v1.26.py`, the abandoned monolith); test_layout.py:14 (references `CNC GENERATOR - Claude v1.04.py`, which does not exist) and :28 (scans for `CNC Box Generator v*` folders, a naming scheme no longer produced)
- **Category:** robustness
- **Problem:** The only test harnesses in the repo exercise a superseded file or nothing at all; the live `cnc_generator.py` has zero automated coverage.
- **Impact:** Every defect above shipped without a tripwire; the C1 overlap sat in the flagship output file.
- **Fix:** Repoint test_gen.py at `cnc_generator.py` (it is import-safe: the mainloop is under `__main__`), and fold the acceptance checks below into it as assertions rather than prints.
- **Confidence:** CONFIRMED (file list; `CNC GENERATOR - Claude v1.04.py` absent from the tree).

### [L1] LOW — Dead and duplicated code that will drift
- **Where:** cnc_generator.py:467–473 vs 521–528 (two identical `compute_finger_layout` definitions — second silently shadows the first), 1696 & 1704 (unreachable `BOTTOM_HATCH_LID`/`BOTTOM_HATCH_CUT` branches — see C2/H1), 1716–1717 (never-populated `BOTTOM ACCESS` buffers), 1875–1877 (`run_generation_patch` marker function), 636–662 (top/bottom finger-edge branches no caller uses)
- **Category:** maintainability
- **Problem/Impact:** Each is harmless today; the duplicate finger-layout function is the dangerous one — an edit to the first definition does nothing, which is exactly how a future joinery fix silently fails to land.
- **Fix:** Delete the first `compute_finger_layout`, the marker function, and the unreachable branches as part of the C2/H1 rework.
- **Confidence:** CONFIRMED.

### [L2] LOW — BinPacker 48×96 expansion never reverts on failure
- **Where:** cnc_generator.py:1245–1263 (`sheet['h'] = 96.0` then `pass` on the no-fit path)
- **Category:** correctness
- **Problem:** When expansion doesn't help, the sheet's height stays 96 anyway; later items and the canvas-size calculation treat it as a 48×96 sheet.
- **Impact:** Oversized master canvas / items placed on a phantom lower half of a sheet the user cuts as 48×48. Only bites with part sets big enough to trigger expansion attempts.
- **Fix:** Restore `sheet['h'] = original_h` in the else branch (the variable is already captured at 1251).
- **Confidence:** CONFIRMED by read; construct a >48" part set to observe.

### [L3] LOW — Version and title mismatches
- **Where:** cnc_generator.py:2775 (UI badge "v1.24" vs file header v1.25), 1977 vs 1981 (SVG `<title>BACK_PANEL_HOLES` inside file named `BACK_PANEL_HOLES_THROUGH…`, so the Illustrator layer name diverges from the filename convention every other file follows)
- **Category:** maintainability
- **Fix:** Bump the badge string; pass `"BACK_PANEL_HOLES_THROUGH"` to `create_svg_header`.
- **Confidence:** CONFIRMED.

### [L4] LOW — Auto-installer retries pip with `--break-system-packages` on system Python
- **Where:** cnc_generator.py:71–75
- **Category:** robustness
- **Problem:** On any non-venv run (e.g. double-clicking with system Python), a failed `pip --user` install is retried mutating Homebrew/system site-packages without asking.
- **Impact:** Can corrupt the system Python environment on a machine this app is copied to ("resizable in case it is used on a different machine" implies such copies).
- **Fix:** Replace the retry with a printed instruction to create/activate the venv (one exists in the project root) and exit.
- **Confidence:** CONFIRMED code path; environment-dependent to trigger.

## Cross-cutting
- **Filename-substring dispatch is the module's systemic weakness.** C2, H1, H2, and both L1 dead branches are all the same root defect: `get_layer_type_v11` classifies whole files by fragile substring order, while several files legitimately contain mixed cut types. Route by element stroke color (the per-part generators already encode semantics in color) and the entire class disappears.
- **One physical parameter, three names.** The glue gap lives as UI `glue_gap` → `FIT_TOLERANCE`, phantom `GLUE_GAP`, and negated `FRONT/BACK_RABBET_WIDTH` (H5, M5). Pick one CONFIG key with one unit and derive the rest at point of use.
- **The master layout has no post-generation invariant checks** (M1): non-overlap, non-negative coordinates, and per-part bbox-vs-packed-cell agreement are all cheap to assert at generation time and would have caught C1 before it reached a shipped file.
- **The Blender template is the drifted twin.** The TriVision variant defines `half_*` before use and honors the clip-start spec; the Blender variant fails both (H4, M6). When fixing, diff the two templates and converge on the TriVision ordering.

## Do not regress
- The half-round finger/socket math in `generate_perimeter_with_fingers` (cnc_generator.py:589–794) is correct and load-bearing: odd symmetric finger count from `compute_finger_layout`, both mating edges derived from `BOX_DEPTH` so counts always agree, `FIT_TOLERANCE` shrinks males only, and first/last fingers snap flush to the outer edge (lines 686–690, 764–768). C1's fix must not alter path geometry — only packing dims and placement transforms.
- Assembled-dimension identities: horizontal rail body `TOTAL_WIDTH − 2·stock` + finger protrusion `stock − fit_tol` per side; vertical rails full `TOTAL_HEIGHT` with sockets `stock` deep. These produce the correct outer box; don't "fix" them while fixing the packer.
- Per-part SVG color semantics (red perimeter / blue holes / orange rabbets / purple window / green pockets) are correct in every individual file — H1/C2 fixes belong in the master-layout flattening only.
- Output-folder versioning (`McTell SVGs v{n+1}`, scan at cnc_generator.py:3196–3205) and settings persistence round-trip work; keep them.
- The unit-toggle conversion in `handle_unit_toggle` (in↔mm on existing field values) is correct; H5/M5 key consolidation must not touch it.

## Acceptance checks
Run from `Gemini McTell CNC Plans/` with the project venv. Checks 1–3 gate the criticals; run check 1 after every fix since it regenerates the master.

1. **[C1] No overlap, no off-sheet geometry.** Drive a generation with the v134 settings (14×14×2.5 in, stock 15.19936 mm, gap 0, window 13×13, cleats/hatches off — `test_gen.py` repointed per M7 works), then:
   ```python
   import re
   svg = open(sorted(__import__('glob').glob('McTell SVGs v*/MASTER_LAYOUT_COMBINED_v*.svg'))[-1]).read()
   parts = {}
   for d, tf, pid in re.findall(r'<path d="([^"]*)" [^>]*transform="([^"]*)" id="(\w+_OUTSIDE_CUTS)"', svg):
       n = [float(x) for x in re.findall(r'-?\d+\.?\d*', d)]
       t = re.findall(r'translate\(([-\d.]+),\s*([-\d.]+)\)', tf); rot = 'rotate(90)' in tf
       (a,b),(c,e) = map(lambda p:(float(p[0]),float(p[1])), t)
       pts = [((x+c), (y+e)) for x,y in zip(n[0::2], n[1::2])]
       if rot: pts = [(-y, x) for x,y in pts]
       pts = [(x+a, y+b) for x,y in pts]
       parts[pid] = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
   assert all(v[0] >= -1e-6 and v[1] >= -1e-6 for v in parts.values()), f"off-sheet: {parts}"
   ks = list(parts)
   for i in range(len(ks)):
       for j in range(i+1, len(ks)):
           A, B = parts[ks[i]], parts[ks[j]]
           assert A[2] <= B[0]+1e-6 or B[2] <= A[0]+1e-6 or A[3] <= B[1]+1e-6 or B[3] <= A[1]+1e-6, f"OVERLAP {ks[i]} x {ks[j]}"
   print("C1 PASS")
   ```
   Must print `C1 PASS`. (Today it fails with `OVERLAP TOP_OUTSIDE_CUTS x BOTTOM_OUTSIDE_CUTS` and off-sheet min-x −0.0984.)
2. **[C3] Nested-hatch generation completes.** Same settings but `hatch_enabled=True` (window 13×13 forces nesting). Generation must produce a new `McTell SVGs v*` folder containing `MASTER_LAYOUT_COMBINED_v*.svg` with no `NameError` dialog/traceback.
3. **[C2]/[H1] Master layer semantics.** In the run from check 2, assert in the master SVG: the rear-hatch *shelf* rect's coordinates appear inside a path whose `data-name` is a rabbet/pocket bucket (not `INSIDE WINDOW`); the `HATCH_LID` inner-step rect and its 4 circles do *not* appear in any `*_OUTSIDE_CUTS` path.
4. **[H2] CSINK mapping.** With `cleats_enabled=True`, generate and assert every `a r r 0 1 0` circle arc from `CLEAT_WALL_HOLES_CSINK` coordinates lands in a path with `data-name="RABBET"`/pocket bucket, and `CLEAT_WALL_HOLES_THROUGH` circles land in `data-name="HOLE"`.
5. **[H3]/[H4]/[M4] Blender features render.** Generate with cleats + rear hatch (raise 1.0 in) enabled; in the emitted `OPEN_ME_IN_BLENDER.v*.py` assert: no occurrence of `== 'True'`; `half_d` is assigned before its first read (`grep -n "half_d"` — first hit is the assignment); emitted `'HATCH_RAISE_IN': 1.0`. Then run it in Blender 4.x: objects `McTell_Cleat_Box`, `McTell_Cleat_Wall`, `McTell_Hatch_Lid` must exist, hatch-lid center Z ≈ `(−H/2 + stock + 1.0·0.0254 + open_h/2)` within 1 mm.
6. **[H5] One glue-gap source.** `grep -n "GLUE_GAP" cnc_generator.py` returns nothing (or only the write `CONFIG['GLUE_GAP'] = CONFIG['FIT_TOLERANCE']`). With glue gap 0.4 mm, rear-hatch and bottom-hatch flange widths in the emitted SVGs must be equal: `stock/2 − 0.4 mm`.
7. **[H6] Window/plug guard.** With the v134 settings (window 13 on plug 12.803), generation must emit a visible warning (or clamp) naming both numbers; with window 12.0 it must stay silent.
8. **[H7] Lid clearance.** With gap 0.4 mm, assert in the emitted SVGs: rear `HATCH_LID` outer rect width == shelf rect width − 0.8 mm (in inches: −0.0315), and lid plug width == opening width − 0.8 mm. Same for the bottom hatch.
9. **[M3] Degenerate window suppressed.** Generate with window enabled and empty size fields: no `FRONT_BEZEL_WINDOW.v*.svg` is written and the master contains no `*_INSIDE_WINDOW` path for FRONT.
10. **[L2] Expansion revert.** Unit-test `BinPacker`: pack one 47×47 item then one 50×47 item; after packing, every sheet with no item taller than 48 has `h == 48.0`, and no item's bbox exceeds its sheet.

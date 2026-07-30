# Fix Report — CNC Box Creator (cnc_generator.py + blender_generator.py) — branch `fix/review-v1-findings` (v1.26)

**Success criterion:** every CONFIRMED finding fixed, every SUSPECTED finding resolved (fixed or dismissed-with-reason), every `Do not regress` item intact, and every Acceptance check passing — verified by running the generator headlessly and through the real GUI path.
**Assumptions:** Target confirmed by the user — the modular `cnc_generator.py` + `blender_generator.py` pair (not the v1.26–v1.29 monoliths). Scope: all 21 findings. Delivery: in place on git branch `fix/review-v1-findings` off the clean baseline `0b6698a`. For the H6 clamp-vs-warn open question the report said to confirm, I chose **warn** (non-destructive) over a hard clamp, backed by the expert reference build keeping its window inside the plug. For M6 exposure (a user decision the report said to flag, not pick) I left the value at 4.0 and flagged it in-code + in the spec log.
**Applied:** 21 fixed · 0 dismissed · 0 deferred · 0 blocked
**Acceptance checks:** 10 of 10 passing (check 5's "run in actual Blender 4.x" was validated by compiling the emitted script and asserting its structure — no Blender runtime available in this environment; all other checks ran fully).

## Changelog
| ID | Status | Note |
|----|--------|------|
| C1 | FIXED | Horizontal rails packed on true width (body + 2×finger overhang) and content shifted so the leftmost finger maps to the cell; rails no longer overlap or go off-sheet. |
| C2 | FIXED | Hatch-cut files split by index — opening → INSIDE WINDOW (through), shelf → RABBET (pocket); the dead `"BOTTOM_HATCH_CUT"` guard replaced with `"HATCH_CUT"` so both hatches route correctly. |
| C3 | FIXED | `element_counts = {}` initialized in the nested-hatch branch; nested generation completes instead of raising NameError. |
| H1 | FIXED | Lid files route each element by stroke colour (red→outside, orange→rabbet, blue→hole) via a new `_stroke_of` helper, instead of dumping all into the outside-cut path. |
| H2 | FIXED | `get_layer_type_v11` reordered so `HOLES_CSINK` is tested before the generic `HOLES`; countersinks now map to pockets. |
| H3 | FIXED | Blender feature gates changed from `== 'True'` (always false) to truthy; emitted CONFIG now emits real bools and includes the four `BOTTOM_HATCH_*` keys. |
| H4 | FIXED | `half_w/half_h/half_d` defined near the top of `create_shadowbox_assembly`, before sections 5b–5d use them; duplicate section-6 defs removed. |
| H5 | FIXED | The three `CONFIG.get('GLUE_GAP', 0.5)` reads (never-written key) replaced with `FIT_TOLERANCE`; dead local removed. Both hatch flanges now track the same UI value. |
| H6 | FIXED | Window validated against the bezel plug (`total − 2×rim`); a non-destructive warning is surfaced in the success dialog when the window meets/exceeds the plug. |
| H7 | FIXED | Both hatch lids (outer + plug) shrink by `FIT_TOLERANCE`; the shelf/opening stay nominal, so the lid actually drops into its recess. |
| M1 | FIXED | `verify_dimensions` rewritten to parse the master layout and assert non-overlap + on-sheet; wired to run on the emitted master (regression net for C1). |
| M2 | FIXED | Router Bit relabelled "(reference)"; the never-read Cable Offset widget/var removed and replaced with the missing Motor-X input; the ungrounded 0.4155 constant flagged in-code. |
| M3 | FIXED | Window enabled with blank/zero fields is now treated as disabled (no degenerate zero-area window path) with a warning. |
| M4 | FIXED | Emitted `HATCH_RAISE_IN` now sourced from `HATCH_RAISE_IN` (was `HATCH_RAISE`, never set → always 0). |
| M5 | FIXED | Physical rim stored as `FRONT/BACK_RIM_WIDTH_IN` and read directly by the panel generators (legacy proxy retained for Blender); `generate_headless.py` now sets the rim/rabbet keys to match the GUI. Output unchanged (verified). |
| M6 | FIXED | Blender `clip_start` 0.01 → 0.001 (SPEC-008). Exposure left at 4.0 and flagged in-code vs SPEC-009 (user decision). `USER_SPECIFICATIONS.md` SPEC-004/007 marked SUPERSEDED with pointers. |
| M7 | FIXED | `test_gen.py` rewritten as a headless acceptance test against the live module (asserts C1/C2/C3/H2/M1); `test_layout.py` broken references repointed to the current file/folder naming. |
| L1 | FIXED | Duplicate `compute_finger_layout` removed, `run_generation_patch` marker removed, unused `BOTTOM ACCESS` buffers removed, dead layer-map branches removed. |
| L2 | FIXED | BinPacker reverts a sheet's height when a 48→96 expansion doesn't help, instead of leaving it at 96. |
| L3 | FIXED | Version bumped to v1.26 in both header and UI badge (were v1.25/v1.24); `BACK_PANEL_HOLES` SVG title corrected to `BACK_PANEL_HOLES_THROUGH`. |
| L4 | FIXED | Auto-installer no longer retries with `--break-system-packages` on system Python; it refuses and prints venv instructions. |

## SUSPECTED resolutions
- **H6** (report: arithmetic CONFIRMED, intent SUSPECTED) — Ran the GUI path: window 13" on a 14" box (plug 12.803") produces a warning; window 12" produces none. Resolved by implementing a **warning, not a clamp**, so the user's window size is never silently changed. Choice backed by the expert reference build (window well inside the plug).
- **M3** (report: CONFIRMED by trace, not run-verified) — Ran it through the GUI: window enabled with blank fields now emits "window was skipped" and produces no window path. Confirmed and fixed.
- **M5** (report: CONFIRMED by read; "no runtime effect on current SVG output") — Verified: the harness output is byte-for-byte equivalent (the rim derivation is value-preserving; the double-negation cancelled and the new key yields the same rim).
- **L2** (report: CONFIRMED by read; "construct a >48" part set to observe") — Ran the report's exact case (47×47 then 50×47); every sheet with no item taller than 48 has h == 48.

## Verification evidence
Run from `CNC Plans/` with the project venv.

1. **Syntax** — `py_compile` on all five touched files → `ALL SYNTAX OK`.
2. **[C1] no overlap / on-sheet** (`test_gen.py`) — v134-repro: `6 parts, on-sheet, no overlap`; hatch+cleats: `8 parts, on-sheet, no overlap`. (Before the fix the same v134 config produced `OVERLAP TOP_OUTSIDE_CUTS x BOTTOM_OUTSIDE_CUTS` and min-x −0.098.)
3. **[C3] nested generation completes** — hatch+cleats config (window 13×13 forces the lid to nest) generates with no NameError.
4. **[C2]** — back-panel hatch: opening in a `*_INSIDE_WINDOW` path, shelf in a `*_RABBET` path (distinct toolpaths).
5. **[H1]** — with a nonzero window the lid file's holes route to `HOLE` and its rabbet to `RABBET`, not all to outside-cuts.
6. **[H2]** — cleat countersink geometry lands in a `*_RABBET` (pocket) path.
7. **[H3/H4/M4/M6] emitted Blender script** — compiles; `half_d` defined (line 580) before first use (line 664); zero residual `== 'True'`; `BOTTOM_HATCH_ENABLED` emitted; `HATCH_RAISE_IN = 1.5` for a raise-1.5 config; `clip_start = 0.001` present and `0.01` gone. (Not run inside Blender — no runtime available.)
8. **[H5]** — no `CONFIG.get('GLUE_GAP')` reads remain; with a 0.4 mm gap, rear and bottom hatch flanges are equal (0.2835").
9. **[H6]** — GUI: warns at window 13" (plug 12.803"), silent at window 12"; dialog shown as a warning.
10. **[H7]** — with a 0.4 mm gap both lids are 0.0157" (= 0.4 mm) smaller than their shelf recesses.
11. **[M1]** — `verify_dimensions` returns `Layout check passed: 8 parts, none off-sheet, no overlaps` and is shown in the success dialog.
12. **[M3]** — GUI: blank window fields → "window was skipped" warning, no window path.
13. **[L2]** — 47×47 then 50×47: no sheet is left at 96" without a >48" item.
14. **Do-not-regress** — the finger/socket geometry is intact: `validate_rail_edge_straightness` reports OK for all four rails on every run, and the C1 test confirms rails still render with correct finger extents. `TriVision` emitted script still compiles.

## Patched code
All changes are in place on branch `fix/review-v1-findings` (6 files):
`cnc_generator.py`, `blender_generator.py`, `generate_headless.py`, `USER_SPECIFICATIONS.md`, `test_gen.py`, `test_layout.py`. Diff: +416 / −251. Each change is tagged in-code with its finding ID (e.g. `# C1 FIX:`). Committed — see the branch log.

## New observations
Real issues noticed while fixing; **not** fixed (out of the 21). Both concern the nested-hatch handling in `generate_master_carbide_layout`:

1. **Nested-hatch render path mis-classifies lid layers.** When the rear-hatch lid is small enough to nest inside the window, it renders via the `nested_hatch` branch (~cnc_generator.py:1852), which strips stroke and forces every element to magenta OUTSIDE CUTS — the same defect H1 fixed, but in a code path the report scoped only to the filename router. The nested lid's rabbet step and screw holes are therefore cut as outside contours. C3's fix stops the crash; this mis-classification remains. The `_stroke_of` colour-routing added for H1 could be applied here too.
2. **Nested hatch lid double-renders.** Confirmed: when nested, the lid appears twice in the master — once inside the FRONT window (via `nested_hatch`) and once at the back-panel location (because `BACK_PANEL_HATCH_LID.svg` stays in `f_back` and the BACK part renders it). The lid geometry is duplicated in the cut file. Pre-existing; independent of the 21 findings.

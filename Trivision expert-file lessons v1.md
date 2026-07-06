# Lessons from the Expert's Canonical Build — Trivision PLS NEW V2

**Source:** `07.01.26 Trivision PLS NEW V2.f3z` (Fusion 360 archive), read live from the open Fusion document via the Fusion MCP — all dimensions below measured from the model, not estimated.
**What the file is:** one document holding both generations. The hidden `Assembled` group is the app's own output imported into Fusion (its Back Panel measures 62.4594 × 43.4594 × 0.5984 in — exactly the parameters in `verify_encasement.py`). The visible `NEW FRAME` group is the CNC expert's rebuilt, canonical version. That makes this a measurable before/after of everything the expert had to change.
**Headline delta:** app output 62.459 × 43.459 × 5.098 in → expert build 68.252 × 43.897 × 6.697 in overall, plus roughly a dozen parts the app never generates.

---

## The measured facts (expert model)

| Feature | Measured value |
|---|---|
| Outer box (assembled) | 68.2522 × 43.8969 × 6.697 in |
| Outer frame depth (rails) | 6.0985 in; stock 0.5906–0.5984 in (15 mm class) |
| Corner box joints | 9 equal fingers × 0.6776 in (17.21 mm) across the 6.0985 in depth; sockets exactly stock-deep; **0.0000 in clearance** (nominal, line-to-line) |
| Front frame / back panel | Full outer footprint (68.25 × 43.90); each sits **0.299 in (= stock/2) into** the frame and stands **0.299 in proud** — the app's stepped-panel concept, confirmed at exactly half stock |
| Front window opening | 62.1819 × 36.8268 in (face border 3.04 in) |
| Plexi pane (QTR PLEXI) | 0.25 in thick, 62.9319 × 37.5768 in = **window opening + 0.750 in** (⅜ in lip per side); floats 0.015 in behind the frame; retained by 4 corner brackets 3 × 3 × stock, each with 2 × 5 mm screw holes |
| Rear access opening | 60.185 × 9.721 in; lid 61.466 × 10.905 → **flange ≈ 0.59–0.64 in per side (≈ full stock)**; lid rests line-to-line, **no fasteners** |
| French cleats | Wall cleat **56 in**, panel cleat **46 in** (10 in of lateral adjustment); 45° engagement overlap 0.47 in with 2.1 mm hang clearance; panel cleat centered ~30% down from box top; plus a **bottom spacer strip 46 × 2 × stock** to hang plumb |
| Double wall | Inner liner frame nested inside the outer frame with a **0.300 in (7.6 mm) wall gap**; liners 66.44 in long |
| Bottom liner = motor/bearing plate | 12 stations at ~5.54 in pitch: per station 4 × 3.5 mm pilots, 4 × 5.3 mm clearance, 2 × 7.5 mm bearing holes (120 holes total); 11 separate bearing blocks 1.68 × 0.30 × 2.85 in with the same hole set |
| Top liner | 12 stations: 2 × ⅛ in pivot holes + 1 × 5 mm hole each |
| Other holes | 1 × ½ in pass-through in outer bottom (cabling); 5 mm holes in back panel, brackets, spacer |
| Dogbones | **None anywhere** — zero cylindrical faces on any joint; inside corners left square (nominal), consistent with the app's manual-roundover philosophy |
| Electronics | Arduino Mega placed as an XRef; motor plate merged into the bottom liner (matches the NEMA-17 stepper STEP file already in the repo) |
| Parameters | **No user parameters.** The expert's timeline is imports + ~50 `OffsetFaces`/`Move`/`Scale` edits — every one of them is a dimension the app got wrong or never exposed |

---

## Lessons for the generalized app

### 1. The window is an assembly, not a hole
The expert treats glazing as three coordinated parts: the opening, a plexi pane cut to **opening + 2 × ⅜ in lip**, and **4 corner retainer brackets** (3 × 3 × stock, two 5 mm screw holes each) that clamp the pane behind the frame. The app cuts only the opening.
**Change:** when the window is enabled, also emit a `PLEXI_PANE` outline (opening + 2 × lip; lip parameter, default 0.375 in), 4 `BRACKET` parts, and bracket screw pilots — and include the pane thickness (default 0.25 in) in the depth stack.

### 2. Half-stock panel steps are confirmed — keep them, and validate the window against the plug
The expert's front/back panels are full outer size, stepped **exactly stock/2** into the frame and proud stock/2 — precisely the app's v48+ plug design and `step_depth = stock/2`. This is independent expert validation of the current architecture. His window (62.18 in) sits far inside the structural plug; the app's own last output (window 13.0 in vs plug 12.8 in) violated this. Reinforces review finding **H6**: enforce `window ≤ plug − margin`.

### 3. CAD stays nominal; fit lives only in the CAM layer
Every mating pair in the canonical model measures **0.0000 in clearance** — fingers, sockets, lid, brackets. The expert models nominal geometry and lets tooling/CAM produce the fit. The app instead bakes the glue gap into all outputs, including the 3D exports.
**Change:** keep `FIT_TOLERANCE` in the CAM-facing SVGs only; generate the Blender/Fusion/TriVision geometry nominal (no pre-shrunk fingers). A downstream expert should never inherit invisible baked-in gaps. (The SVG-side lid clearance from review finding **H7** still stands — that layer is where fit belongs.)

### 4. Access lid: full-stock flange, no fasteners
Expert flange is ≈ 0.6 in per side (≈ full stock); the app computes `stock/2 − gap` ≈ 0.28 in — half as much bearing surface. The expert's lid also has zero screw holes (gravity/friction fit).
**Change:** make flange width a parameter defaulting to ~1 × stock, and make the 4 corner screws optional (default off).

### 5. A French-cleat *system* is three parts
The expert hangs the box on: a **wall cleat 10 in longer than the panel cleat** (lateral adjustability), the panel cleat mounted ~30% down from the top (close to the app's ⅓ rule — keep it), and a **bottom spacer strip** (panel-cleat length × 2 in × stock) so the box hangs plumb. The app makes two equal-length cleats and no spacer.
**Change:** wall cleat = panel cleat + ~10 in (cap at sheet width); always emit the spacer strip with its mounting holes.

### 6. The finger-joint algorithm survives expert review
Nine equal fingers, odd count, sockets exactly stock-deep, flush outer faces — the expert's corners are structurally identical to what `compute_finger_layout` + the perimeter generator produce. Only his target width is larger (17.2 mm vs the 15 mm default) on this big box. Zero dogbones confirms the manual-roundover approach.
**Change:** none to the math (protect it — it is in the review's do-not-regress list). Consider scaling default finger width with box size instead of a fixed 15 mm.

### 7. Holes are a fastener-driven system, not a single radius
The expert uses a consistent three-tier hole vocabulary: **3.5 mm pilot**, **5.3 mm clearance**, **7.5 mm bearing**, plus ⅛ in pivots, 5 mm mounting holes, and a ½ in cable pass-through. The app hardcodes `hole_r = 0.1` for nearly everything.
**Change:** define hole types (pilot / clearance / countersink / bearing / pass-through) with per-fastener defaults, and let each feature reference a type. This also subsumes review finding **H2** (countersinks must stay pockets).

### 8. Interior-first sizing is the real spec
The box grew ~5.8 in wider and 1 in deeper because the *contents* dictate size: 12 prism stations at 5.54 in pitch, a 0.30 in wall gap, motor bay, plexi stack-up. The app sizes exterior-first; `verify_encasement.py` (inner object + clearance) was a one-off hardcoded attempt at the right idea.
**Change:** add an interior-driven mode — user enters interior payload (or N stations × pitch + margins) and the app derives exterior dims. At minimum, display the computed interior dimensions live in the UI so a mismatch is visible before cutting.

### 9. Equipment boxes want a double wall
The expert nests an inner liner frame (carrying all 120 bearing/pilot holes) inside the structural outer frame, 0.30 in apart. Structure and mechanism mounting are separated — holes live in the sacrificial/replaceable liner, not the box walls.
**Change (larger feature):** optional "liner" sub-frame at a configurable wall offset, with a repeating station-hole pattern (N stations, pitch, hole set per station). The 11 bearing blocks suggest a companion small-part strip the nesting layer should pack automatically.

### 10. Motor mounting is a plate with stations, not a pocket
The app's motor feature is a single NEMA-17 pocket in a rail at an ungrounded 0.4155 × width (review finding **M2**: no UI input reaches it). The expert instead merged a **motor mount plate** into the bottom liner and placed the Arduino beside it.
**Change:** replace/augment the motor pocket with a motor-plate template (NEMA pattern + shaft/bearing holes at station positions), and keep an electronics envelope (Arduino footprint) in the depth/width check.

### 11. Meta-lesson: every `OffsetFaces` in the expert's timeline is a missing parameter
The expert never created a single user parameter — he brute-forced ~50 face offsets, moves, and scales on imported dumb solids. That is the cost of the app exporting non-parametric geometry with wrong or inflexible dimensions. Two remedies, in order of value:
1. Get the numbers in this table into the app as defaults/parameters (lips, flanges, cleat deltas, wall gap, hole tiers) so the output is right the first time.
2. Make the Fusion export parametric — emit user parameters (`stock`, `depth`, `window_w`, …) wired to the sketches (the `DXF_for_Fusion` experiment in `McTell SVGs v131` is the seed), so the next expert adjusts a value instead of rebuilding the frame.

---

## Suggested priority

Quick wins that change cut files directly: **1** (plexi + brackets), **4** (lid flange), **5** (cleat system + spacer), **7** (hole types). Structural but high-value: **3** (nominal 3D), **8** (interior-first sizing). Larger features to scope with Joel: **9** (liner sub-frame), **10** (motor plate), **11.2** (parametric Fusion export). Items **2** and **6** are validations — protect existing behavior and finish review findings H6/H7/H2.

*Caveats:* the wall cleat's 213-face body includes non-planar surfaces I did not fully classify (likely slotted mounting features — worth a visual check in Fusion before copying its hole pattern). Station count (12) and pitch (5.54 in) are project-specific to this trivision sign; the lesson is the parametric pattern, not those constants.

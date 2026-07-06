# USER SPECIFICATIONS LOG

## Shadowbox v66 - Fusion 360 3D Assembly

This log tracks all user specifications and requirements. Before making any change, verify it does not conflict with or undo previous specifications.

---

### SPEC-001: Box Dimensions

- **Date**: 2026-01-24
- **Requirement**: 25" × 25" × 10" assembled box
- **Stock thickness**: 0.5906" (15mm Baltic Birch)
- **Status**: ACTIVE

### SPEC-002: Part Assembly

- **Date**: 2026-01-24
- **Requirement**: 6 parts assembled in 3D representation
  - TOP_Body, BOTTOM_Body (horizontal rails with finger joints)
  - LEFT_Body, RIGHT_Body (vertical rails with finger joints)
  - FRONT_Body (bezel with window)
  - BACK_Body (panel)
- **Status**: ACTIVE

### SPEC-003: FRONT_Body Window Cutout

- **Date**: 2026-01-24
- **Requirement**: 8" × 8" centered window cutout in FRONT_Body
- **Details**: Through-cut, not a pocket
- **Verification**: Body should have >6 faces (10 faces minimum with window)
- **Status**: ACTIVE

### SPEC-004: FRONT_Body Rabbet

- **Date**: 2026-01-24
- **Requirement**: 0.3125" (5/16") rabbet around perimeter of FRONT_Body
- **Details**: Cut on inside face, half-stock depth (~0.295")
- **Purpose**: Creates visible inside edge when panel is inset into frame (matches BACK_Body behavior)
- **Verification**: Body should have ~15 faces (with both window and rabbet)
- **Status**: SUPERSEDED (2026-07-06) — the fixed-5/16" rabbet was replaced by the v48+ stepped-plug
  design: the plug rim = stock + glue gap + lid-fit adjustment (see `generate_front_bezel_parts`
  / `FRONT_RIM_WIDTH_IN`). Kept for history; do not conflict-check current code against the 5/16" value.

### SPEC-006: FRONT_Body Position (Inset)

- **Date**: 2026-01-24
- **Requirement**: FRONT_Body sits INSIDE the frame with rabbet nestled against rails
- **Details**: Rabbeted inner portion at Y = -5", outer lip overlaps rail faces
- **Position**: Y = -5.30" to -4.70" (moved inward by rabbet depth 0.295")
- **Status**: ACTIVE

### SPEC-007: Rail Receiving Rabbets

- **Date**: 2026-01-24
- **Requirement**: All 4 rails (TOP, BOTTOM, LEFT, RIGHT) have receiving rabbets on BOTH front and back edges
- **Rabbet width**: 0.2781" (per SVG)
- **Rabbet depth**: ~0.295" (half stock, to receive panel rabbets)
- **Purpose**: Creates pocket for FRONT and BACK panels to nestle into
- **Status**: SUPERSEDED (2026-07-06) — from v48 the rails DO NOT carry receiving rabbets
  (see `generate_rail_parts`, "v48 UPDATE: Rails DO NOT have rabbets"). The panels self-register
  via the stepped plug instead. Kept for history.

### SPEC-008/009 note (2026-07-06)

Blender viewport `clip_start` is now 0.001m per SPEC-008 (was 0.01m). SPEC-009 specifies scene
exposure 2.5, but `blender_generator.py` sets 4.0; this is flagged in-code and left for a
deliberate decision (update the spec or set the code to 2.5) rather than changed silently.

### SPEC-005: Material Appearance - Baltic Birch

- **Date**: 2026-01-24
- **Requirement**: Baltic Birch plywood appearance (not Pine with fake knots)
- **Face color**: #E2CBAD
- **End grain color**: #C0AD93
- **End grain texture**: 11-ply striped pattern visible on edges
- **Status**: ACTIVE

### SPEC-008: Blender Viewport Settings

- **Date**: 2026-01-26
- **Requirement**: Viewport `Clip Start` must be set to 0.001m (1mm) or lower to allow close-up inspection without geometry clipping.
- **Details**: Default Blender clipping (0.1m) makes checking tight joinery impossible. Script must enforce this setting on all 3D Views.
- **Status**: ACTIVE

### SPEC-009: Blender Lighting & Exposure

- **Date**: 2026-01-26
- **Requirement**: Visualization must use specific lighting settings for consistency.
- **Light**: Type = Area, Power = 5 W/Energy.
- **Exposure**: Scene Exposure = 2.5.
- **World Background**: Strength = 0.020.
- **Status**: ACTIVE

### SPEC-010: Finder File Colors

- **Date**: 2026-01-26
- **Requirement**: "OPEN_ME_IN_BLENDER" and "MASTER_LAYOUT_COMBINED" files must be tagged Green (Label Index 6) in Finder upon generation.
- **Status**: ACTIVE

---

## CONFLICT CHECK TEMPLATE

Before implementing any change, verify:

- [ ] Does not remove FRONT_Body window cutout (SPEC-003)
- [ ] Does not remove FRONT_Body rabbet (SPEC-004)
- [ ] Maintains correct box dimensions (SPEC-001)
- [ ] All 6 parts remain in assembly (SPEC-002)
- [ ] Baltic Birch appearance preserved (SPEC-005)

---

## CHANGE LOG

| Date | Change | Specs Verified | Notes |
|------|--------|----------------|-------|
| 2026-01-24 | Created 3D assembly | SPEC-001, SPEC-002 | Initial creation |
| 2026-01-24 | Added window to FRONT_Body | SPEC-003 | 8"×8" centered |
| 2026-01-24 | Added rabbet to FRONT_Body | SPEC-003, SPEC-004 | Verified window preserved (15 faces) |
| 2026-01-24 | Moved FRONT_Body inside frame | SPEC-003, SPEC-004, SPEC-006 | Back face at Y=-5", all features preserved (15 faces) |
| 2026-01-24 | Adjusted FRONT_Body for rabbet fit | SPEC-003, SPEC-004, SPEC-006 | Moved inward by 0.295" so rabbet nestles against rails, 15 faces preserved |
| 2026-01-24 | Added receiving rabbets to all rails | SPEC-003, SPEC-004, SPEC-007 | Front+back rabbets on TOP/BOTTOM/LEFT/RIGHT, FRONT_Body 15 faces preserved |

### PROJECT CLOSET LOG

- **Date**: 2026-01-25
- **Action**: Moved clutter files to `PROJECT CLOSET/` to clean up workspace
- **Moved Items**:
  - `__pycache__`
  - `! Github EvilHacker BoxJoint-main`
  - `Box_Creator copied from Vetric app`
  - `ghostphone_gen.py`
  - `import ezdxf.py`
  - `Launch_Generator.command`
  - `CNC_Generator_GUI.py`
  - `CNC Plans/Generator.iconset`
  - `CNC Plans/dist` (Contains The Built App)
  - `CNC Plans/build`
  - `CNC Plans/Rabbet Visualization from Blender`
  - `CNC Plans/build_app.sh`
  - `CNC Plans/*.spec`
  - `CNC Plans/*.icns`
  - `CNC Plans/*.icns`
  - `Blender Simuation` (Old v1/prototype files)
  - `fix_render_settings.py` (Blender color correction utility)
  - `generate_test_rail.py`
  - `Generator App Icon.png`
  - `MASTER_LAYOUT_v72.svg`
  - `new roundover profile.jpg`
  - `verify_svg_dimensions.py`
  - `verify_v50.py`
  - `Ghostphone_Shadowbox.svg`
  - `Shadowbox_Master_Plan.dxf`
- **Excluded**: `venv` (Must remain in place for Python environment to function)

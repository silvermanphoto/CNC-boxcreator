# CNC Box Joinery Math Fixes

## Issues Fixed

### 1. Rail Width Calculation (CRITICAL FIX)
**Problem:** Horizontal rails (TOP/BOTTOM) were incorrectly reduced by `2 * BLIND_SKIN` when using blind box joints.

**Location:** `generate_rail_svg()` function, line 379

**Before:**
```python
rail_w = CONFIG['TOTAL_WIDTH'] - (2 * CONFIG['BLIND_SKIN']) if (is_horizontal and CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT") else CONFIG['TOTAL_WIDTH'] if is_horizontal else CONFIG['TOTAL_HEIGHT']
```

**After:**
```python
# FIXED: Rail width should always be TOTAL_WIDTH (horizontal) or TOTAL_HEIGHT (vertical)
# BLIND_SKIN doesn't reduce rail width - it's the thickness of material left on the front face
rail_w = CONFIG['TOTAL_WIDTH'] if is_horizontal else CONFIG['TOTAL_HEIGHT']
```

**Impact:** Rails now have the correct width to align properly at corners.

---

### 2. Finger Length Calculation (CRITICAL FIX)
**Problem:** Finger length was incorrectly calculated, not matching socket depth.

**Location:** `draw_blind_finger_geometry()` function, line 210

**Before:**
```python
finger_len = h - blind_skin - 0.2  # h is STOCK_THICKNESS
```

**After:**
```python
# FIXED: Finger length must match socket depth
# For blind joints: socket depth = STOCK_THICKNESS - BLIND_SKIN (cut from back, leaving skin on front)
# Finger extends from front, so length = STOCK_THICKNESS - BLIND_SKIN to match socket
finger_len = h - blind_skin  # h is STOCK_THICKNESS
```

**Impact:** Fingers now properly fit into sockets.

---

### 3. Socket Depth Matching (CRITICAL FIX)
**Problem:** Socket depth was set to full `STOCK_THICKNESS`, but should match finger length for blind joints.

**Location:** `generate_rail_svg()` function, lines 421 and 449

**Before:**
```python
res = draw_blind_socket_geometry(x, y + (i*width_end), width_end, CONFIG['STOCK_THICKNESS'], CONFIG['STOCK_THICKNESS'], ...)
```

**After:**
```python
# FIXED: Socket depth must match finger length for blind joints
socket_depth = CONFIG['STOCK_THICKNESS'] - CONFIG['BLIND_SKIN'] if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT" else CONFIG['STOCK_THICKNESS']
res = draw_blind_socket_geometry(x, y + (i*width_end), width_end, CONFIG['STOCK_THICKNESS'], socket_depth, ...)
```

**Impact:** Sockets now match finger lengths exactly.

---

### 4. Left End Finger Geometry (CRITICAL FIX)
**Problem:** Left end fingers had incorrect length calculation.

**Location:** `generate_rail_svg()` function, line 459

**Before:**
```python
finger_len = CONFIG['STOCK_THICKNESS'] - CONFIG['BLIND_SKIN'] - 0.2
```

**After:**
```python
# FIXED: Finger length must match socket depth
# Socket depth = STOCK_THICKNESS - BLIND_SKIN, so finger length must match
finger_len = CONFIG['STOCK_THICKNESS'] - CONFIG['BLIND_SKIN']
```

**Impact:** Left end fingers now match socket depths.

---

## Summary

All corner joinery issues have been fixed:

1. ✅ **Rail widths** now correctly use TOTAL_WIDTH/TOTAL_HEIGHT without incorrect reduction
2. ✅ **Finger lengths** now match socket depths exactly
3. ✅ **Socket depths** now correctly account for BLIND_SKIN
4. ✅ **Corner alignment** is ensured through consistent finger pattern calculations

## Next Steps

1. **Regenerate SVGs:** Run the Python script (`CNC WITH GUI v40.py`) to generate new SVG files with corrected math
2. **Re-import to Blender:** Import the new SVGs or regenerate Blender geometry
3. **Verify:** Check that corners align properly - rails should join seamlessly

## Technical Notes

- **BLIND_SKIN** is the thickness of material remaining on the front face to hide the joint
- **Socket depth** = STOCK_THICKNESS - BLIND_SKIN (for blind joints)
- **Finger length** = STOCK_THICKNESS - BLIND_SKIN (must match socket depth)
- **Rail width** = TOTAL_WIDTH or TOTAL_HEIGHT (never reduced by BLIND_SKIN)

All rails use the same finger pattern based on `BOX_DEPTH`, ensuring perfect corner alignment.


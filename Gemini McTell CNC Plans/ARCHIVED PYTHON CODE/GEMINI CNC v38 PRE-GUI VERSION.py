#!/usr/bin/env python3
"""
McTell Parametric CNC Shadowbox Generator v38
=============================================
UPDATES v38:
- MOD: 'FRONT_BEZEL' Window Cutout is now PERFECTLY SQUARE.
       Removed tool-radius compensation arcs.
       (Note: CNC will still leave a radius in physical corners unless filed manually).
- LOGIC: Preserves v37 Blind/Half-Round switch and all v36 features.

OUTPUT:
- SVGs for all parts (Bezel, Rails, Back, Stops)
- x CAM_Instructions.txt
"""

import os
import math
import re
from pathlib import Path
from datetime import datetime

# ==============================================================================
# I. UNIT CONVERSION & UTILS
# ==============================================================================

def convert_to_mm(value, unit):
    if unit in ["inches", "in", '"']:
        return value * 25.4
    elif unit == "mm":
        return value
    else:
        raise ValueError(f"Unknown unit: {unit}")

def format_inches(value_mm):
    """Format dimension in inches, removing decimals for round numbers."""
    inches = value_mm / 25.4
    if abs(inches - round(inches)) < 0.001:
        return f'{int(round(inches))}"'
    else:
        return f'{inches:.2f}"'

def f(val):
    return f"{val:.4f}"

# ==============================================================================
# II. INTERACTIVE SETUP & GLOBAL STATE
# ==============================================================================

# Global Configuration Dictionary (Populated in main)
CONFIG = {}

def get_user_inputs():
    print("=" * 60)
    print("McTell Parametric CNC Generator v38 - Initialization")
    print("=" * 60)

    # 1. JOINERY SELECTION
    print("Please select a joinery method:")
    print("Available Methods:")
    print("(a) BLIND BOX JOINT (Blind mortises and tenons, with a \"skin\" hiding the joint)")
    print("(b) HALF-ROUND BOX JOINT (Fingers will be flush with mating surface)")
    
    joinery_choice = input("\nSelect (a/b): ").strip().lower()
    if joinery_choice == 'a':
        CONFIG['ACTIVE_JOINERY_METHOD'] = "BLIND_BOX_JOINT"
        CONFIG['BLIND_SKIN'] = 3.0 # Default mm
    elif joinery_choice == 'b':
        CONFIG['ACTIVE_JOINERY_METHOD'] = "HALF_ROUND_BOX_JOINT"
        CONFIG['BLIND_SKIN'] = 0.0
    else:
        print("Invalid selection. Defaulting to HALF_ROUND_BOX_JOINT.")
        CONFIG['ACTIVE_JOINERY_METHOD'] = "HALF_ROUND_BOX_JOINT"
        CONFIG['BLIND_SKIN'] = 0.0

    print(f"\nACTIVE METHOD: {CONFIG['ACTIVE_JOINERY_METHOD']}")

    # 2. VARIABLE MAPPING
    defaults = {
        1:  (15.0, "mm"),    # Material Thickness
        2:  (0.25, "in"),    # Tool Dia Primary
        3:  (0.125, "in"),   # Tool Dia Detail
        4:  (0.010, "in"),   # Glue Gap
        5:  (0.25, "in"),    # Tab Length (Gap to Frame)
        6:  (0.5, "in"),     # Tab Base Width
        7:  (15.0, "mm"),    # Target Finger Width
        8:  (3.0, "mm"),     # Blind Skin
        9:  (0.625, "in"),   # Back Rabbet Width
        10: (0.3, "in"),     # Back Rabbet Depth
        11: ("Y", "bool"),   # Motor Cutout?
        12: (0.25, "in"),    # Motor Pocket Depth
        13: (5.2, "mm"),     # Screw Pilot Dia
        14: (40.0, "in"),    # Total Width
        15: (40.0, "in"),    # Total Height
        16: (4.0, "in"),     # Box Depth
        17: (1.59, "in"),    # Bezel Width
        18: (0.84, "in"),    # Glass Overlap
        19: (0.5, "in"),     # Glazing Setback
        20: ("DEFAULT", "calc"), # Motor Pos X
        21: (3.0, "in")      # Cable Offset
    }

    print("\nPlease approve variables. Respond with numbered values (e.g., '1. 14.8, 14. 40.0'),")
    print("or simply hit Return to Accept Defaults.")
    print(f"1. Material Thickness (Def: 15mm)")
    print(f"5. Tab Length / Gap (Def: 0.25\")")
    print(f"6. Tab Base Width (Def: 0.5\")")
    print(f"14. Total Box Width (Def: 40.0\")")
    print(f"15. Total Box Height (Def: 40.0\")")
    print(f"16. Box Depth (Def: 4.0\")")
    
    user_resp = input("\nResponse: ").strip()
    
    overrides = {}
    if user_resp and user_resp.lower() != "accept defaults":
        matches = re.findall(r'(\d+)\.\s*([0-9\.]+)', user_resp)
        for num_str, val_str in matches:
            overrides[int(num_str)] = float(val_str)
    else:
        print("... Defaults Accepted.")

    def get_val(idx, unit_override=None):
        val, unit = defaults[idx]
        if idx in overrides:
            val = overrides[idx]
        if unit == "bool": return val
        if unit == "calc": return val
        return convert_to_mm(val, unit if unit_override is None else unit_override)

    CONFIG['STOCK_THICKNESS'] = get_val(1, "mm") 
    CONFIG['TOOL_D_PRIMARY'] = get_val(2)
    CONFIG['TOOL_R'] = CONFIG['TOOL_D_PRIMARY'] / 2.0
    CONFIG['FIT_TOLERANCE'] = get_val(4)
    CONFIG['TAB_PEAK'] = get_val(5) 
    CONFIG['TAB_BASE'] = get_val(6) 
    CONFIG['TAB_TIP'] = convert_to_mm(0.125, "inches") 
    
    CONFIG['TARGET_FINGER_WIDTH'] = get_val(7, "mm")
    if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT":
        CONFIG['BLIND_SKIN'] = get_val(8, "mm")
    else:
        CONFIG['BLIND_SKIN'] = 0.0 # Force 0 if not blind
    
    CONFIG['BACK_PANEL_RABBET_WIDTH'] = get_val(9)
    CONFIG['BACK_PANEL_RABBET_DEPTH'] = get_val(10)
    
    motor_enabled_raw = defaults[11][0]
    if 11 in overrides: motor_enabled_raw = "Y" 
    CONFIG['MOTOR_POCKET_ENABLED'] = True 
    
    CONFIG['NEMA_POCKET_DEPTH'] = get_val(12)
    CONFIG['SCREW_PILOT_DIA'] = get_val(13, "mm")
    
    CONFIG['TOTAL_WIDTH'] = get_val(14)
    CONFIG['TOTAL_HEIGHT'] = get_val(15)
    CONFIG['BOX_DEPTH'] = get_val(16)
    CONFIG['BEZEL_WIDTH'] = get_val(17)
    CONFIG['GLASS_OVERLAP'] = get_val(18)
    
    CONFIG['WINDOW_CUTOUT_WIDTH'] = CONFIG['TOTAL_WIDTH'] - (2 * CONFIG['BEZEL_WIDTH'])
    CONFIG['WINDOW_CUTOUT_HEIGHT'] = CONFIG['TOTAL_HEIGHT'] - (2 * CONFIG['BEZEL_WIDTH'])
    
    photograph_width = CONFIG['TOTAL_WIDTH'] - (2 * CONFIG['STOCK_THICKNESS'])
    CONFIG['MOTOR_POCKET_X'] = 0.4155 * photograph_width 
    CONFIG['MOTOR_CABLE_OFFSET'] = get_val(21)
    CONFIG['CABLE_HOLE_X'] = CONFIG['MOTOR_POCKET_X'] - CONFIG['MOTOR_CABLE_OFFSET']
    
    CONFIG['MOTOR_POCKET_SIZE'] = 42.0 
    CONFIG['MOTOR_MOUNT_PATTERN'] = 31.0
    CONFIG['CANVAS_SIZE_STD'] = convert_to_mm(48.0, "inches")
    CONFIG['CANVAS_SIZE_LARGE'] = convert_to_mm(65.0, "inches")
    CONFIG['PART_ANCHOR_OFFSET'] = convert_to_mm(4.0, "inches")
    
    CONFIG['ENABLE_CORNER_FILL'] = True
    CONFIG['CORNER_FILL_SIZE'] = convert_to_mm(0.125, "inches")

# ==============================================================================
# III. GEOMETRY KERNELS
# ==============================================================================

def compute_finger_layout(edge_len, target_w):
    count = round(edge_len / target_w)
    if count % 2 == 0: count += 1
    actual_w = edge_len / count
    return count, actual_w

def draw_blind_socket_geometry(x, y, w, h, depth, tool_r, glue_gap, direction):
    """
    Generates socket geometry. 
    Handles both Blind (T-Bone) and Half-Round (Corner Fill) cases based on Config.
    """
    w_socket = w + glue_gap
    shift = (w_socket - w) / 2.0 
    rect_x, rect_y, rect_w, rect_h = 0, 0, 0, 0
    tbone_centers = [] 
    corner_fills = []

    if direction == 'DOWN': 
        rect_x = x - shift; rect_y = y; rect_w = w_socket; rect_h = depth
        if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT":
            tbone_centers = [(rect_x - (tool_r*0.2), rect_y + rect_h - tool_r), (rect_x + rect_w + (tool_r*0.2), rect_y + rect_h - tool_r)]
        elif CONFIG['ENABLE_CORNER_FILL']:
            sz = CONFIG['CORNER_FILL_SIZE']
            corner_fills.append((rect_x, rect_y + rect_h - sz, sz, sz))
            corner_fills.append((rect_x + rect_w - sz, rect_y + rect_h - sz, sz, sz))

    elif direction == 'UP': 
        rect_x = x - shift; rect_y = y - depth; rect_w = w_socket; rect_h = depth
        if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT":
            tbone_centers = [(rect_x - (tool_r*0.2), rect_y + tool_r), (rect_x + rect_w + (tool_r*0.2), rect_y + tool_r)]
        elif CONFIG['ENABLE_CORNER_FILL']:
            sz = CONFIG['CORNER_FILL_SIZE']
            corner_fills.append((rect_x, rect_y, sz, sz))
            corner_fills.append((rect_x + rect_w - sz, rect_y, sz, sz))

    elif direction == 'RIGHT': 
        rect_x = x; rect_y = y - shift; rect_w = depth; rect_h = w_socket
        if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT":
            tbone_centers = [(rect_x + rect_w - tool_r, rect_y - (tool_r*0.2)), (rect_x + rect_w - tool_r, rect_y + rect_h + (tool_r*0.2))]
        elif CONFIG['ENABLE_CORNER_FILL']:
            sz = CONFIG['CORNER_FILL_SIZE']
            corner_fills.append((rect_x + rect_w - sz, rect_y, sz, sz))
            corner_fills.append((rect_x + rect_w - sz, rect_y + rect_h - sz, sz, sz))

    elif direction == 'LEFT': 
        rect_x = x - depth; rect_y = y - shift; rect_w = depth; rect_h = w_socket
        if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT":
            tbone_centers = [(rect_x + tool_r, rect_y - (tool_r*0.2)), (rect_x + tool_r, rect_y + rect_h + (tool_r*0.2))]
        elif CONFIG['ENABLE_CORNER_FILL']:
            sz = CONFIG['CORNER_FILL_SIZE']
            corner_fills.append((rect_x, rect_y, sz, sz))
            corner_fills.append((rect_x, rect_y + rect_h - sz, sz, sz))

    return {
        'pocket_rect': (rect_x, rect_y, rect_w, rect_h), 
        'tbones': [(cx, cy, tool_r) for cx, cy in tbone_centers],
        'corner_fills': corner_fills
    }

def draw_halfround_finger_geometry(x, y, w, finger_len, tool_r, glue_gap, direction):
    # Standard Half-Round Finger logic
    w_finger = w - glue_gap
    shift = (w - w_finger) / 2.0
    cmds = []
    eff_r = min(tool_r, w_finger / 2.0)
    
    if direction == 'UP':
        fx = x + shift; fy = y; tip_y = y - finger_len
        cmds += [f"L {f(fx)} {f(tip_y + eff_r)}", f"A {f(eff_r)} {f(eff_r)} 0 0 1 {f(fx + eff_r)} {f(tip_y)}"]
        if w_finger > 2 * eff_r: cmds.append(f"L {f(fx + w_finger - eff_r)} {f(tip_y)}")
        cmds += [f"A {f(eff_r)} {f(eff_r)} 0 0 1 {f(fx + w_finger)} {f(tip_y + eff_r)}", f"L {f(fx + w_finger)} {f(fy)}"]
    elif direction == 'RIGHT':
        fx = x; fy = y + shift; tip_x = x + finger_len
        cmds += [f"L {f(tip_x - eff_r)} {f(fy)}", f"A {f(eff_r)} {f(eff_r)} 0 0 1 {f(tip_x)} {f(fy + eff_r)}"]
        if w_finger > 2 * eff_r: cmds.append(f"L {f(tip_x)} {f(fy + w_finger - eff_r)}")
        cmds += [f"A {f(eff_r)} {f(eff_r)} 0 0 1 {f(tip_x - eff_r)} {f(fy + w_finger)}", f"L {f(fx)} {f(fy + w_finger)}"]
    return cmds

def draw_blind_finger_geometry(x, y, w, h, blind_skin, glue_gap, direction):
    """
    Generates BLIND finger geometry (shorter, no rounding).
    This creates the path commands for the finger PROFILE.
    It does NOT generate the inner pocket commands (handled in main loop via blue layer).
    """
    w_finger = w - glue_gap
    shift = (w - w_finger) / 2.0
    finger_len = h - blind_skin - 0.2 # Shorter than stock to fit in pocket
    cmds = []
    pocket_rect = None 
    
    # We are drawing the PROFILE (Black line) that goes AROUND the finger.
    # Logic: Walk out from base, around tip, back to base.
    
    if direction == 'UP':
        fx = x + shift; fy = y; tip_y = y - finger_len
        cmds = [f"L {f(fx)} {f(tip_y)}", f"L {f(fx + w_finger)} {f(tip_y)}", f"L {f(fx + w_finger)} {f(fy)}"]
        pocket_rect = (fx, tip_y, w_finger, finger_len) # X, Y, W, H (Top-Left based)
    elif direction == 'RIGHT':
        fx = x; fy = y + shift; tip_x = x + finger_len
        cmds = [f"L {f(tip_x)} {f(fy)}", f"L {f(tip_x)} {f(fy + w_finger)}", f"L {f(fx)} {f(fy + w_finger)}"]
        pocket_rect = (fx, fy, finger_len, w_finger)
    
    return {'cmds': cmds, 'pocket_rect': pocket_rect}

# ==============================================================================
# IV. TABBING LOGIC & FRAME GENERATION
# ==============================================================================

def get_safe_tab_positions(part_name, edge_len, is_jointed, finger_data=None):
    tabs = []
    if "RAIL" in part_name:
        if is_jointed: return [] 
        else: return [edge_len * 0.25, edge_len * 0.75]

    if part_name == "FRONT_BEZEL":
        if is_jointed:
            if finger_data:
                count, width = finger_data
                if count >= 6:
                    valid_indices = [2, count - 3] 
                else:
                    valid_indices = [0, count - 1] 
                
                for i in valid_indices:
                    center_of_finger = (i * width) + (width / 2)
                    tabs.append(center_of_finger)
            return tabs
        else: return [edge_len / 2]

    if part_name == "BACK_PANEL": return [edge_len / 2]

    if "GLAZING_STOP" in part_name:
        if edge_len > 254: return [edge_len * 0.25, edge_len * 0.75]
        else: return []

    return tabs

def generate_tab_markers(start_x, start_y, direction, tab_offsets):
    base_w = CONFIG['TAB_BASE']
    tip_w = CONFIG['TAB_TIP']
    height = CONFIG['TAB_PEAK']
    markers = []
    
    for t_off in tab_offsets:
        p1, p2, p3, p4 = (0,0), (0,0), (0,0), (0,0)
        
        if direction == 'RIGHT': 
            cx, cy = start_x + t_off, start_y
            p1 = (cx - base_w/2, cy - height)
            p2 = (cx + base_w/2, cy - height)
            p3 = (cx + tip_w/2, cy)
            p4 = (cx - tip_w/2, cy)
            
        elif direction == 'DOWN': 
            cx, cy = start_x, start_y + t_off
            p1 = (cx + height, cy - base_w/2)
            p2 = (cx + height, cy + base_w/2)
            p3 = (cx, cy + tip_w/2)
            p4 = (cx, cy - tip_w/2)

        elif direction == 'LEFT': 
            cx, cy = start_x - t_off, start_y
            p1 = (cx + base_w/2, cy + height)
            p2 = (cx - base_w/2, cy + height)
            p3 = (cx - tip_w/2, cy)
            p4 = (cx + tip_w/2, cy)

        elif direction == 'UP': 
            cx, cy = start_x, start_y - t_off
            p1 = (cx - height, cy + base_w/2)
            p2 = (cx - height, cy - base_w/2)
            p3 = (cx, cy - tip_w/2)
            p4 = (cx, cy + tip_w/2)
            
        points = f"{f(p1[0])},{f(p1[1])} {f(p2[0])},{f(p2[1])} {f(p3[0])},{f(p3[1])} {f(p4[0])},{f(p4[1])}"
        markers.append(f'<polygon points="{points}" fill="none" stroke="#FF00FF" stroke-width="0.35"/>')
        
    return markers

def generate_cutout_frame(anchor_x, anchor_y, w, h, part_type):
    gap = CONFIG['TAB_PEAK']
    clearance = CONFIG['STOCK_THICKNESS'] + gap
    
    fx, fy, fw, fh = 0, 0, 0, 0
    
    if "RAIL" in part_type:
        fx = anchor_x - clearance
        fw = w + (2 * clearance) 
        fy = anchor_y - clearance
        fh = clearance + h + gap
    else:
        fx = anchor_x - gap
        fy = anchor_y - gap
        fw = w + (2 * gap)
        fh = h + (2 * gap)
        
    return f'<rect x="{f(fx)}" y="{f(fy)}" width="{f(fw)}" height="{f(fh)}" fill="none" stroke="#00FF00" stroke-width="0.5"/>'

# ==============================================================================
# V. SVG GENERATORS
# ==============================================================================

def generate_label_text(part_name, width_mm, height_mm, cx, cy, rotation=0):
    dim_w = format_inches(width_mm)
    dim_h = format_inches(height_mm)
    transform = f'transform="rotate({rotation} {f(cx)} {f(cy)})"' if rotation != 0 else ''
    return f'''  <text x="{f(cx)}" y="{f(cy)}" text-anchor="middle" {transform}>
    <tspan x="{f(cx)}" dy="0" font-family="Josefin Sans" font-weight="600" font-size="28.22" fill="#FF00FF">{part_name}</tspan>
    <tspan x="{f(cx)}" dy="35" font-family="Josefin Sans" font-weight="400" font-size="21.17" fill="#FF00FF">{dim_w} x {dim_h}</tspan>
  </text>'''

def generate_front_bezel_svg():
    print("GENERATING: FRONT_BEZEL")
    canvas_sz = CONFIG['CANVAS_SIZE_LARGE']
    w = CONFIG['TOTAL_WIDTH']
    h = CONFIG['TOTAL_HEIGHT']
    anchor_x = (canvas_sz - w) / 2
    anchor_y = (canvas_sz - h) / 2
    
    path_cmds = [f"M {f(anchor_x)} {f(anchor_y)}", f"L {f(anchor_x + w)} {f(anchor_y)}", 
                 f"L {f(anchor_x + w)} {f(anchor_y + h)}", f"L {f(anchor_x)} {f(anchor_y + h)}", "Z"]
    
    count_h, width_h = compute_finger_layout(w, CONFIG['TARGET_FINGER_WIDTH'])
    count_v, width_v = compute_finger_layout(h, CONFIG['TARGET_FINGER_WIDTH'])
    
    pocket_elements = []
    tab_markers = []

    # Tabs
    t_pos = get_safe_tab_positions("FRONT_BEZEL", w, True, (count_h, width_h))
    tab_markers += generate_tab_markers(anchor_x, anchor_y, 'RIGHT', t_pos)
    t_pos = get_safe_tab_positions("FRONT_BEZEL", h, True, (count_v, width_v))
    tab_markers += generate_tab_markers(anchor_x + w, anchor_y, 'DOWN', t_pos)
    t_pos = get_safe_tab_positions("FRONT_BEZEL", w, True, (count_h, width_h))
    tab_markers += generate_tab_markers(anchor_x + w, anchor_y + h, 'LEFT', t_pos)
    t_pos = get_safe_tab_positions("FRONT_BEZEL", h, True, (count_v, width_v))
    tab_markers += generate_tab_markers(anchor_x, anchor_y + h, 'UP', t_pos)

    # Sockets (Blind vs Half-Round handled in draw_blind_socket_geometry via CONFIG)
    x, y = anchor_x, anchor_y + h
    for i in range(count_h):
        if i % 2 == 1:
            res = draw_blind_socket_geometry(x + (i*width_h), y, width_h, CONFIG['STOCK_THICKNESS'], CONFIG['STOCK_THICKNESS'], CONFIG['TOOL_R'], CONFIG['FIT_TOLERANCE'], 'UP')
            rx, ry, rw, rh = res['pocket_rect']
            pocket_elements.append(f'<rect x="{f(rx)}" y="{f(ry)}" width="{f(rw)}" height="{f(rh)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
            for cx, cy, r in res['tbones']: pocket_elements.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
            for fx, fy, fw, fh in res.get('corner_fills', []): pocket_elements.append(f'<rect x="{f(fx)}" y="{f(fy)}" width="{f(fw)}" height="{f(fh)}" fill="#000000" stroke="none"/>')

    x, y = anchor_x + w, anchor_y
    for i in range(count_v):
        if i % 2 == 1:
            res = draw_blind_socket_geometry(x, y + (i*width_v), width_v, CONFIG['STOCK_THICKNESS'], CONFIG['STOCK_THICKNESS'], CONFIG['TOOL_R'], CONFIG['FIT_TOLERANCE'], 'LEFT')
            rx, ry, rw, rh = res['pocket_rect']
            pocket_elements.append(f'<rect x="{f(rx)}" y="{f(ry)}" width="{f(rw)}" height="{f(rh)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
            for cx, cy, r in res['tbones']: pocket_elements.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
            for fx, fy, fw, fh in res.get('corner_fills', []): pocket_elements.append(f'<rect x="{f(fx)}" y="{f(fy)}" width="{f(fw)}" height="{f(fh)}" fill="#000000" stroke="none"/>')

    x, y = anchor_x, anchor_y
    for i in range(count_h):
        if i % 2 == 1:
            res = draw_blind_socket_geometry(x + (i*width_h), y, width_h, CONFIG['STOCK_THICKNESS'], CONFIG['STOCK_THICKNESS'], CONFIG['TOOL_R'], CONFIG['FIT_TOLERANCE'], 'DOWN')
            rx, ry, rw, rh = res['pocket_rect']
            pocket_elements.append(f'<rect x="{f(rx)}" y="{f(ry)}" width="{f(rw)}" height="{f(rh)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
            for cx, cy, r in res['tbones']: pocket_elements.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
            for fx, fy, fw, fh in res.get('corner_fills', []): pocket_elements.append(f'<rect x="{f(fx)}" y="{f(fy)}" width="{f(fw)}" height="{f(fh)}" fill="#000000" stroke="none"/>')

    x, y = anchor_x, anchor_y
    for i in range(count_v):
        if i % 2 == 1:
            res = draw_blind_socket_geometry(x, y + (i*width_v), width_v, CONFIG['STOCK_THICKNESS'], CONFIG['STOCK_THICKNESS'], CONFIG['TOOL_R'], CONFIG['FIT_TOLERANCE'], 'RIGHT')
            rx, ry, rw, rh = res['pocket_rect']
            pocket_elements.append(f'<rect x="{f(rx)}" y="{f(ry)}" width="{f(rw)}" height="{f(rh)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
            for cx, cy, r in res['tbones']: pocket_elements.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
            for fx, fy, fw, fh in res.get('corner_fills', []): pocket_elements.append(f'<rect x="{f(fx)}" y="{f(fy)}" width="{f(fw)}" height="{f(fh)}" fill="#000000" stroke="none"/>')
    
    win_x = anchor_x + CONFIG['BEZEL_WIDTH']; win_y = anchor_y + CONFIG['BEZEL_WIDTH']
    win_w = CONFIG['WINDOW_CUTOUT_WIDTH']; win_h = CONFIG['WINDOW_CUTOUT_HEIGHT']
    
    # FIXED: PERFECTLY SQUARE WINDOW (No radius)
    window_path = (f"M {f(win_x)} {f(win_y)} "
                   f"L {f(win_x + win_w)} {f(win_y)} "
                   f"L {f(win_x + win_w)} {f(win_y + win_h)} "
                   f"L {f(win_x)} {f(win_y + win_h)} "
                   "Z")
    
    label_text = generate_label_text("FRONT_BEZEL", w, h, anchor_x + w/2, anchor_y + h/2)
    pocket_svg = "\n".join(pocket_elements)
    tab_svg = "\n".join(tab_markers)
    frame_svg = generate_cutout_frame(anchor_x, anchor_y, w, h, "FRONT_BEZEL")
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{f(canvas_sz)}mm" height="{f(canvas_sz)}mm" viewBox="0 0 {f(canvas_sz)} {f(canvas_sz)}">
  <title>FRONT_BEZEL</title>
  {label_text}
  {frame_svg}
  <path d="{' '.join(path_cmds)}" fill="none" stroke="#00c9ff" stroke-width="0.5"/>
  <path d="{window_path}" fill="none" stroke="#FF0000" stroke-width="0.5"/>
  {pocket_svg}
  {tab_svg}
</svg>'''

def generate_rail_svg(rail_name, length_spec, is_horizontal, has_motor_pocket=False, rotation_deg=0, label_offset=(0,0), label_rotation_deg=None, forced_finger_layout=None):
    print(f"GENERATING: {rail_name}")
    canvas_sz = CONFIG['CANVAS_SIZE_STD']
    
    # DETERMINE RAIL WIDTH BASED ON METHOD
    # Blind: Width = Total - 2*Skin
    # Half-Round: Width = Total (Flush)
    rail_w = 0; rail_h = CONFIG['BOX_DEPTH']; is_part_a_socket = False 
    
    if is_horizontal: 
        if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT": 
            rail_w = CONFIG['TOTAL_WIDTH'] - (2 * CONFIG['BLIND_SKIN'])
        else: 
            rail_w = CONFIG['TOTAL_WIDTH'] 
    else: 
        is_part_a_socket = True; rail_w = CONFIG['TOTAL_HEIGHT'] 
    
    anchor_x = (canvas_sz - rail_w) / 2; anchor_y = (canvas_sz - rail_h) / 2
    path_cmds = []; pocket_elements = []; tab_markers = []
    
    count_end, width_end = compute_finger_layout(rail_h, CONFIG['TARGET_FINGER_WIDTH']) 
    count_face, width_face = forced_finger_layout if forced_finger_layout else compute_finger_layout(rail_w, CONFIG['TARGET_FINGER_WIDTH'])
    
    path_cmds.append(f"M {f(anchor_x)} {f(anchor_y)}") 
    
    # 1. TOP EDGE (Face Joint)
    center_rail_x = anchor_x + (rail_w / 2.0)
    total_pattern_w = count_face * width_face
    pattern_start_x = center_rail_x - (total_pattern_w / 2.0)
    x_curr = pattern_start_x
    y_curr = anchor_y
    if pattern_start_x > anchor_x: path_cmds.append(f"L {f(pattern_start_x)} {f(y_curr)}")
        
    for i in range(count_face):
        x_abs = pattern_start_x + (i * width_face)
        if i % 2 == 1: 
            # FINGER
            if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT":
                # BLIND: Finger is shorter and has rectangular profile. 
                res = draw_blind_finger_geometry(x_abs, y_curr, width_face, CONFIG['STOCK_THICKNESS'], CONFIG['BLIND_SKIN'], CONFIG['FIT_TOLERANCE'], 'UP')
                path_cmds += res['cmds']
                bx, by, bw, bh = res['pocket_rect']
                pocket_elements.append(f'<rect x="{f(bx)}" y="{f(by)}" width="{f(bw)}" height="{f(bh)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
            else:
                # HALF-ROUND: Standard logic
                path_cmds += draw_halfround_finger_geometry(x_abs, y_curr, width_face, CONFIG['STOCK_THICKNESS'], CONFIG['TOOL_R'], CONFIG['FIT_TOLERANCE'], 'UP')
        else:
            # GAP
            x_next_abs = pattern_start_x + ((i + 1) * width_face)
            path_cmds.append(f"L {f(x_next_abs)} {f(y_curr)}")
    
    path_cmds.append(f"L {f(anchor_x + rail_w)} {f(anchor_y)}")

    # 2. RIGHT END (Jointed)
    x = anchor_x + rail_w; y = anchor_y
    if is_part_a_socket:
        path_cmds.append(f"L {f(x)} {f(y + rail_h)}") 
        for i in range(count_end):
            if i % 2 == 1:
                res = draw_blind_socket_geometry(x, y + (i*width_end), width_end, CONFIG['STOCK_THICKNESS'], CONFIG['STOCK_THICKNESS'], CONFIG['TOOL_R'], CONFIG['FIT_TOLERANCE'], 'LEFT')
                rx, ry, rw, rh = res['pocket_rect']
                pocket_elements.append(f'<rect x="{f(rx)}" y="{f(ry)}" width="{f(rw)}" height="{f(rh)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
                for cx, cy, r in res['tbones']: pocket_elements.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
                for fx, fy, fw, fh in res.get('corner_fills', []):
                     pocket_elements.append(f'<rect x="{f(fx)}" y="{f(fy)}" width="{f(fw)}" height="{f(fh)}" fill="#000000" stroke="none"/>')
    else:
        for i in range(count_end):
            is_finger = (i % 2 != 0) 
            if is_finger: 
                if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT":
                    res = draw_blind_finger_geometry(x, y + (i*width_end), width_end, CONFIG['STOCK_THICKNESS'], CONFIG['BLIND_SKIN'], CONFIG['FIT_TOLERANCE'], 'RIGHT')
                    path_cmds += res['cmds']
                    bx, by, bw, bh = res['pocket_rect']
                    pocket_elements.append(f'<rect x="{f(bx)}" y="{f(by)}" width="{f(bw)}" height="{f(bh)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
                else:
                    path_cmds += draw_halfround_finger_geometry(x, y + (i*width_end), width_end, CONFIG['STOCK_THICKNESS'], CONFIG['TOOL_R'], CONFIG['FIT_TOLERANCE'], 'RIGHT')
            else: path_cmds.append(f"L {f(x)} {f(y + (i+1)*width_end)}")

    # 3. BOTTOM EDGE (Non-Jointed)
    path_cmds.append(f"L {f(anchor_x)} {f(anchor_y + rail_h)}") 
    t_pos = get_safe_tab_positions(rail_name, rail_w, False, None)
    tab_markers += generate_tab_markers(anchor_x + rail_w, anchor_y + rail_h, 'LEFT', t_pos)

    # 4. LEFT END (Jointed)
    x = anchor_x; y = anchor_y + rail_h 
    if is_part_a_socket:
        path_cmds.append(f"L {f(x)} {f(anchor_y)}")
        for i in range(count_end):
            if i % 2 == 1:
                res = draw_blind_socket_geometry(x, anchor_y + (i*width_end), width_end, CONFIG['STOCK_THICKNESS'], CONFIG['STOCK_THICKNESS'], CONFIG['TOOL_R'], CONFIG['FIT_TOLERANCE'], 'RIGHT')
                rx, ry, rw, rh = res['pocket_rect']
                pocket_elements.append(f'<rect x="{f(rx)}" y="{f(ry)}" width="{f(rw)}" height="{f(rh)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
                for cx, cy, r in res['tbones']: pocket_elements.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
                for fx, fy, fw, fh in res.get('corner_fills', []): pocket_elements.append(f'<rect x="{f(fx)}" y="{f(fy)}" width="{f(fw)}" height="{f(fh)}" fill="#000000" stroke="none"/>')
    else:
        for i in range(count_end - 1, -1, -1):
            is_finger = (i % 2 != 0)
            if is_finger:
                if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT":
                    w_finger = width_end - CONFIG['FIT_TOLERANCE']
                    shift = (width_end - w_finger) / 2.0
                    y_finger_bot = (anchor_y + (i*width_end) + width_end) - shift
                    y_finger_top = (anchor_y + (i*width_end)) + shift
                    finger_len = CONFIG['STOCK_THICKNESS'] - CONFIG['BLIND_SKIN'] - 0.2
                    tip_x = x - finger_len
                    path_cmds.append(f"L {f(x)} {f(y_finger_bot)}")
                    path_cmds.append(f"L {f(tip_x)} {f(y_finger_bot)}")
                    path_cmds.append(f"L {f(tip_x)} {f(y_finger_top)}")
                    path_cmds.append(f"L {f(x)} {f(y_finger_top)}")
                    path_cmds.append(f"L {f(x)} {f(anchor_y + (i*width_end))}")
                    pocket_elements.append(f'<rect x="{f(tip_x)}" y="{f(y_finger_top)}" width="{f(finger_len)}" height="{f(w_finger)}" fill="none" stroke="#0000FF" stroke-width="0.5"/>')
                else:
                    y_top = anchor_y + (i * width_end)
                    w_finger = width_end - CONFIG['FIT_TOLERANCE']
                    y_finger_bot = y_top + width_end - (width_end - w_finger)/2.0
                    y_finger_top = y_top + (width_end - w_finger)/2.0
                    eff_r = min(CONFIG['TOOL_R'], w_finger/2.0)
                    finger_len = CONFIG['STOCK_THICKNESS']
                    tip_x = x - finger_len
                    path_cmds.append(f"L {f(x)} {f(y_finger_bot)}")
                    path_cmds.append(f"L {f(tip_x + eff_r)} {f(y_finger_bot)}")
                    path_cmds.append(f"A {f(eff_r)} {f(eff_r)} 0 0 1 {f(tip_x)} {f(y_finger_bot - eff_r)}")
                    if w_finger > 2*eff_r: path_cmds.append(f"L {f(tip_x)} {f(y_finger_top + eff_r)}")
                    path_cmds.append(f"A {f(eff_r)} {f(eff_r)} 0 0 1 {f(tip_x + eff_r)} {f(y_finger_top)}")
                    path_cmds.append(f"L {f(x)} {f(y_finger_top)}")
                    path_cmds.append(f"L {f(x)} {f(anchor_y + (i*width_end))}")
            else:
                path_cmds.append(f"L {f(x)} {f(anchor_y + (i*width_end))}")

    path_cmds.append("Z")
    
    motor_elements = ""
    if has_motor_pocket and CONFIG['MOTOR_POCKET_ENABLED']:
        rail_start_offset = (CONFIG['TOTAL_WIDTH'] - rail_w) / 2.0
        motor_target_x = CONFIG['MOTOR_POCKET_X']
        px = anchor_x + (motor_target_x - rail_start_offset); py = anchor_y + (rail_h / 2); sz = CONFIG['MOTOR_POCKET_SIZE']
        pat = CONFIG['MOTOR_MOUNT_PATTERN']
        motor_elements = f'''
  <rect x="{f(px - sz/2)}" y="{f(py - sz/2)}" width="{f(sz)}" height="{f(sz)}" fill="#FFFFFF" stroke="#0000FF" stroke-width="0.5"/>
  <circle cx="{f(px)}" cy="{f(py)}" r="{f(6.35)}" fill="#FFFFFF" stroke="#FF0000" stroke-width="0.5"/>
  <circle cx="{f(px - pat/2)}" cy="{f(py - pat/2)}" r="1.7" fill="#FFFFFF" stroke="#FF0000" stroke-width="0.5"/>
  <circle cx="{f(px + pat/2)}" cy="{f(py - pat/2)}" r="1.7" fill="#FFFFFF" stroke="#FF0000" stroke-width="0.5"/>
  <circle cx="{f(px - pat/2)}" cy="{f(py + pat/2)}" r="1.7" fill="#FFFFFF" stroke="#FF0000" stroke-width="0.5"/>
  <circle cx="{f(px + pat/2)}" cy="{f(py + pat/2)}" r="1.7" fill="#FFFFFF" stroke="#FF0000" stroke-width="0.5"/>
  <circle cx="{f(anchor_x + CONFIG['CABLE_HOLE_X'])}" cy="{f(py)}" r="{f(6.35)}" fill="#FFFFFF" stroke="#FF0000" stroke-width="0.5"/>'''

    canvas_cx = canvas_sz / 2; canvas_cy = canvas_sz / 2
    label_cx = canvas_cx + label_offset[0]; label_cy = canvas_cy + label_offset[1]
    lbl_rot = label_rotation_deg if label_rotation_deg is not None else rotation_deg
    transform_attr = f'transform="rotate({rotation_deg} {f(canvas_cx)} {f(canvas_cy)})"' if rotation_deg != 0 else ''
    pocket_svg = "\n".join(pocket_elements)
    tab_svg = "\n".join(tab_markers)
    frame_svg = generate_cutout_frame(anchor_x, anchor_y, rail_w, rail_h, rail_name)
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{f(canvas_sz)}mm" height="{f(canvas_sz)}mm" viewBox="0 0 {f(canvas_sz)} {f(canvas_sz)}">
  <title>{rail_name}</title>
  {generate_label_text(rail_name, rail_w, rail_h, label_cx, label_cy, lbl_rot)}
  <g {transform_attr}>
    {frame_svg}
    <path d="{' '.join(path_cmds)}" fill="#FF97F5" stroke="#000000" stroke-width="0.3528"/>
    {pocket_svg}
    {motor_elements}
    {tab_svg}
  </g>
</svg>'''

def generate_back_panel_svg():
    print("GENERATING: BACK_PANEL")
    canvas_sz = CONFIG['CANVAS_SIZE_STD']
    w = CONFIG['TOTAL_WIDTH']; h = CONFIG['TOTAL_HEIGHT']
    anchor = CONFIG['PART_ANCHOR_OFFSET']
    outer_path = f"M {f(anchor)} {f(anchor)} L {f(anchor+w)} {f(anchor)} L {f(anchor+w)} {f(anchor+h)} L {f(anchor)} {f(anchor+h)} Z"
    rw = CONFIG['BACK_PANEL_RABBET_WIDTH']
    rabbet_path = f"M {f(anchor+rw)} {f(anchor+rw)} L {f(anchor+w-rw)} {f(anchor+rw)} L {f(anchor+w-rw)} {f(anchor+h-rw)} L {f(anchor+rw)} {f(anchor+h-rw)} Z"
    
    hole_offset = rw / 2; hole_r = CONFIG['SCREW_PILOT_DIA'] / 2
    holes = [
        (anchor + hole_offset, anchor + hole_offset), (anchor + w - hole_offset, anchor + hole_offset),
        (anchor + hole_offset, anchor + h - hole_offset), (anchor + w - hole_offset, anchor + h - hole_offset),
        (anchor + w/3, anchor + hole_offset), (anchor + 2*w/3, anchor + hole_offset),
        (anchor + w/3, anchor + h - hole_offset), (anchor + 2*w/3, anchor + h - hole_offset),
        (anchor + hole_offset, anchor + h/3), (anchor + hole_offset, anchor + 2*h/3),
        (anchor + w - hole_offset, anchor + h/3), (anchor + w - hole_offset, anchor + 2*h/3)
    ]
    hole_elements = "\n".join([f'  <circle cx="{f(hx)}" cy="{f(hy)}" r="{f(hole_r)}" fill="#FFFFFF" stroke="#FF0000" stroke-width="0.5"/>' for hx, hy in holes])
    
    tab_markers = []
    t_pos = get_safe_tab_positions("BACK_PANEL", w, False)
    tab_markers += generate_tab_markers(anchor, anchor, 'RIGHT', t_pos)
    t_pos = get_safe_tab_positions("BACK_PANEL", h, False)
    tab_markers += generate_tab_markers(anchor + w, anchor, 'DOWN', t_pos)
    t_pos = get_safe_tab_positions("BACK_PANEL", w, False)
    tab_markers += generate_tab_markers(anchor + w, anchor + h, 'LEFT', t_pos)
    t_pos = get_safe_tab_positions("BACK_PANEL", h, False)
    tab_markers += generate_tab_markers(anchor, anchor + h, 'UP', t_pos)
    
    label_text = generate_label_text("BACK_PANEL", w, h, anchor + w/2, anchor + h/2)
    tab_svg = "\n".join(tab_markers)
    frame_svg = generate_cutout_frame(anchor, anchor, w, h, "BACK_PANEL")
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{f(canvas_sz)}mm" height="{f(canvas_sz)}mm" viewBox="0 0 {f(canvas_sz)} {f(canvas_sz)}">
  <title>BACK_PANEL</title>
  {label_text}
  {frame_svg}
  <path d="{outer_path}" fill="none" stroke="#000000" stroke-width="0.5"/>
  <path d="{rabbet_path}" fill="none" stroke="#0000FF" stroke-width="0.5"/>
  {hole_elements}
  {tab_svg}
</svg>'''

def generate_glazing_stops_svg():
    print("GENERATING: GLAZING_STOPS")
    canvas_sz = CONFIG['CANVAS_SIZE_STD']
    len_h = CONFIG['TOTAL_WIDTH'] + convert_to_mm(5.0, "inches")
    len_v = CONFIG['TOTAL_HEIGHT'] + convert_to_mm(5.0, "inches")
    w = CONFIG['STOCK_THICKNESS']
    gap = convert_to_mm(2.0, "inches")
    group_h = (4 * w) + (3 * gap)
    center_x = convert_to_mm(24.0, "inches")
    center_y = convert_to_mm(22.5681, "inches")
    start_y = center_y - (group_h / 2.0)
    elements = []
    tab_markers = []
    
    sy = start_y
    for length in [len_h, len_h, len_v, len_v]:
        sx = center_x - (length / 2.0)
        elements.append(generate_cutout_frame(sx, sy, length, w, "GLAZING_STOP"))
        elements.append(f'<rect x="{f(sx)}" y="{f(sy)}" width="{f(length)}" height="{f(w)}" fill="#FF97F5" stroke="#000000" stroke-width="0.3528"/>')
        t_pos = get_safe_tab_positions("GLAZING_STOP", length, False)
        tab_markers += generate_tab_markers(sx, sy, 'RIGHT', t_pos)
        tab_markers += generate_tab_markers(sx + length, sy + w, 'LEFT', t_pos)
        sy += w + gap
    
    label_text = generate_label_text("GLAZING_STOPS", len_h, group_h, center_x, start_y - 100)
    content = "\n".join(elements)
    tab_svg = "\n".join(tab_markers)
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{f(canvas_sz)}mm" height="{f(canvas_sz)}mm" viewBox="0 0 {f(canvas_sz)} {f(canvas_sz)}">
  <title>GLAZING_STOPS</title>
  {label_text}
  {content}
  {tab_svg}
</svg>'''

def generate_cam_instructions(output_dir, version_str):
    filename = f"x CAM_Instructions.txt"
    filepath = output_dir / filename
    
    with open(filepath, "w") as cam_file:
        cam_file.write(f"Project: McTell Ghostphone Shadowbox\n")
        cam_file.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        cam_file.write(f"Active Joinery Method: {CONFIG['ACTIVE_JOINERY_METHOD']}\n\n")

        cam_file.write("CUT LIST (Name | Qty | Dimensions):\n")
        cam_file.write(f"1. FRONT_BEZEL | 1 | {format_inches(CONFIG['TOTAL_WIDTH'])} x {format_inches(CONFIG['TOTAL_HEIGHT'])}\n")
        rail_len_tb = CONFIG['TOTAL_WIDTH'] - 2*CONFIG['BLIND_SKIN'] if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT" else CONFIG['TOTAL_WIDTH']
        cam_file.write(f"2. TOP_RAIL | 1 | {format_inches(rail_len_tb)} x {format_inches(CONFIG['BOX_DEPTH'])}\n")
        cam_file.write(f"3. BOTTOM_RAIL | 1 | {format_inches(rail_len_tb)} x {format_inches(CONFIG['BOX_DEPTH'])}\n")
        cam_file.write(f"4. LEFT_RAIL | 1 | {format_inches(CONFIG['TOTAL_HEIGHT'])} x {format_inches(CONFIG['BOX_DEPTH'])}\n")
        cam_file.write(f"5. RIGHT_RAIL | 1 | {format_inches(CONFIG['TOTAL_HEIGHT'])} x {format_inches(CONFIG['BOX_DEPTH'])}\n")
        cam_file.write(f"6. BACK_PANEL | 1 | {format_inches(CONFIG['TOTAL_WIDTH'])} x {format_inches(CONFIG['TOTAL_HEIGHT'])}\n")
        cam_file.write(f"7. GLAZING_STOPS | 4 | Mixed Lengths (+5.0\" oversize)\n\n")

        cam_file.write("COLOR MAP & MACHINING SPECS:\n")
        cam_file.write("BLACK (Outer Profile):\n")
        cam_file.write("  Operation : Contour / Outside Cut\n")
        cam_file.write("  Tool : #201 0.25\" End Mill\n")
        cam_file.write(f"  Depth : {f(CONFIG['STOCK_THICKNESS'] + 0.25)}mm (Cut Through into spoilboard)\n")
        cam_file.write("  **IMPORTANT: Use MAGENTA markers to place Tabs in CAM.**\n")
        cam_file.write("  **TAB SETTINGS: Width=0.5\", Height=0.125\" (Milled down to 0.125\" remaining on table).**\n")
        
        cam_file.write("RED (Inner Cutouts & Holes):\n")
        cam_file.write("  Operation : Pocket (for Windows) or Helical Drill (for Holes)\n")
        cam_file.write("  Tool : #201 for large windows; #102 0.125\" for holes < 6.35mm\n")
        cam_file.write(f"  Depth : {f(CONFIG['STOCK_THICKNESS'] + 0.25)}mm (Cut Through)\n")
        
        cam_file.write("BLUE (Pockets & Rabbets):\n")
        cam_file.write("  Operation : Pocket / Area Clearance\n")
        cam_file.write("  Tool : #201 0.25\" End Mill\n")
        cam_file.write("  Specific Depths:\n")
        cam_file.write(f"    - Back Panel Rabbet: {f(CONFIG['BACK_PANEL_RABBET_DEPTH'])}mm\n")
        if CONFIG['MOTOR_POCKET_ENABLED']: cam_file.write(f"    - Motor Pocket: {f(CONFIG['NEMA_POCKET_DEPTH'])}mm\n")
        if CONFIG['ACTIVE_JOINERY_METHOD'] == "BLIND_BOX_JOINT": cam_file.write(f"    - Blind Joints: {f(CONFIG['STOCK_THICKNESS'] - CONFIG['BLIND_SKIN'])}mm\n")
        if CONFIG['ENABLE_CORNER_FILL']: cam_file.write(f"    - Corner Reliefs: {f(CONFIG['STOCK_THICKNESS'] + 0.25)}mm (Through)\n")
        
        cam_file.write("GREEN (Onion-Skin Cutout Frame):\n")
        cam_file.write("  Operation : Contour / Outside Cut\n")
        cam_file.write("  Tool : #201 0.25\" End Mill\n")
        cam_file.write(f"  Depth : {f(CONFIG['STOCK_THICKNESS'] + 0.25)}mm (Cut Through)\n")

        cam_file.write("\nMACHINING SEQUENCE:\n")
        cam_file.write("Step 1: (Tool #102) Helical mill all 5mm pilot holes (Back Panel) and 3.4mm mount holes (Bottom Rail).\n")
        cam_file.write(f"Step 2: (Tool Change -> #201)\n")
        cam_file.write("Step 3: Pocket all BLUE regions (Rabbets, Motor Recess, Joinery Pockets).\n")
        cam_file.write("Step 4: Profile/Cut-Through all RED regions (Windows, Shaft Holes).\n")
        cam_file.write("Step 5: Profile/Cut-Through all BLACK regions (Part Perimeters). ENSURE TABS ARE SET (H=0.125\").\n")
        cam_file.write("Step 6: Profile/Cut-Through all GREEN regions (Onion-Skin Cutout Frame). This releases the block.\n")

def main():
    get_user_inputs()
    base_path = Path("/Users/joelsilverman/Desktop/2026 Files/26-005 Gemini-created CNC Box Creator/Gemini McTell CNC Plans")
    base_path.mkdir(parents=True, exist_ok=True)
    existing_versions = []
    for child in base_path.iterdir():
        if child.is_dir() and "McTell SVGs v" in child.name:
            match = re.search(r'v(\d+)', child.name)
            if match: existing_versions.append(int(match.group(1)))
    next_ver = max(existing_versions) + 1 if existing_versions else 1
    if next_ver < 38: next_ver = 38
    
    output_dir = base_path / f"McTell SVGs v{next_ver}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nCreated Output Directory: {output_dir}")
    
    master_finger_layout_h = compute_finger_layout(CONFIG['TOTAL_WIDTH'], CONFIG['TARGET_FINGER_WIDTH']) 
    master_finger_layout_v = compute_finger_layout(CONFIG['TOTAL_HEIGHT'], CONFIG['TARGET_FINGER_WIDTH']) 
    
    OFFSET_5_INCH = convert_to_mm(5.0, "inches")
    
    files = {
        f"FRONT_BEZEL_v{next_ver}.svg": generate_front_bezel_svg(),
        f"TOP_RAIL_v{next_ver}.svg": generate_rail_svg("TOP_RAIL", CONFIG['TOTAL_WIDTH'], is_horizontal=True, rotation_deg=180, label_offset=(0, -OFFSET_5_INCH), label_rotation_deg=0, forced_finger_layout=master_finger_layout_h),
        f"BOTTOM_RAIL_v{next_ver}.svg": generate_rail_svg("BOTTOM_RAIL", CONFIG['TOTAL_WIDTH'], is_horizontal=True, has_motor_pocket=True, rotation_deg=0, label_offset=(0, OFFSET_5_INCH), forced_finger_layout=master_finger_layout_h),
        f"LEFT_RAIL_v{next_ver}.svg": generate_rail_svg("LEFT_RAIL", CONFIG['TOTAL_HEIGHT'], is_horizontal=False, rotation_deg=90, label_offset=(-OFFSET_5_INCH, 0), forced_finger_layout=master_finger_layout_v),
        f"RIGHT_RAIL_v{next_ver}.svg": generate_rail_svg("RIGHT_RAIL", CONFIG['TOTAL_HEIGHT'], is_horizontal=False, rotation_deg=-90, label_offset=(OFFSET_5_INCH, 0), forced_finger_layout=master_finger_layout_v),
        f"BACK_PANEL_v{next_ver}.svg": generate_back_panel_svg(),
        f"GLAZING_STOPS_v{next_ver}.svg": generate_glazing_stops_svg(),
    }
    
    for filename, content in files.items():
        with open(output_dir / filename, 'w') as fh:
            fh.write(content)
        print(f"  OK {filename}")
        
    generate_cam_instructions(output_dir, next_ver)

    print(f"\nSUCCESS. Files saved to: {output_dir}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
CNC GENERATOR - CARBIDE-OPTIMIZED v45
======================================
Fork of v43, adding combined viz and flush fingers.

Key Changes from v42:
- No text labels
- No glazing strips
- Stroke-only SVGs (no fill)
- Individual SVGs per part with 2" margins
- Units in inches for Illustrator/Carbide scale parity
- Color-coded strokes by operation type
- Separate files per operation (PERIMETER, HOLES, POCKETS, RABBETS)
- Open geometry for finger sockets (no T-bones)
- TOP_RAIL and BACK_PANEL use simple perimeters (no fingers)
"""

import os
import sys
import math
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageTk
import json

# ==============================================================================
# CONSTANTS - Carbide Create Color Coding
# ==============================================================================
COLOR_PERIMETER = "#ff0000"  # Red - outer cuts and finger joints
COLOR_HOLES = "#0000ff"      # Blue - circular holes
COLOR_POCKETS = "#8fea00"    # Green - shallow pockets (motors)
COLOR_RABBETS = "#e09500"    # Orange - rabbet channels

STROKE_WIDTH = "0.01"  # inches - thin stroke for CNC precision
MARGIN_INCHES = 2.0    # 2" margin on all sides

# ==============================================================================
# GLOBAL CONFIG
# ==============================================================================
CONFIG = {}

def f(val):
    """Format float to 4 decimal places"""
    return f"{val:.4f}"

def convert_to_inches(value_mm):
    """Convert mm to inches"""
    return value_mm / 25.4

def convert_to_mm(value, unit):
    if unit in ["inches", "in", '"']:
        return value * 25.4
    elif unit == "mm":
        return value
    else:
        return float(value)

def convert_string_to_mm(value_str, default_unit="inches"):
    """Parse string like "5'", "60 in", "1500 mm" and return mm float."""
    if not isinstance(value_str, str):
        val = float(value_str)
        if default_unit in ["inches", "in", '"']:
            return val * 25.4
        return val

    val_str = value_str.lower().strip()
    if not val_str:
        return 0.0

    if "'" in val_str:
        try:
            parts = val_str.split("'")
            feet = float(parts[0])
            inches = 0.0
            if len(parts) > 1 and parts[1].strip():
                inches_part = parts[1].replace('"', '').strip()
                if inches_part:
                    inches = float(inches_part)
            return (feet * 12 + inches) * 25.4
        except ValueError:
            pass

    if "mm" in val_str:
        try:
            return float(re.sub(r"[^\d.]", "", val_str))
        except ValueError:
            pass

    if "cm" in val_str:
        try:
            return float(re.sub(r"[^\d.]", "", val_str)) * 10
        except ValueError:
            pass

    try:
        clean_val = re.sub(r"[^\d.]", "", val_str)
        val = float(clean_val)
        if default_unit in ["inches", "in", '"']:
            return val * 25.4
        return val
    except ValueError:
        return 0.0

def compute_finger_layout(edge_len, target_w):
    """Compute finger count and width for edge."""
    count = round(edge_len / target_w)
    if count % 2 == 0:
        count += 1
    actual_w = edge_len / count
    return count, actual_w

# ==============================================================================
# SVG HELPER FUNCTIONS
# ==============================================================================

def create_svg_header(width_in, height_in, title):
    """Create SVG header with inches units for Carbide Create compatibility."""
    # Clean Layer Name: Remove underscores, replace with spaces. 
    # Title passed often has underscores (e.g. TOP_RAIL_PERIMETER)
    layer_name = title.replace("_", " ")
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" 
     width="{f(width_in)}in" 
     height="{f(height_in)}in" 
     viewBox="0 0 {f(width_in)} {f(height_in)}">
  <title>{title}</title>
  <g id="{layer_name}">'''

def create_svg_footer():
    return "  </g>\n</svg>"

def create_path(d, color):
    """Create stroke-only path element."""
    return f'  <path d="{d}" fill="none" stroke="{color}" stroke-width="{STROKE_WIDTH}"/>'

def create_circle(cx, cy, r, color):
    """Create stroke-only circle element."""
    return f'  <circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="none" stroke="{color}" stroke-width="{STROKE_WIDTH}"/>'

def create_rect(x, y, w, h, color):
    """Create stroke-only rectangle element."""
    return f'  <rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" fill="none" stroke="{color}" stroke-width="{STROKE_WIDTH}"/>'

# ==============================================================================
# GEOMETRY GENERATION - Carbide Optimized
# ==============================================================================

def compute_finger_layout(edge_len_mm, target_width_mm):
    """Calculate finger count and width for symmetrical odd layout."""
    # Ensure odd number of fingers for symmetry (F-S-F...F or S-F-S...S)
    count = round(edge_len_mm / target_width_mm)
    if count % 2 == 0:
        count += 1
    actual_width_mm = edge_len_mm / count
    return count, actual_width_mm

def generate_perimeter_with_fingers(part_name, width_in, height_in, finger_config):
    """
    Generate perimeter path with HALF-ROUND FINGER JOINTS.
    
    STRATEGY: "Corner Fill" / Manual Roundover
    - FINGERS: Cut SQUARE and EXTENDED (Protrusion) to allow manual roundover.
    - SOCKETS: Cut SQUARE (CNC naturally rounds corners).
    
    SMART CORNERS:
    - If a corner is a SOCKET, the path must NOT go to the outer corner (ax, ay).
    - It must stay at the INNER corner (e.g., ax + stock_thk, ay).
    - This prevents visually intersecting lines ("Overruns") and redundant cuts.
    """
    
    # 1. HELPER CONSTANTS
    tool_d_in = CONFIG.get('TOOL_DIAMETER', 0.25)
    stock_thk = convert_to_inches(CONFIG['STOCK_THICKNESS'])
    
    # Protrusion set to 0.0 for flush fingers (Manual Roundover does not add length)
    # Fingers will be exactly stock_thk - fit_tol
    protrusion = 0.0
    
    # Canvas definitions required for return
    canvas_w = width_in + 4.0
    canvas_h = height_in + 4.0
    
    # Tolerance: Shrink MALE Fingers
    # Tolerance: Shrink MALE Fingers
    fit_tol = convert_to_inches(CONFIG.get('FIT_TOLERANCE', 0.254)) # Defaults to 0.010" (0.254mm) 
    
    # 2. PATH GENERATION STATE
    path_cmds = []
    
    # Check Corner Configurations (Is Corner a Socket?)
    # LEFT RAIL (Vert): Left=Sockets, Right=Sockets. Top=None, Bot=None. -> All Corners Sockets.
    # TOP RAIL (Horiz): Left=Fingers, Right=Fingers. -> Corners Fingers.
    
    left_type = finger_config.get('left')
    right_type = finger_config.get('right')
    top_type = finger_config.get('top')
    bottom_type = finger_config.get('bottom')

    # Helper to determine if a corner should be "Inner" (Socket)
    # Parity: Index 0 is Start. Index Last is End.
    # For Vertical Edges (Left/Right): Start=Top, End=Bot.
    # For Horizontal Edges (Top/Bot): Start=Left, End=Right.
    
    # Top-Left Corner: Start of Left Edge? End of Top Edge?
    # Actually, simpler: If 'left' starts with socket -> Inner X. If 'top' starts with socket -> Inner Y.
    # But parity is tricky.
    
    # Let's rely on Edge Generation loop checks, but set start point correctly.
    
    ax = MARGIN_INCHES
    ay = MARGIN_INCHES
    
    # Determine Start Point (Top-Left)
    start_x = ax
    start_y = ay
    
    # If Left Edge starts with Socket (Top-Left is Socket)
    # AND Left Edge is responsible for vertical cut.
    # If Top-Left is a Socket Corner.
    # The path starts at INNER X if Left Edge is Sockets.
    if left_type == 'sockets':
        start_x += stock_thk
        
    path_cmds.append(f"M {f(start_x)} {f(start_y)}")
    
    # -------------------------------------------------------------------------
    # TOP EDGE (Left to Right)
    # -------------------------------------------------------------------------
    if top_type:
        count, finger_w_mm = compute_finger_layout(width_in * 25.4, CONFIG.get('TARGET_FINGER_WIDTH', 15.0))
        finger_w = convert_to_inches(finger_w_mm)
        
        for i in range(count):
            x_start = ax + (i * finger_w)
            x_end = ax + ((i + 1) * finger_w)
            is_active = (i % 2 == 0)
            
            if top_type == 'fingers' and is_active:
                # PROUD FINGER (UP)
                f_start = x_start + (fit_tol / 2.0)
                f_end = x_end - (fit_tol / 2.0)
                # Apply Glue Gap (fit_tol) to Length as well per user request
                f_height = (stock_thk + protrusion) - fit_tol
                
                path_cmds.append(f"L {f(f_start)} {f(ay)}")
                path_cmds.append(f"L {f(f_start)} {f(ay - f_height)}")
                path_cmds.append(f"L {f(f_end)} {f(ay - f_height)}")
                path_cmds.append(f"L {f(f_end)} {f(ay)}")
                path_cmds.append(f"L {f(x_end)} {f(ay)}")
            # ... (Add socket logic if Top had sockets, but currently None)
            else:
                path_cmds.append(f"L {f(x_end)} {f(ay)}")
    else:
        # Straight Edge (Top)
        # Check End Corner (Top-Right): If Right Edge starts with Socket -> Stop Short.
        target_x = ax + width_in
        if right_type == 'sockets':
            target_x -= stock_thk
        path_cmds.append(f"L {f(target_x)} {f(ay)}")

    # -------------------------------------------------------------------------
    # RIGHT EDGE (Top to Bottom)
    # -------------------------------------------------------------------------
    rx = ax + width_in
    if right_type:
        count, finger_w_mm = compute_finger_layout(height_in * 25.4, CONFIG.get('TARGET_FINGER_WIDTH', 15.0))
        finger_w = convert_to_inches(finger_w_mm)
        
        for i in range(count):
            y_start = ay + (i * finger_w)
            y_end = ay + ((i + 1) * finger_w)
            is_active = (i % 2 == 0)
            
            if right_type == 'fingers' and is_active:
                # PROUD FINGER (RIGHT)
                f_start = y_start + (fit_tol / 2.0)
                f_end = y_end - (fit_tol / 2.0)
                f_len = (stock_thk + protrusion) - fit_tol
                path_cmds.append(f"L {f(rx)} {f(f_start)}")
                path_cmds.append(f"L {f(rx + f_len)} {f(f_start)}")
                path_cmds.append(f"L {f(rx + f_len)} {f(f_end)}")
                path_cmds.append(f"L {f(rx)} {f(f_end)}")
                path_cmds.append(f"L {f(rx)} {f(y_end)}")
            
            elif right_type == 'sockets' and is_active:
                # SOCKET (LEFT/INWARD)
                f_len = stock_thk
                # Skip Entry Line if i==0 (Corner Socket)
                if i > 0:
                    path_cmds.append(f"L {f(rx)} {f(y_start)}")
                    path_cmds.append(f"L {f(rx - f_len)} {f(y_start)}")
                
                # Draw Bottom of Socket
                path_cmds.append(f"L {f(rx - f_len)} {f(y_end)}")
                
                # Skip Exit Line if i==last (Corner Socket)
                if i < count - 1:
                    path_cmds.append(f"L {f(rx)} {f(y_end)}")
            else:
                path_cmds.append(f"L {f(rx)} {f(y_end)}")
    else:
        # Straight Edge (Right)
        # Check End Corner (Bottom-Right): If Bottom Edge starts with Socket -> Stop Short.
        target_y = ay + height_in
        if bottom_type == 'sockets':
            target_y -= stock_thk
        path_cmds.append(f"L {f(rx)} {f(target_y)}")

    # -------------------------------------------------------------------------
    # BOTTOM EDGE (Right to Left)
    # -------------------------------------------------------------------------
    by = ay + height_in
    if bottom_type:
        count, finger_w_mm = compute_finger_layout(width_in * 25.4, CONFIG.get('TARGET_FINGER_WIDTH', 15.0))
        finger_w = convert_to_inches(finger_w_mm)
        
        for i in range(count):
            x_start = ax + width_in - (i * finger_w)
            x_end = ax + width_in - ((i + 1) * finger_w)
            is_active = (i % 2 == 0)
            
            if bottom_type == 'fingers' and is_active:
                f_start = x_start - (fit_tol / 2.0)
                f_end = x_end + (fit_tol / 2.0)
                f_height = (stock_thk + protrusion) - fit_tol
                path_cmds.append(f"L {f(f_start)} {f(by)}")
                path_cmds.append(f"L {f(f_start)} {f(by + f_height)}")
                path_cmds.append(f"L {f(f_end)} {f(by + f_height)}")
                path_cmds.append(f"L {f(f_end)} {f(by)}")
                path_cmds.append(f"L {f(x_end)} {f(by)}")
            # ... (Socket logic if needed)
            else:
                path_cmds.append(f"L {f(x_end)} {f(by)}")
    else:
        # Straight Edge (Bottom)
        # Check End Corner (Bottom-Left): If Left Edge starts with Socket -> Stop Short.
        target_x = ax
        if left_type == 'sockets':
            target_x += stock_thk
        path_cmds.append(f"L {f(target_x)} {f(by)}")

    # -------------------------------------------------------------------------
    # LEFT EDGE (Bottom to Top)
    # -------------------------------------------------------------------------
    lx = ax
    if left_type:
        count, finger_w_mm = compute_finger_layout(height_in * 25.4, CONFIG.get('TARGET_FINGER_WIDTH', 15.0))
        finger_w = convert_to_inches(finger_w_mm)
        
        for i in range(count):
            y_start = ay + height_in - (i * finger_w)
            y_end = ay + height_in - ((i + 1) * finger_w)
            is_active = (i % 2 == 0)
            
            if left_type == 'fingers' and is_active:
                f_start = y_start - (fit_tol / 2.0)
                f_end = y_end + (fit_tol / 2.0)
                f_len = (stock_thk + protrusion) - fit_tol
                path_cmds.append(f"L {f(lx)} {f(f_start)}")
                path_cmds.append(f"L {f(lx - f_len)} {f(f_start)}")
                path_cmds.append(f"L {f(lx - f_len)} {f(f_end)}")
                path_cmds.append(f"L {f(lx)} {f(f_end)}")
                path_cmds.append(f"L {f(lx)} {f(y_end)}")
            
            elif left_type == 'sockets' and is_active:
                # SOCKET (RIGHT/INWARD)
                f_len = stock_thk
                # Skip Entry (i=0)
                if i > 0:
                    path_cmds.append(f"L {f(lx)} {f(y_start)}")
                    path_cmds.append(f"L {f(lx + f_len)} {f(y_start)}")
                
                path_cmds.append(f"L {f(lx + f_len)} {f(y_end)}")
                
                # Skip Exit (i=count-1)
                if i < count - 1:
                    path_cmds.append(f"L {f(lx)} {f(y_end)}")
            else:
                path_cmds.append(f"L {f(lx)} {f(y_end)}")
    else:
        path_cmds.append(f"L {f(lx)} {f(ay)}")
        
    path_cmds.append("Z")
        
    return " ".join(path_cmds), canvas_w, canvas_h

def generate_combined_visualization(version, paths):
    """
    Generate a combined visualization of all 4 rails side-by-side.
    
    Canvas: 30x9 inches
    Styles: Stroke Black, Fill Colors per rail
    """
    canvas_w = 30.0
    canvas_h = 9.0
    
    # Coordinates (X, Y)
    coords = {
        'TOP': (2.3765, 2.0),
        'LEFT': (9.7922, 2.0),
        'BOTTOM': (15.1527, 2.0),
        'RIGHT': (22.4568, 2.0)
    }
    
    # Colors
    colors = {
        'TOP': "#e5db1f",
        'LEFT': "#1abce8",
        'BOTTOM': "#f975e6",
        'RIGHT': "#14f4af"
    }
    
    lines = []
    lines.append(f'<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(canvas_w)}in" height="{f(canvas_h)}in" viewBox="0 0 {f(canvas_w)} {f(canvas_h)}">')
    lines.append(f'  <title>COMBINED_RAILS_VISUALIZATION</title>')
    lines.append(f'  <g id="Combined Rails">')
    
    # Draw each rail
    # Order: TOP, LEFT, BOTTOM, RIGHT
    for key in ['TOP', 'LEFT', 'BOTTOM', 'RIGHT']:
        if key in paths:
            path_d = paths[key]
            x, y = coords[key]
            fill = colors[key]
            
            # Group with translation
            lines.append(f'    <g transform="translate({f(x)}, {f(y)})">')
            # Stroke black, Fill colored
            lines.append(f'      <path d="{path_d}" fill="{fill}" stroke="#000000" stroke-width="{STROKE_WIDTH}"/>')
            lines.append(f'    </g>')
            
    lines.append('  </g>')
    lines.append('</svg>')
    
    return "\n".join(lines)

def generate_front_bezel_parts(version):
    """Generate FRONT_BEZEL SVGs (PERIMETER, WINDOW)."""
    width_in = convert_to_inches(CONFIG['TOTAL_WIDTH'])
    height_in = convert_to_inches(CONFIG['TOTAL_HEIGHT'])
    
    canvas_w = width_in + (2 * MARGIN_INCHES)
    canvas_h = height_in + (2 * MARGIN_INCHES)
    
    # Bezel is a simple frame held by rabbets (No fingers/sockets)
    finger_config = {
        'top': None,
        'right': None,
        'bottom': None,
        'left': None
    }
    
    files = {}
    
    # PERIMETER
    perimeter_elements = []
    perimeter_elements.append(create_svg_header(canvas_w, canvas_h, f"FRONT_BEZEL_PERIMETER"))
    
    path_d, _, _ = generate_perimeter_with_fingers("FRONT_BEZEL", width_in, height_in, finger_config)
    perimeter_elements.append(create_path(path_d, COLOR_PERIMETER))
    
    perimeter_elements.append(create_svg_footer())
    files[f"FRONT_BEZEL_PERIMETER.v{version}.svg"] = "\n".join(perimeter_elements)
    
    # WINDOW
    window_elements = []
    window_elements.append(create_svg_header(canvas_w, canvas_h, f"FRONT_BEZEL_WINDOW"))
    
    bezel_w = convert_to_inches(CONFIG.get('BEZEL_WIDTH', 1.59))
    ax = MARGIN_INCHES
    ay = MARGIN_INCHES
    
    win_x = ax + bezel_w
    win_y = ay + bezel_w
    win_w = width_in - (2 * bezel_w)
    win_h = height_in - (2 * bezel_w)
    
    window_d = f"M {f(win_x)} {f(win_y)} L {f(win_x)} {f(win_y + win_h)} L {f(win_x + win_w)} {f(win_y + win_h)} L {f(win_x + win_w)} {f(win_y)} Z"
    window_elements.append(create_path(window_d, COLOR_PERIMETER))
    
    window_elements.append(create_svg_footer())
    files[f"FRONT_BEZEL_WINDOW.v{version}.svg"] = "\n".join(window_elements)
    
    # VISUALIZATION
    viz_elements = []
    viz_elements.append(create_svg_header(canvas_w, canvas_h, f"VISUALIZATION_FRONT_BEZEL.v{version}"))
    viz_elements.append(create_path(path_d, COLOR_PERIMETER))
    viz_elements.append(create_path(window_d, COLOR_PERIMETER))
    viz_elements.append(create_svg_footer())
    files[f"VISUALIZATION_FRONT_BEZEL.v{version}.svg"] = "\n".join(viz_elements)
    
    return files

def generate_rail_parts(rail_name, is_horizontal, has_motor_pocket, version):
    """Generate rail SVGs (PERIMETER, HOLES, POCKETS, RABBETS)."""
    if is_horizontal:
        rail_w_in = convert_to_inches(CONFIG['TOTAL_WIDTH'])
        rail_h_in = convert_to_inches(CONFIG['BOX_DEPTH'])
    else:
        # For vertical rails, length is TOTAL_HEIGHT
        rail_w_in = convert_to_inches(CONFIG['TOTAL_HEIGHT'])
        rail_h_in = convert_to_inches(CONFIG['BOX_DEPTH'])
    
    # Symmetrical Odd Count Finger Logic
    if is_horizontal:
        # TOP_RAIL / BOTTOM_RAIL (Ends only)
        finger_config = {
            'top': None,         # Face (Rabbet)
            'right': 'fingers',  # End with Finger
            'bottom': None,      # Back (Rabbet)
            'left': 'fingers'    # Start with Finger
        }
    else:
        # LEFT_RAIL / RIGHT_RAIL (Ends only)
        finger_config = {
            'top': None,         # Face (Rabbet)
            'right': 'sockets',  # End with Socket
            'bottom': None,      # Back (Rabbet)
            'left': 'sockets'    # Start with Socket
        }
    path_d, p_width, p_height = generate_perimeter_with_fingers(rail_name, rail_w_in, rail_h_in, finger_config)
    
    # Use the canvas dimensions returned by generate_perimeter to ensure protrusions fit
    canvas_w = p_width
    canvas_h = p_height
    
    # Restore margins for hole positioning logic
    ax = MARGIN_INCHES
    ay = MARGIN_INCHES
    
    files = {}
    
    # Update Header with correct dimensions
    perimeter_elements = []
    perimeter_elements.append(create_svg_header(canvas_w, canvas_h, f"{rail_name}_PERIMETER"))
    perimeter_elements.append(create_path(path_d, COLOR_PERIMETER))
    
    perimeter_elements.append(create_svg_footer())
    files[f"{rail_name}_PERIMETER.v{version}.svg"] = "\n".join(perimeter_elements)
    
    # HOLES (Motor Mounts) & POCKETS (Motor Recess)
    holes_elements = []
    pockets_elements = []
    
    # Pre-calculate motor position for use in Holes and Viz
    motor_x_in = 0
    motor_y_in = 0
    pocket_in = 0
    
    if has_motor_pocket and CONFIG.get('MOTOR_POCKET_ENABLED', False):
        holes_elements.append(create_svg_header(canvas_w, canvas_h, f"{rail_name}_HOLES"))
        pockets_elements.append(create_svg_header(canvas_w, canvas_h, f"{rail_name}_POCKETS"))
        
        # Center of Rail
        motor_x_in = convert_to_inches(CONFIG.get('MOTOR_POCKET_X', 0))
        motor_y_in = rail_h_in / 2
        
        # 1. POCKET (NEMA Frame - default 42mm sq)
        pocket_mm = CONFIG.get('MOTOR_POCKET_SIZE', 42.0)
        pocket_in = convert_to_inches(pocket_mm)
        
        pockets_elements.append(create_rect(
            ax + motor_x_in - pocket_in/2,
            ay + motor_y_in - pocket_in/2,
            pocket_in,
            pocket_in,
            COLOR_POCKETS
        ))
        
        # 2. SHAFT HOLE (0.5" / 12.7mm)
        holes_elements.append(create_circle(ax + motor_x_in, ay + motor_y_in, 0.25, COLOR_HOLES))
        
        # 3. MOUNTING HOLES (31mm pattern, 3.4mm holes)
        pattern_mm = CONFIG.get('MOTOR_MOUNT_PATTERN', 31.0)
        pattern_in = convert_to_inches(pattern_mm)
        mount_r = convert_to_inches(1.7) # 3.4mm / 2
        offset = pattern_in / 2.0
        
        hole_locs = [
            (-offset, -offset), (offset, -offset),
            (-offset, offset), (offset, offset)
        ]
        for dx, dy in hole_locs:
            holes_elements.append(create_circle(ax + motor_x_in + dx, ay + motor_y_in + dy, mount_r, COLOR_HOLES))
            
        holes_elements.append(create_svg_footer())
        pockets_elements.append(create_svg_footer())
        
        files[f"{rail_name}_HOLES.v{version}.svg"] = "\n".join(holes_elements)
        files[f"{rail_name}_POCKETS.v{version}.svg"] = "\n".join(pockets_elements)

    # RABBETS (Front & Back)
    rabbets_elements = []
    rabbets_elements.append(create_svg_header(canvas_w, canvas_h, f"{rail_name}_RABBETS.v{version}"))
    
    front_w = CONFIG.get('FRONT_RABBET_WIDTH', 0.3)
    back_w = CONFIG.get('BACK_RABBET_WIDTH', 0.3)
    
    rabbets_elements.append(create_rect(ax, ay, rail_w_in, front_w, COLOR_RABBETS))
    rabbets_elements.append(create_rect(ax, ay + rail_h_in - back_w, rail_w_in, back_w, COLOR_RABBETS))
    
    rabbets_elements.append(create_svg_footer())
    files[f"{rail_name}_RABBETS.v{version}.svg"] = "\n".join(rabbets_elements)
    
    # NO BACK SCREW HOLES - Removed as per user request
    
    # VISUALIZATION
    viz_elements = []
    viz_elements.append(create_svg_header(canvas_w, canvas_h, f"VISUALIZATION_{rail_name}.v{version}"))
    viz_elements.append(create_path(path_d, COLOR_PERIMETER))
    viz_elements.append(create_rect(ax, ay, rail_w_in, front_w, COLOR_RABBETS))
    viz_elements.append(create_rect(ax, ay + rail_h_in - back_w, rail_w_in, back_w, COLOR_RABBETS))
    
    if has_motor_pocket and CONFIG.get('MOTOR_POCKET_ENABLED', False):
        # Scale logic for visual? No, straight rect
        viz_elements.append(create_rect(ax + motor_x_in - pocket_in/2, ay + motor_y_in - pocket_in/2, pocket_in, pocket_in, COLOR_POCKETS))
        viz_elements.append(create_circle(ax + motor_x_in, ay + motor_y_in, 0.25, COLOR_HOLES))
        # Viz mount holes
        pattern_in = convert_to_inches(CONFIG.get('MOTOR_MOUNT_PATTERN', 31.0))
        offset = pattern_in / 2.0
        mount_r = convert_to_inches(1.7)
        hole_locs = [(-offset, -offset), (offset, -offset), (-offset, offset), (offset, offset)]
        for dx, dy in hole_locs:
            viz_elements.append(create_circle(ax + motor_x_in + dx, ay + motor_y_in + dy, mount_r, COLOR_HOLES))
        
    viz_elements.append(create_svg_footer())
    files[f"VISUALIZATION_{rail_name}.v{version}.svg"] = "\n".join(viz_elements)
    
    return files, path_d
def generate_blender_script(version, config, rail_paths):
    """
    Generate a complete Blender Python script that recreates the shadowbox assembly.

    This script can be opened directly in Blender's Text Editor and run to create:
    - All 6 pieces with accurate finger joint geometry
    - Correct positioning in assembled orientation
    - Two plywood materials (wide face and end grain)
    - Area light setup per JLS specifications
    - Viewport set to Material Preview and JLS Workspace
    """

    # Calculate dimensions from config
    total_width_in = convert_to_inches(config['TOTAL_WIDTH'])
    total_height_in = convert_to_inches(config['TOTAL_HEIGHT'])
    box_depth_in = convert_to_inches(config['BOX_DEPTH'])
    stock_thk_in = convert_to_inches(config['STOCK_THICKNESS'])

    # Convert to meters for Blender
    total_width_m = total_width_in * 0.0254
    total_height_m = total_height_in * 0.0254
    box_depth_m = box_depth_in * 0.0254
    stock_thk_m = stock_thk_in * 0.0254

    script = f'''#!/usr/bin/env python3
"""
OPEN ME IN BLENDER - McTell Shadowbox Assembly v{version}
=========================================================
Generated by CNC Generator - Carbide-Optimized

This script creates a complete 3D visualization of the shadowbox assembly
with accurate finger joint geometry based on your CNC SVG files.

INSTRUCTIONS:
1. Open Blender
2. Switch to Scripting workspace (or open a Text Editor panel)
3. Open this file (Text > Open)
4. Click "Run Script" or press Alt+P

The script will create:
- All 6 pieces (Top Rail, Bottom Rail, Left Rail, Right Rail, Front Bezel, Back Panel)
- Positioned in assembled orientation
- Two plywood materials: wide face (#E2CBAD) and end grain (#C0AD93)
- Area light for visualization
- Imperial units (inches) configured
- Viewport set to Material Preview with JLS Workspace
"""

import bpy
import bmesh
import re
from mathutils import Vector, Euler
import math

# ==============================================================================
# CONFIGURATION (from your CNC Generator settings)
# ==============================================================================
CONFIG = {{
    'TOTAL_WIDTH_IN': {total_width_in:.4f},
    'TOTAL_HEIGHT_IN': {total_height_in:.4f},
    'BOX_DEPTH_IN': {box_depth_in:.4f},
    'STOCK_THICKNESS_IN': {stock_thk_in:.4f},
    'STOCK_THICKNESS_M': {stock_thk_m:.6f},
    'TOTAL_WIDTH_M': {total_width_m:.6f},
    'TOTAL_HEIGHT_M': {total_height_m:.6f},
    'BOX_DEPTH_M': {box_depth_m:.6f},
}}

# SVG MARGIN used in path generation (2 inches)
MARGIN_IN = 2.0

# Plywood colors (hex to RGB 0-1)
COLOR_WIDE_FACE = (0xE2/255, 0xCB/255, 0xAD/255, 1.0)  # #E2CBAD
COLOR_END_GRAIN = (0xC0/255, 0xAD/255, 0x93/255, 1.0)  # #C0AD93

# ==============================================================================
# SVG PATH DATA (embedded from generated files)
# ==============================================================================
SVG_PATHS = {{
    'TOP_RAIL': """{rail_paths.get('TOP', 'M 0 0 Z')}""",
    'BOTTOM_RAIL': """{rail_paths.get('BOTTOM', 'M 0 0 Z')}""",
    'LEFT_RAIL': """{rail_paths.get('LEFT', 'M 0 0 Z')}""",
    'RIGHT_RAIL': """{rail_paths.get('RIGHT', 'M 0 0 Z')}""",
}}

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def parse_svg_path(path_d, margin_offset=2.0):
    """Parse SVG path d attribute into list of (x, y) vertices in inches, then convert to meters."""
    vertices = []
    commands = re.findall(r'([MLZ])\\s*([\\d.\\-\\s]*)', path_d)

    for cmd, coords_str in commands:
        if cmd == 'Z':
            continue
        coords = coords_str.strip().split()
        if len(coords) >= 2:
            x_in = float(coords[0]) - margin_offset
            y_in = float(coords[1]) - margin_offset
            x_m = x_in * 0.0254
            y_m = y_in * 0.0254
            vertices.append((x_m, y_m))

    return vertices

def create_plywood_materials():
    """Create the two plywood materials: wide face and end grain."""

    # Wide face material (#E2CBAD)
    mat_wide = bpy.data.materials.new(name="Plywood_Wide_Face")
    mat_wide.use_nodes = True
    nodes = mat_wide.node_tree.nodes
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    principled = nodes.new('ShaderNodeBsdfPrincipled')
    principled.inputs['Base Color'].default_value = COLOR_WIDE_FACE
    principled.inputs['Roughness'].default_value = 0.6
    mat_wide.node_tree.links.new(principled.outputs['BSDF'], output.inputs['Surface'])

    # End grain material (#C0AD93 - darker)
    mat_end = bpy.data.materials.new(name="Plywood_End_Grain")
    mat_end.use_nodes = True
    nodes = mat_end.node_tree.nodes
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    principled = nodes.new('ShaderNodeBsdfPrincipled')
    principled.inputs['Base Color'].default_value = COLOR_END_GRAIN
    principled.inputs['Roughness'].default_value = 0.7
    mat_end.node_tree.links.new(principled.outputs['BSDF'], output.inputs['Surface'])

    return mat_wide, mat_end

def get_face_dominant_axis(face_normal):
    """Determine which axis a face normal is most aligned with."""
    abs_normal = [abs(face_normal.x), abs(face_normal.y), abs(face_normal.z)]
    max_idx = abs_normal.index(max(abs_normal))
    return ['X', 'Y', 'Z'][max_idx]

def apply_end_grain_materials(obj, mat_wide, mat_end, end_grain_axes):
    """
    Apply end grain material to faces perpendicular to specified axes.

    end_grain_axes: list of axes ('X', 'Y', 'Z') where face normals pointing
                    along these axes should get the end grain material.
    """
    if obj.type != 'MESH':
        return

    # Ensure object has both materials
    obj.data.materials.clear()
    obj.data.materials.append(mat_wide)  # Index 0
    obj.data.materials.append(mat_end)   # Index 1

    # Use bmesh to analyze and assign materials per face
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    for face in bm.faces:
        # Get face normal in world space (after transforms applied)
        normal_world = obj.matrix_world.to_3x3() @ face.normal
        dominant_axis = get_face_dominant_axis(normal_world)

        if dominant_axis in end_grain_axes:
            face.material_index = 1  # End grain
        else:
            face.material_index = 0  # Wide face

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

def create_mesh_from_profile(name, vertices, thickness_m, collection, extrude_axis='Z'):
    """Create a 3D mesh by extruding a 2D profile and link to collection."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)

    # IMPORTANT: Link to collection immediately so it exists in the scene
    collection.objects.link(obj)

    bm = bmesh.new()

    bottom_verts = []
    for v in vertices:
        if extrude_axis == 'Z':
            vert = bm.verts.new((v[0], v[1], 0))
        elif extrude_axis == 'Y':
            vert = bm.verts.new((v[0], 0, v[1]))
        elif extrude_axis == 'X':
            vert = bm.verts.new((0, v[0], v[1]))
        bottom_verts.append(vert)

    bm.verts.ensure_lookup_table()

    if len(bottom_verts) >= 3:
        try:
            bm.faces.new(bottom_verts)
        except:
            pass

    if extrude_axis == 'Z':
        extrude_vec = Vector((0, 0, thickness_m))
    elif extrude_axis == 'Y':
        extrude_vec = Vector((0, thickness_m, 0))
    elif extrude_axis == 'X':
        extrude_vec = Vector((thickness_m, 0, 0))

    ret = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    verts = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=verts, vec=extrude_vec)

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    return obj

def create_simple_box(name, width_m, height_m, depth_m, collection):
    """Create a simple box mesh and link to specified collection."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)

    # Link to our collection
    collection.objects.link(obj)

    # Create box geometry using bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()

    # Set dimensions
    obj.dimensions = (width_m, depth_m, height_m)

    return obj

# ==============================================================================
# MAIN ASSEMBLY FUNCTION
# ==============================================================================

def create_shadowbox_assembly():
    """Create the complete McTell Shadowbox assembly."""

    print("=" * 60)
    print("Creating McTell Shadowbox Assembly v{version}")
    print("=" * 60)

    # 1. SETUP SCENE
    print("\\n[1/7] Setting up scene...")

    bpy.context.scene.unit_settings.system = 'IMPERIAL'
    bpy.context.scene.unit_settings.length_unit = 'INCHES'
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = 16
    bpy.context.scene.cycles.preview_samples = 32

    # Create collection
    collection = bpy.data.collections.new("McTell Shadowbox Assembly")
    bpy.context.scene.collection.children.link(collection)

    # Make it active
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[collection.name]

    # 2. CREATE PLYWOOD MATERIALS
    print("[2/7] Creating plywood materials...")

    mat_wide, mat_end = create_plywood_materials()
    print(f"  - Wide face: #E2CBAD")
    print(f"  - End grain: #C0AD93")

    # 3. CREATE PARTS
    print("[3/7] Creating parts...")

    stock_thk = CONFIG['STOCK_THICKNESS_M']
    total_w = CONFIG['TOTAL_WIDTH_M']
    total_h = CONFIG['TOTAL_HEIGHT_M']
    box_d = CONFIG['BOX_DEPTH_M']

    parts = {{}}

    # TOP RAIL
    print("  - Top Rail")
    top_verts = parse_svg_path(SVG_PATHS['TOP_RAIL'])
    if len(top_verts) >= 3:
        parts['TOP'] = create_mesh_from_profile("McTell_Top_Rail", top_verts, stock_thk, collection, 'Z')
    else:
        parts['TOP'] = create_simple_box("McTell_Top_Rail", total_w, stock_thk, box_d, collection)

    # BOTTOM RAIL
    print("  - Bottom Rail")
    bot_verts = parse_svg_path(SVG_PATHS['BOTTOM_RAIL'])
    if len(bot_verts) >= 3:
        parts['BOTTOM'] = create_mesh_from_profile("McTell_Bottom_Rail", bot_verts, stock_thk, collection, 'Z')
    else:
        parts['BOTTOM'] = create_simple_box("McTell_Bottom_Rail", total_w, stock_thk, box_d, collection)

    # LEFT RAIL
    print("  - Left Rail")
    left_verts = parse_svg_path(SVG_PATHS['LEFT_RAIL'])
    if len(left_verts) >= 3:
        parts['LEFT'] = create_mesh_from_profile("McTell_Left_Rail", left_verts, stock_thk, collection, 'Z')
        parts['LEFT'].rotation_euler = (0, math.radians(90), 0)
    else:
        parts['LEFT'] = create_simple_box("McTell_Left_Rail", stock_thk, total_h, box_d, collection)

    # RIGHT RAIL
    print("  - Right Rail")
    right_verts = parse_svg_path(SVG_PATHS['RIGHT_RAIL'])
    if len(right_verts) >= 3:
        parts['RIGHT'] = create_mesh_from_profile("McTell_Right_Rail", right_verts, stock_thk, collection, 'Z')
        parts['RIGHT'].rotation_euler = (0, math.radians(-90), 0)
    else:
        parts['RIGHT'] = create_simple_box("McTell_Right_Rail", stock_thk, total_h, box_d, collection)

    # FRONT BEZEL
    print("  - Front Bezel")
    parts['FRONT'] = create_simple_box("McTell_Front_Bezel", total_w, total_h, stock_thk, collection)

    # BACK PANEL
    print("  - Back Panel")
    parts['BACK'] = create_simple_box("McTell_Back_Panel", total_w, total_h, stock_thk, collection)

    # 4. POSITION PARTS
    print("[4/7] Positioning parts...")

    half_w = total_w / 2
    half_h = total_h / 2
    half_d = box_d / 2

    # Set origins to geometry center
    for key, obj in parts.items():
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        obj.select_set(False)

    # Get actual horizontal rail width (includes finger protrusions)
    top_rail_width = parts['TOP'].dimensions.x
    finger_tip_x = top_rail_width / 2

    # Position each part
    parts['TOP'].location = (0, 0, half_h - stock_thk/2)
    parts['BOTTOM'].location = (0, 0, -half_h + stock_thk/2)
    parts['LEFT'].location = (-finger_tip_x + stock_thk/2, 0, 0)
    parts['RIGHT'].location = (finger_tip_x - stock_thk/2, 0, 0)
    parts['FRONT'].location = (0, -half_d - stock_thk/2, 0)
    parts['BACK'].location = (0, half_d + stock_thk/2, 0)

    # 5. APPLY TRANSFORMS AND MATERIALS
    print("[5/7] Applying transforms and materials...")

    # Apply transforms first
    for key, obj in parts.items():
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        obj.select_set(False)

    # Define end grain axes for each part (after transforms applied)
    # End grain = narrow 15mm faces = faces whose normals point perpendicular to the wide face
    end_grain_config = {{
        'TOP': ['X'],           # End grain on left/right (finger sides)
        'BOTTOM': ['X'],        # End grain on left/right (finger sides)
        'LEFT': ['Z'],          # After rotation, end grain points up/down
        'RIGHT': ['Z'],         # After rotation, end grain points up/down
        'FRONT': ['X', 'Z'],    # End grain on all 4 edges
        'BACK': ['X', 'Z'],     # End grain on all 4 edges
    }}

    for key, obj in parts.items():
        apply_end_grain_materials(obj, mat_wide, mat_end, end_grain_config.get(key, []))

    # 6. ADD LIGHTING
    print("[6/7] Setting up lighting...")

    # Area light per JLS specifications
    light_data = bpy.data.lights.new(name="Area_Light", type='AREA')
    light_data.color = (1.0, 1.0, 1.0)  # #FFFFFF
    light_data.energy = 45.0            # Power: 45
    light_data.shape = 'SQUARE'         # Shape: square
    light_data.size = 300 * 0.0254      # Size: 300 (convert inches to meters)
    light_data.spread = math.radians(180)  # Spread: 180 degrees

    # Set exposure on the scene/view layer
    bpy.context.scene.view_settings.exposure = 4.0

    light_obj = bpy.data.objects.new("Area_Light", light_data)
    collection.objects.link(light_obj)

    # Location: -90", -20", -80" (convert to meters)
    light_obj.location = (-90 * 0.0254, -20 * 0.0254, -80 * 0.0254)
    # Rotation: 0, 208, 0 degrees
    light_obj.rotation_euler = (0, math.radians(208), 0)

    # 7. SET VIEWPORT TO MATERIAL PREVIEW AND SELECT JLS WORKSPACE
    print("[7/7] Setting viewport and workspace...")

    # Set viewport shading to Material Preview
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'MATERIAL'
                    break
            break

    # Frame all objects
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            override = bpy.context.copy()
            override['area'] = area
            with bpy.context.temp_override(**override):
                bpy.ops.view3d.view_all(center=True)
            break

    # Switch to JLS Workspace if it exists
    if "JLS Workspace" in bpy.data.workspaces:
        bpy.context.window.workspace = bpy.data.workspaces["JLS Workspace"]
        print("  - Switched to JLS Workspace")
    else:
        print("  - JLS Workspace not found, using current workspace")

    print("\\n" + "=" * 60)
    print("ASSEMBLY COMPLETE!")
    print("=" * 60)
    print(f"\\nDimensions:")
    print(f"  Total Width:  {{CONFIG['TOTAL_WIDTH_IN']:.2f}} inches")
    print(f"  Total Height: {{CONFIG['TOTAL_HEIGHT_IN']:.2f}} inches")
    print(f"  Box Depth:    {{CONFIG['BOX_DEPTH_IN']:.2f}} inches")
    print(f"  Stock:        {{CONFIG['STOCK_THICKNESS_IN']:.4f}} inches (15mm)")
    print(f"\\nMaterials:")
    print(f"  Wide face: #E2CBAD")
    print(f"  End grain: #C0AD93")
    print(f"\\nParts created: {{len(parts)}}")
    print("\\nTIP: Press Numpad 0 for camera view, or use the viewport controls to orbit.")

# ==============================================================================
# RUN
# ==============================================================================
if __name__ == "__main__":
    create_shadowbox_assembly()
'''

    return script


def generate_back_panel_parts(version):
    """Generate BACK_PANEL SVGs (PERIMETER, HOLES, RABBETS)."""
    width_in = convert_to_inches(CONFIG['TOTAL_WIDTH'])
    height_in = convert_to_inches(CONFIG['TOTAL_HEIGHT'])
    
    canvas_w = width_in + (2 * MARGIN_INCHES)
    canvas_h = height_in + (2 * MARGIN_INCHES)
    ax = MARGIN_INCHES
    ay = MARGIN_INCHES
    
    files = {}
    
    # PERIMETER - simple rectangle (no fingers per user requirement)
    perimeter_elements = []
    perimeter_elements.append(create_svg_header(canvas_w, canvas_h, f"BACK_PANEL_PERIMETER"))
    
    path_d = f"M {f(ax)} {f(ay)} L {f(ax + width_in)} {f(ay)} L {f(ax + width_in)} {f(ay + height_in)} L {f(ax)} {f(ay + height_in)} Z"
    perimeter_elements.append(create_path(path_d, COLOR_PERIMETER))
    
    perimeter_elements.append(create_svg_footer())
    files[f"BACK_PANEL_PERIMETER.v{version}.svg"] = "\n".join(perimeter_elements)
    
    # HOLES - screw pilot holes for removable back panel
    holes_elements = []
    holes_elements.append(create_svg_header(canvas_w, canvas_h, f"BACK_PANEL_HOLES"))
    
    back_rabbet_w = CONFIG.get('BACK_RABBET_WIDTH', 0.3)
    hole_offset = back_rabbet_w / 2
    hole_r = convert_to_inches(CONFIG.get('SCREW_PILOT_DIA', 5.0)) / 2
    
    # Position holes to align with screw holes in the rail back rabbets
    hole_positions = [
        (ax + hole_offset, ay + hole_offset),
        (ax + width_in - hole_offset, ay + hole_offset),
        (ax + hole_offset, ay + height_in - hole_offset),
        (ax + width_in - hole_offset, ay + height_in - hole_offset),
        (ax + width_in/3, ay + hole_offset),
        (ax + 2*width_in/3, ay + hole_offset),
        (ax + width_in/3, ay + height_in - hole_offset),
        (ax + 2*width_in/3, ay + height_in - hole_offset),
        (ax + hole_offset, ay + height_in/3),
        (ax + hole_offset, ay + 2*height_in/3),
        (ax + width_in - hole_offset, ay + height_in/3),
        (ax + width_in - hole_offset, ay + 2*height_in/3),
    ]
    
    for hx, hy in hole_positions:
        holes_elements.append(create_circle(hx, hy, hole_r, COLOR_HOLES))
    
    holes_elements.append(create_svg_footer())
    files[f"BACK_PANEL_HOLES.v{version}.svg"] = "\n".join(holes_elements)
    
    # VISUALIZATION - perimeter + holes superimposed
    viz_elements = []
    viz_elements.append(create_svg_header(canvas_w, canvas_h, f"VISUALIZATION_BACK_PANEL.v{version}"))
    viz_elements.append(create_path(path_d, COLOR_PERIMETER))
    for hx, hy in hole_positions:
        viz_elements.append(create_circle(hx, hy, hole_r, COLOR_HOLES))
    viz_elements.append(create_svg_footer())
    files[f"VISUALIZATION_BACK_PANEL.v{version}.svg"] = "\n".join(viz_elements)
    
    return files

# ==============================================================================
# UI - Simplified from v42
# ==============================================================================

class RoundedButton(tk.Canvas):
    def __init__(self, parent, width, height, corner_radius, color="#59c135", fg="white", command=None, text="", font=("Arial", 16, "bold")):
        tk.Canvas.__init__(self, parent, borderwidth=0, relief="flat", highlightthickness=0, bg=parent["bg"])
        self.command = command
        self.fg = fg
        self.normal_color = color
        self.hover_color = "#6be042"
        self.width = width
        self.height = height
        self.radius = corner_radius
        self.text_val = text
        self.font = font
        
        self.configure(width=width, height=height)
        self.draw(self.normal_color)
        
        self.bind("<Button-1>", self.on_click)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def draw(self, fill_color):
        self.delete("all")
        r = self.radius
        w = self.width
        h = self.height
        
        self.create_oval(0, 0, 2*r, 2*r, fill=fill_color, outline=fill_color)
        self.create_oval(w-2*r, 0, w, 2*r, fill=fill_color, outline=fill_color)
        self.create_rectangle(r, 0, w-r, 2*r, fill=fill_color, outline=fill_color)
        
        self.create_text(w/2, h/2, text=self.text_val, fill=self.fg, font=self.font)

    def on_click(self, event):
        if self.command:
            self.command()
    
    def on_enter(self, event):
        self.draw(self.hover_color)
    
    def on_leave(self, event):
        self.draw(self.normal_color)


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + self.widget.winfo_width() + 10
        y = y + self.widget.winfo_rooty()
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffff", foreground="#00008B",
                         relief=tk.SOLID, borderwidth=1,
                         font=("Arial", 10, "normal"), padx=5, pady=3)
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class CarbideOptimizedApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CNC Generator - Carbide-Optimized v45")
        self.geometry("1100x700")
        self.configure(bg="#1e1e24")

        target_path = Path("/Users/joelsilverman/Desktop/2026 Files/26-005 Gemini-created CNC Box Creator/Gemini McTell CNC Plans/")
        current_path = Path(__file__).resolve().parent
        default_out = str(target_path) if current_path == target_path.resolve() else ""

        self.vars = {
            'out_folder': tk.StringVar(value=default_out),
            'width': tk.StringVar(value="40.0"),
            'height': tk.StringVar(value="40.0"),
            'depth': tk.StringVar(value="4.0"),
            'stock_thk': tk.StringVar(value="15.0"),
            'tool_primary': tk.DoubleVar(value=0.25),
            'glue_gap': tk.DoubleVar(value=0.010),
            'finger_width': tk.DoubleVar(value=15.0),
            # Rabbet parameters (default 50% stock thickness)
            'front_rabbet_width': tk.StringVar(value="50%"),  # Can be % or inches
            'front_rabbet_depth': tk.StringVar(value="50%"),
            'back_rabbet_width': tk.StringVar(value="50%"),
            'back_rabbet_depth': tk.StringVar(value="50%"),
            'pilot_dia': tk.DoubleVar(value=5.0),
            'motor_enabled': tk.BooleanVar(value=True),
            'motor_x_val': tk.StringVar(value=""),
            'bezel_w': tk.DoubleVar(value=1.59),
            'cable_offset': tk.DoubleVar(value=3.0)
        }

        self.setup_ui()

    def setup_ui(self):
        container = tk.Frame(self, bg="#1e1e24")
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # Header
        tk.Label(container, text="CNC Generator - Carbide-Optimized v45", 
                 font=("Helvetica", 20, "bold"), bg="#1e1e24", fg="#8eaaff").pack(pady=(0, 5))
        
        tk.Label(container, text="Generates separate SVG files per operation for easy Carbide Create import",
                 font=("Arial", 11), bg="#1e1e24", fg="#888888").pack()

        # Main content frame with two columns
        main_frame = tk.Frame(container, bg="#1e1e24")
        main_frame.pack(fill=tk.BOTH, expand=True, pady=15)
        
        # LEFT COLUMN - Input fields
        left_col = tk.Frame(main_frame, bg="#1e1e24")
        left_col.pack(side="left", fill=tk.Y, padx=(0, 30))
        
        # RIGHT COLUMN - Button and Legend
        right_col = tk.Frame(main_frame, bg="#1e1e24")
        right_col.pack(side="left", fill=tk.Y, anchor="n", pady=20)

        # === LEFT COLUMN CONTENT ===
        input_frame = tk.Frame(left_col, bg="#1e1e24")
        input_frame.pack(fill=tk.X)

        r = 0
        
        # Output Folder
        tk.Label(input_frame, text="Output Folder:", fg="white", bg="#1e1e24", font=("Arial", 12)).grid(row=r, column=0, sticky="e", padx=(0, 5), pady=2)
        f_frame = tk.Frame(input_frame, bg="#1e1e24")
        f_frame.grid(row=r, column=1, columnspan=2, sticky="w")
        tk.Entry(f_frame, textvariable=self.vars['out_folder'], bg="#2d2d36", fg="white", width=45).pack(side="left")
        tk.Button(f_frame, text="Browse...", command=self.browse_folder).pack(side="left", padx=5)
        r += 1

        # Dimensions
        self.make_row(input_frame, r, "Total Width:", self.vars['width'], "inches"); r += 1
        self.make_row(input_frame, r, "Total Height:", self.vars['height'], "inches"); r += 1
        self.make_row(input_frame, r, "Box Depth:", self.vars['depth'], "inches"); r += 1
        
        # Material
        self.make_row(input_frame, r, "Stock Thickness:", self.vars['stock_thk'], "mm"); r += 1
        self.make_row(input_frame, r, "Tool Diameter:", self.vars['tool_primary'], "inches"); r += 1
        self.make_row(input_frame, r, "Fit Tolerance / Glue Gap:", self.vars['glue_gap'], "inches"); r += 1
        self.make_row(input_frame, r, "Target Finger Width:", self.vars['finger_width'], "mm"); r += 1
        
        # Rabbet Joinery
        tk.Label(input_frame, text="Rabbet Joinery", font=("Arial", 12, "bold"), fg="#8eaaff", bg="#1e1e24").grid(row=r, column=0, columnspan=3, sticky="w", pady=(8, 3)); r += 1
        self.make_row(input_frame, r, "Front Rabbet Width:", self.vars['front_rabbet_width'], "% or in"); r += 1
        self.make_row(input_frame, r, "Front Rabbet Depth:", self.vars['front_rabbet_depth'], "% or in"); r += 1
        self.make_row(input_frame, r, "Back Rabbet Width:", self.vars['back_rabbet_width'], "% or in"); r += 1
        self.make_row(input_frame, r, "Back Rabbet Depth:", self.vars['back_rabbet_depth'], "% or in"); r += 1
        self.make_row(input_frame, r, "Pilot Hole Dia:", self.vars['pilot_dia'], "mm"); r += 1
        
        # Bezel
        self.make_row(input_frame, r, "Bezel Width:", self.vars['bezel_w'], "inches"); r += 1

        # Motor
        cb = tk.Checkbutton(input_frame, text="Enable Motor Pocket", variable=self.vars['motor_enabled'],
                            bg="#1e1e24", fg="white", selectcolor="#1e1e24", font=("Arial", 12))
        cb.grid(row=r, column=0, columnspan=2, sticky="w", pady=5)
        r += 1

        # === RIGHT COLUMN CONTENT ===
        
        # Generate Button
        self.btn_gen = RoundedButton(right_col, width=280, height=50, corner_radius=25,
                                     color="#59c135", text="GENERATE CARBIDE SVGs",
                                     font=("Arial", 14, "bold"),
                                     command=self.run_generation)
        self.btn_gen.pack(pady=(40, 25))

        # Color Legend
        legend_frame = tk.Frame(right_col, bg="#1e1e24")
        legend_frame.pack()
        
        tk.Label(legend_frame, text="Color Legend:", font=("Arial", 12, "bold"), bg="#1e1e24", fg="white").pack(anchor="w", pady=(0, 5))
        colors = [
            (COLOR_PERIMETER, "Perimeter/Cuts (Red)"),
            (COLOR_HOLES, "Holes (Blue)"),
            (COLOR_POCKETS, "Pockets (Green)"),
            (COLOR_RABBETS, "Rabbets (Orange)")
        ]
        for color, label in colors:
            row = tk.Frame(legend_frame, bg="#1e1e24")
            row.pack(anchor="w", pady=1)
            tk.Canvas(row, width=18, height=18, bg=color, highlightthickness=0).pack(side="left", padx=(0, 8))
            tk.Label(row, text=label, bg="#1e1e24", fg="white", font=("Arial", 10)).pack(side="left")

    def make_row(self, parent, r, label_text, var, unit):
        tk.Label(parent, text=label_text, fg="white", bg="#1e1e24", font=("Arial", 12)).grid(row=r, column=0, sticky="e", padx=5, pady=3)
        tk.Entry(parent, textvariable=var, bg="#2d2d36", fg="white", width=10, font=("Arial", 12)).grid(row=r, column=1, sticky="w")
        tk.Label(parent, text=unit, fg="gray", bg="#1e1e24", font=("Arial", 10)).grid(row=r, column=2, sticky="w")

    def browse_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.vars['out_folder'].set(d)

    def run_generation(self):
        try:
            raw_out = self.vars['out_folder'].get().strip()
            if not raw_out:
                raise ValueError("Please select an Output Folder.")

            # Populate CONFIG
            v = self.vars
            CONFIG['STOCK_THICKNESS'] = convert_string_to_mm(v['stock_thk'].get(), "mm")
            CONFIG['TOOL_D_PRIMARY'] = convert_to_mm(v['tool_primary'].get(), "inches")
            CONFIG['TOOL_R'] = CONFIG['TOOL_D_PRIMARY'] / 2.0
            CONFIG['FIT_TOLERANCE'] = convert_to_mm(v['glue_gap'].get(), "inches")
            CONFIG['TARGET_FINGER_WIDTH'] = v['finger_width'].get()
            
            # Parse rabbet dimensions (can be % or inches)
            stock_thk_in = convert_to_inches(CONFIG['STOCK_THICKNESS'])
            
            def parse_rabbet_value(val_str, stock_thk):
                """Parse rabbet value - can be percentage (50%) or inches (0.25)"""
                val_str = val_str.strip()
                if '%' in val_str:
                    pct = float(val_str.replace('%', '')) / 100.0
                    return stock_thk * pct
                else:
                    return float(val_str)
            
            CONFIG['FRONT_RABBET_WIDTH'] = parse_rabbet_value(v['front_rabbet_width'].get(), stock_thk_in)
            CONFIG['FRONT_RABBET_DEPTH'] = parse_rabbet_value(v['front_rabbet_depth'].get(), stock_thk_in)
            CONFIG['BACK_RABBET_WIDTH'] = parse_rabbet_value(v['back_rabbet_width'].get(), stock_thk_in)
            CONFIG['BACK_RABBET_DEPTH'] = parse_rabbet_value(v['back_rabbet_depth'].get(), stock_thk_in)
            
            CONFIG['SCREW_PILOT_DIA'] = v['pilot_dia'].get()
            CONFIG['MOTOR_POCKET_ENABLED'] = v['motor_enabled'].get()
            CONFIG['TOTAL_WIDTH'] = convert_string_to_mm(v['width'].get(), "inches")
            CONFIG['TOTAL_HEIGHT'] = convert_string_to_mm(v['height'].get(), "inches")
            CONFIG['BOX_DEPTH'] = convert_string_to_mm(v['depth'].get(), "inches")
            CONFIG['BEZEL_WIDTH'] = convert_to_mm(v['bezel_w'].get(), "inches")
            
            # Motor position
            photograph_width = CONFIG['TOTAL_WIDTH'] - (2 * CONFIG['STOCK_THICKNESS'])
            user_x = v['motor_x_val'].get().strip()
            if user_x:
                CONFIG['MOTOR_POCKET_X'] = float(user_x)
            else:
                CONFIG['MOTOR_POCKET_X'] = 0.4155 * photograph_width
            
            CONFIG['MOTOR_CABLE_OFFSET'] = convert_to_mm(v['cable_offset'].get(), "inches")
            CONFIG['CABLE_HOLE_X'] = CONFIG['MOTOR_POCKET_X'] - CONFIG['MOTOR_CABLE_OFFSET']

            # Setup output directory
            out_path = Path(raw_out)
            out_path.mkdir(parents=True, exist_ok=True)
            
            existing_versions = []
            for child in out_path.iterdir():
                if child.is_dir() and "McTell SVGs v" in child.name:
                    match = re.search(r'v(\d+)', child.name)
                    if match:
                        existing_versions.append(int(match.group(1)))
            
            next_ver = max(existing_versions) + 1 if existing_versions else 1
            
            final_out_dir = out_path / f"McTell SVGs v{next_ver}"
            final_out_dir.mkdir(parents=True, exist_ok=True)

            # Generate all parts
            all_files = {}
            rail_paths = {}
            
            all_files.update(generate_front_bezel_parts(next_ver))
            
            # TOP RAIL
            f_top, p_top = generate_rail_parts("TOP_RAIL", is_horizontal=True, has_motor_pocket=False, version=next_ver)
            all_files.update(f_top)
            rail_paths['TOP'] = p_top
            
            # BOTTOM RAIL
            f_bot, p_bot = generate_rail_parts("BOTTOM_RAIL", is_horizontal=True, has_motor_pocket=True, version=next_ver)
            all_files.update(f_bot)
            rail_paths['BOTTOM'] = p_bot
            
            # LEFT RAIL
            f_left, p_left = generate_rail_parts("LEFT_RAIL", is_horizontal=False, has_motor_pocket=False, version=next_ver)
            all_files.update(f_left)
            rail_paths['LEFT'] = p_left
            
            # RIGHT RAIL
            f_right, p_right = generate_rail_parts("RIGHT_RAIL", is_horizontal=False, has_motor_pocket=False, version=next_ver)
            all_files.update(f_right)
            rail_paths['RIGHT'] = p_right
            
            all_files.update(generate_back_panel_parts(next_ver))
            
            # Combined Visualization
            combined_svg = generate_combined_visualization(next_ver, rail_paths)
            all_files[f"VISUALIZATION_COMBINED_RAILS.v{next_ver}.svg"] = combined_svg
            
            # Generate Blender Script
            blender_script = generate_blender_script(next_ver, CONFIG, rail_paths)

            # Write files
            for fname, content in all_files.items():
                with open(final_out_dir / fname, 'w') as f:
                    f.write(content)
            
            # Write Blender script
            blender_script_path = final_out_dir / f"OPEN_ME_IN_BLENDER.v{next_ver}.py"
            with open(blender_script_path, 'w') as f:
                f.write(blender_script)

            # Save config
            with open(final_out_dir / "config.json", "w") as f:
                json.dump(CONFIG, f, indent=4)

            file_count = len(all_files)
            messagebox.showinfo("Success", 
                f"Generation Complete!\n\n"
                f"Version: v{next_ver}\n"
                f"Files: {file_count} SVGs + 1 Blender Script\n"
                f"Location: {final_out_dir}\n\n"
                f"Blender Script: OPEN_ME_IN_BLENDER.v{next_ver}.py")

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")


if __name__ == "__main__":
    app = CarbideOptimizedApp()
    app.mainloop()

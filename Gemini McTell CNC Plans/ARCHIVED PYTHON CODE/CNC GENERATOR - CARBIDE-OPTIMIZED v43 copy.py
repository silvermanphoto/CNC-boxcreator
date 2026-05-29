#!/usr/bin/env python3
"""
CNC GENERATOR - CARBIDE-OPTIMIZED v43
======================================
Fork of v42, optimized for Carbide Create CAM workflow.

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
    
    # Protrusion for "Chiclet" look (Manual Roundover)
    # Woodsmith / Half-Round Logic: Protrusion = Radius of Roundover Bit
    # Standard is Stock Thickness / 2.0
    protrusion = stock_thk / 2.0
    
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
    
    return files
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
        self.title("CNC Generator - Carbide-Optimized v43")
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
        tk.Label(container, text="CNC Generator - Carbide-Optimized v43", 
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
        self.make_row(input_frame, r, "Glue Gap:", self.vars['glue_gap'], "inches"); r += 1
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
            
            all_files.update(generate_front_bezel_parts(next_ver))
            all_files.update(generate_rail_parts("TOP_RAIL", is_horizontal=True, has_motor_pocket=False, version=next_ver))
            all_files.update(generate_rail_parts("BOTTOM_RAIL", is_horizontal=True, has_motor_pocket=True, version=next_ver))
            all_files.update(generate_rail_parts("LEFT_RAIL", is_horizontal=False, has_motor_pocket=False, version=next_ver))
            all_files.update(generate_rail_parts("RIGHT_RAIL", is_horizontal=False, has_motor_pocket=False, version=next_ver))
            all_files.update(generate_back_panel_parts(next_ver))

            # Write files
            for fname, content in all_files.items():
                with open(final_out_dir / fname, 'w') as f:
                    f.write(content)

            # Save config
            with open(final_out_dir / "config.json", "w") as f:
                json.dump(CONFIG, f, indent=4)

            file_count = len(all_files)
            messagebox.showinfo("Success", 
                f"Generation Complete!\n\n"
                f"Version: v{next_ver}\n"
                f"Files: {file_count} SVGs\n"
                f"Location: {final_out_dir}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")


if __name__ == "__main__":
    app = CarbideOptimizedApp()
    app.mainloop()

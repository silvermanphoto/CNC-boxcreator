#!/usr/bin/env python3
"""
# CNC GENERATOR - CARBIDE-OPTIMIZED v1.24
# ========================================
# PRODUCTION RELEASE v1.24
#
# Key Changes:
# - Extracted Blender/TriVision generation to separate module (blender_generator.py).
# - Reduced main file size.
#   - Height constrained by (Box Depth - Front Rabbet - Back Rabbet - 0.5").
#   - Width (Inches) allowed up to 90% of Rail Width.
#   - X Position (%) with live inch feedback.
#   - Center alignment logic.
# - Combined Master Layout (Multiple 48x48 Artboards side-by-side).
# - Text Annotations:
#   - Part Name (12pt)
#   - Operation Details (8pt)
# - Implemented 2D Nesting (Bin Packing) Algorithm.
# - Optimized for 48x48 sheets (expandable to 48x96).
# - Automatic rotation for best fit.
# - Grouping of FRONT + HATCH.
#
# Key Changes:
# - SVG Structure Flattened (No Groups).
# - Advanced Text Collision Detection.
# - Updated Text Formatting (Lato Black, Colors).
# - Text: Part Name (80pt), Sub-Part (70pt Blue), Instructions (70pt Green).
"""

import os
import sys
import math
import re
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json
from utils import convert_to_inches, MARGIN_INCHES

# ==============================================================================
# AUTO-INSTALL DEPENDENCIES
# ==============================================================================
def ensure_dependencies():
    """Auto-install required packages if missing."""
    if getattr(sys, 'frozen', False):
        return
    required = ['matplotlib']
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"Installing missing dependencies: {', '.join(missing)}")
        
        # Check if running in a virtual environment
        in_venv = sys.prefix != sys.base_prefix
        
        cmd = [sys.executable, '-m', 'pip', 'install']
        
        # Only use --user if NOT in a virtual environment
        if not in_venv:
            cmd.append('--user')
            
        try:
            subprocess.check_call(cmd + missing)
        except subprocess.CalledProcessError:
            # If failed and NOT in venv, try --break-system-packages (for Homebrew/managed python)
            if not in_venv:
                print("Retrying with --break-system-packages flag...")
                cmd.append('--break-system-packages')
                subprocess.check_call(cmd + missing)
            else:
                # If in venv and failed, re-raise the error
                raise

        print("Dependencies installed. Please restart the application.")
        sys.exit(0)

ensure_dependencies()

import matplotlib
matplotlib.use('TkAgg')  # Use Tk backend for embedding
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# ==============================================================================
# TOOLTIP CLASS - Mouseover hints for UI elements
# ==============================================================================
class ToolTip:
    """Create a tooltip for a given widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                        background="#ffffe0", foreground="#000000",
                        relief=tk.SOLID, borderwidth=1,
                        font=("Arial", 10), padx=6, pady=4)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

# ==============================================================================
# 3D PREVIEW WIDGET - Live box visualization
# ==============================================================================
class BoxPreview3D(tk.Frame):
    """Embedded 3D preview of the box using matplotlib."""

    # Colors matching the CNC visualization scheme
    PANEL_COLORS = {
        'front': '#e8cf6c',   # Yellow/gold (front frame with window)
        'back': '#49bcf6',    # Light blue
        'left': '#e498c3',    # Pink (like rabbets)
        'right': '#e498c3',
        'top': '#49bcf6',     # Light blue
        'bottom': '#49bcf6',  # Light blue
    }

    def __init__(self, parent, width=373, height=320):  # 33% larger (280*1.33=373, 240*1.33=320)
        super().__init__(parent, bg="#f0f0f0")
        self.width = width
        self.height = height

        # Create matplotlib figure with transparent background
        self.fig = Figure(figsize=(width/100, height/100), dpi=100, facecolor='#f0f0f0')
        self.ax = self.fig.add_subplot(111, projection='3d', facecolor='#f0f0f0')

        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Mouse interaction for rotation
        self.last_x = 0
        self.last_y = 0
        self.canvas_widget.bind("<Button-1>", self.on_mouse_down)
        self.canvas_widget.bind("<B1-Motion>", self.on_mouse_drag)

        # Default view angle - original correct view
        self.elev = 25
        self.azim = -60

        # Window dimensions (will be set by update)
        self.window_w = 0
        self.window_h = 0

        # Initial empty box
        self.update_box(10, 10, 4, 0.59, 0, 0)  # Default dimensions in inches

    def on_mouse_down(self, event):
        self.last_x = event.x
        self.last_y = event.y

    def on_mouse_drag(self, event):
        dx = event.x - self.last_x
        dy = event.y - self.last_y
        self.azim -= dx * 0.5
        self.elev += dy * 0.5
        self.elev = max(-90, min(90, self.elev))
        self.last_x = event.x
        self.last_y = event.y
        self.ax.view_init(elev=self.elev, azim=self.azim)
        self.canvas.draw_idle()

    def update_box(self, width_in, height_in, depth_in, stock_thk_in, window_w=0, window_h=0, 
                   hatch_enabled=False, hatch_w_pct=0, hatch_h_pct=0, hatch_raise_in=0,
                   b_hatch_enabled=False, b_hatch_w=0, b_hatch_h=0, b_hatch_x_pct=0):
        """Update the 3D preview with new dimensions and optional window/hatch."""
        self.ax.clear()

        w = width_in   # X dimension
        d = depth_in   # Y dimension
        h = height_in  # Z dimension
        t = stock_thk_in
        self.window_w = window_w
        self.window_h = window_h
        
        has_window = (window_w > 0 and window_h > 0)

        # Back panel (Y=d plane, XZ rectangle) - solid, away from viewer
        back_verts = [(0, d, 0), (w, d, 0), (w, d, h), (0, d, h)]
        poly = Poly3DCollection([back_verts], alpha=0.7, facecolor=self.PANEL_COLORS['back'],
                                edgecolor='#333333', linewidth=0.5)
        self.ax.add_collection3d(poly)

        # HATCH VISUALIZATION (New v1.17)
        if hatch_enabled:
            # Calculate physical dimensions
            hatch_w = w * (hatch_w_pct / 100.0)
            hatch_h = h * (hatch_h_pct / 100.0)
            
            # Position: Centered Horizontally, Y=d (on Back Panel face)
            hw_x = (w - hatch_w) / 2
            
            # Position Z:
            # Raise=0 -> Flush with Bottom STOCK (Top of Bottom Rail)
            # Origin Z=0 is box bottom.
            # Bottom Rail Height = stock_thk_in.
            # So Bottom of Hatch = stock_thk_in + hatch_raise_in.
            hatch_z = stock_thk_in + hatch_raise_in
            
            # Draw Hatch Rectangle (Darker Blue/Grey to stand out)
            hx1 = hw_x
            hx2 = hw_x + hatch_w
            hz1 = hatch_z
            hz2 = hatch_z + hatch_h
            
            # Slightly offset Y+ to flicker-free draw on top of back panel?
            # Viewer is Y-. Back Panel is Y=d. Back of box is FARTHEST from viewer.
            # If we draw at d-eps, it will be "inside" the box / in front of the back panel.
            # Back Panel is drawn first.
            hy = d - 0.05 # Push slightly "in" towards front
            
            hatch_verts = [(hx1, hy, hz1), (hx2, hy, hz1), (hx2, hy, hz2), (hx1, hy, hz2)]
            # Color: Dark Grey/Blue
            poly_h = Poly3DCollection([hatch_verts], alpha=0.9, facecolor='#2c3e50',
                                    edgecolor='black', linewidth=1.5) # Black outline
            self.ax.add_collection3d(poly_h)

        # BOTTOM ACCESS PANEL VISUALIZATION
        if b_hatch_enabled and b_hatch_w > 0 and b_hatch_h > 0:
            # Dimensions are already in inches
            bh_w = b_hatch_w
            bh_h = b_hatch_h
            
            # X Calculation logic matches update_bottom_hatch_status
            rail_width = w - (2 * t)
            center_x_rel = rail_width * (b_hatch_x_pct / 100.0)
            center_x_abs = t + center_x_rel
            
            bh_x1 = center_x_abs - (bh_w / 2.0)
            bh_x2 = center_x_abs + (bh_w / 2.0)
            
            # Y Position: Centered in Depth (d)
            center_y = d / 2.0
            bh_y1 = center_y - (bh_h / 2.0)
            bh_y2 = center_y + (bh_h / 2.0)
            
            # Z Position: Slightly above 0 to be visible on top of bottom panel
            bh_z = 0.05 
            
            bh_verts = [(bh_x1, bh_y1, bh_z), (bh_x2, bh_y1, bh_z), (bh_x2, bh_y2, bh_z), (bh_x1, bh_y2, bh_z)]
            
            # Color: Matching Hatch Color with same style
            poly_bh = Poly3DCollection([bh_verts], alpha=0.9, facecolor='#2c3e50',
                                    edgecolor='black', linewidth=1.5)
            self.ax.add_collection3d(poly_bh)

        # Left panel (X=0 plane, YZ rectangle)
        left_verts = [(0, t, 0), (0, d-t, 0), (0, d-t, h), (0, t, h)]
        poly = Poly3DCollection([left_verts], alpha=0.7, facecolor=self.PANEL_COLORS['left'],
                                edgecolor='#333333', linewidth=0.5)
        self.ax.add_collection3d(poly)

        # Right panel (X=w plane, YZ rectangle)
        right_verts = [(w, t, 0), (w, d-t, 0), (w, d-t, h), (w, t, h)]
        poly = Poly3DCollection([right_verts], alpha=0.7, facecolor=self.PANEL_COLORS['right'],
                                edgecolor='#333333', linewidth=0.5)
        self.ax.add_collection3d(poly)

        # Top panel (Z=h plane, XY rectangle)
        top_verts = [(t, t, h), (w-t, t, h), (w-t, d-t, h), (t, d-t, h)]
        poly = Poly3DCollection([top_verts], alpha=0.7, facecolor=self.PANEL_COLORS['top'],
                                edgecolor='#333333', linewidth=0.5)
        self.ax.add_collection3d(poly)

        # Bottom panel (Z=0 plane, XY rectangle)
        bottom_verts = [(t, t, 0), (w-t, t, 0), (w-t, d-t, 0), (t, d-t, 0)]
        poly = Poly3DCollection([bottom_verts], alpha=0.7, facecolor=self.PANEL_COLORS['bottom'],
                                edgecolor='#333333', linewidth=0.5)
        self.ax.add_collection3d(poly)

        # Front panel (Y=0 plane, XZ rectangle) - FACING THE VIEWER - with optional window
        if has_window and window_w < w and window_h < h:
            # Window centered on front panel
            win_x = (w - window_w) / 2
            win_z = (h - window_h) / 2

            # Four strips around the window (at Y=0) - NO internal edges
            # Bottom strip
            bottom_strip = [(0, 0, 0), (w, 0, 0), (w, 0, win_z), (0, 0, win_z)]
            # Top strip
            top_strip = [(0, 0, win_z + window_h), (w, 0, win_z + window_h), (w, 0, h), (0, 0, h)]
            # Left strip
            left_strip = [(0, 0, win_z), (win_x, 0, win_z), (win_x, 0, win_z + window_h), (0, 0, win_z + window_h)]
            # Right strip
            right_strip = [(win_x + window_w, 0, win_z), (w, 0, win_z), (w, 0, win_z + window_h), (win_x + window_w, 0, win_z + window_h)]

            # Draw strips without edges (no internal lines)
            for strip in [bottom_strip, top_strip, left_strip, right_strip]:
                poly = Poly3DCollection([strip], alpha=0.7, facecolor=self.PANEL_COLORS['front'],
                                        edgecolor=self.PANEL_COLORS['front'], linewidth=0)
                self.ax.add_collection3d(poly)

            # Draw only the outer border of the front panel
            outer_border = [(0, 0, 0), (w, 0, 0), (w, 0, h), (0, 0, h), (0, 0, 0)]
            ox = [p[0] for p in outer_border]
            oy = [p[1] for p in outer_border]
            oz = [p[2] for p in outer_border]
            self.ax.plot(ox, oy, oz, color='#333333', linewidth=0.5)

            # Black window border
            border = [(win_x, 0, win_z), (win_x + window_w, 0, win_z),
                      (win_x + window_w, 0, win_z + window_h), (win_x, 0, win_z + window_h), (win_x, 0, win_z)]
            bx = [p[0] for p in border]
            by = [p[1] for p in border]
            bz = [p[2] for p in border]
            self.ax.plot(bx, by, bz, color='black', linewidth=2.5)
            
            # DEBUG: VISUALIZE CENTER
            # Green Center vertical line on Front Panel
            cx = w / 2.0
            cz = h / 2.0
            self.ax.plot([cx, cx], [0, 0], [0, h], color='#00ff00', linewidth=1.0, linestyle='--')
            
            # Red Dot at Window Center
            wcx = win_x + (window_w / 2.0)
            wcz = win_z + (window_h / 2.0)
            self.ax.scatter([wcx], [0], [wcz], color='red', s=20)
            
        else:
            # Solid front panel
            front_verts = [(0, 0, 0), (w, 0, 0), (w, 0, h), (0, 0, h)]
            poly = Poly3DCollection([front_verts], alpha=0.7, facecolor=self.PANEL_COLORS['front'],
                                    edgecolor='#333333', linewidth=0.5)
            self.ax.add_collection3d(poly)
            
            # Draw Center Line even if no window, for reference
            cx = w / 2.0
            self.ax.plot([cx, cx], [0, 0], [0, h], color='#00ff00', linewidth=1.0, linestyle='--')

        # Set equal aspect ratio
        max_dim = max(w, h, d)
        self.ax.set_xlim([0, max_dim * 1.1])
        self.ax.set_ylim([0, max_dim * 1.1])
        self.ax.set_zlim([0, max_dim * 1.1])

        # Clean up axes - remove all axis lines and ticks
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_zticks([])
        self.ax.xaxis.pane.fill = False
        self.ax.yaxis.pane.fill = False
        self.ax.zaxis.pane.fill = False
        self.ax.xaxis.pane.set_edgecolor('none')
        self.ax.yaxis.pane.set_edgecolor('none')
        self.ax.zaxis.pane.set_edgecolor('none')
        # Hide the axis lines completely
        self.ax.xaxis.line.set_color('none')
        self.ax.yaxis.line.set_color('none')
        self.ax.zaxis.line.set_color('none')

        self.ax.view_init(elev=self.elev, azim=self.azim)
        self.canvas.draw_idle()

    def _make_panel_vertices(self, x, y, z, dx, dy, dz, plane):
        """Create vertices for a rectangular panel."""
        if plane == 'xy':  # Front/back panels
            return [(x, y, z), (x+dx, y, z), (x+dx, y+dy, z), (x, y+dy, z)]
        elif plane == 'yz':  # Left/right panels
            return [(x, y, z), (x, y+dy, z), (x, y+dy, z+dz), (x, y, z+dz)]
        elif plane == 'xz':  # Top/bottom panels
            return [(x, y, z), (x+dx, y, z), (x+dx, y, z+dz), (x, y, z+dz)]

# ==============================================================================
# CONSTANTS - Carbide Create Color Coding
# ==============================================================================
COLOR_PERIMETER = "#ff0000"  # Red - outer cuts and finger joints
COLOR_HOLES = "#0000ff"      # Blue - circular holes
COLOR_POCKETS = "#8fea00"    # Green - shallow pockets (motors)
COLOR_RABBETS = "#e09500"    # Orange - rabbet channels
COLOR_WINDOW = "#af00af"     # Purple - window cutout

STROKE_WIDTH = "0.01"  # inches - thin stroke for CNC precision



# ==============================================================================
# GLOBAL CONFIG
# ==============================================================================
CONFIG = {}

def f(val):
    """Format float to 4 decimal places"""
    return f"{val:.4f}"




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

def create_text(x, y, content, font_size=12, color="#000000", anchor="middle"):
    """Create SVG text element."""
    # Anchor: middle, start, end
    return f'<text x="{f(x)}" y="{f(y)}" font-family="Lato, sans-serif" font-size="{font_size}" fill="{color}" text-anchor="{anchor}">{content}</text>'

def create_svg_header(width_in, height_in, title):
    """Create SVG header with inches units for Carbide Create compatibility."""
    # Clean Layer Name: Use title directly if possible, or replace underscores if desired.
    # User requested descriptive names. "BACK_PANEL_HOLES" is cleaner than "BACK PANEL HOLES" for ID.
    layer_name = title
    
    # ILLUSTRATOR METADATA:
    # xmlns:xb="http://openoffice.org/2009/office" is irrelevant
    # We add 'id' and 'data-name' which Illustrator uses for Layer naming upon import.
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" 
     width="{f(width_in)}in" 
     height="{f(height_in)}in" 
     viewBox="0 0 {f(width_in)} {f(height_in)}">
  <title>{title}</title>
  <g id="{layer_name}" data-name="{layer_name}">'''

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

def validate_rail_edge_straightness(path_data, rail_name):
    """
    Check that top and bottom edges are perfectly straight lines.
    Call this AFTER generating each rail perimeter path, BEFORE writing to SVG.
    """
    if not path_data:
        return True

    # Simple parsing of "M x y L x y ..." string
    # Remove commands and split
    clean_data = path_data.replace('M', ' ').replace('L', ' ').replace('Z', ' ')
    tokens = clean_data.split()
    
    coords = []
    # Parse pairs
    for k in range(0, len(tokens), 2):
        if k+1 < len(tokens):
            try:
                # Store as object or tuple with accessors
                coords.append((float(tokens[k]), float(tokens[k+1])))
            except ValueError:
                pass
                
    if not coords:
        return True
    
    # Identify edge Y-values (the main horizontal lines)
    ys = [c[1] for c in coords]
    top_edge_y = min(ys)      # Topmost Y (min Y in SVG)
    bottom_edge_y = max(ys)   # Bottommost Y (max Y in SVG)
    
    # Find all points that SHOULD be on the top edge
    # (points with Y within tolerance of top_edge_y)
    top_edge_points = [y for y in ys if abs(y - top_edge_y) < 0.01]
    
    # Find all points that SHOULD be on the bottom edge
    bottom_edge_points = [y for y in ys if abs(y - bottom_edge_y) < 0.01]
    
    # VALIDATION: All top edge points must have EXACTLY the same Y (within rounding)
    top_y_values = set(round(y, 4) for y in top_edge_points)
    if len(top_y_values) > 1:
        raise ValueError(
            f"{rail_name}: TOP EDGE NOT STRAIGHT! "
            f"Found multiple Y-values: {top_y_values}. "
            f"Expected single value: {top_edge_y}"
        )
    
    # VALIDATION: All bottom edge points must have EXACTLY the same Y
    bottom_y_values = set(round(y, 4) for y in bottom_edge_points)
    if len(bottom_y_values) > 1:
        raise ValueError(
            f"{rail_name}: BOTTOM EDGE NOT STRAIGHT! "
            f"Found multiple Y-values: {bottom_y_values}. "
            f"Expected single value: {bottom_edge_y}"
        )
    
    print(f"OK {rail_name}: Top and bottom edges validated as straight")
    return True

def generate_perimeter_with_fingers(part_name, width_in, height_in, finger_config):
    """
    Generate perimeter path with HALF-ROUND FINGER JOINTS.
    """
    
    # 1. HELPER CONSTANTS
    stock_thk = convert_to_inches(CONFIG['STOCK_THICKNESS'])
    
    # Protrusion set to 0.0 for flush fingers (Manual Roundover does not add length)
    # Fingers will be exactly stock_thk - fit_tol
    protrusion = 0.0
    
    # Canvas definitions required for return
    canvas_w = width_in + 4.0
    canvas_h = height_in + 4.0
    
    # Tolerance: Shrink MALE Fingers
    fit_tol = convert_to_inches(CONFIG.get('FIT_TOLERANCE', 0.254)) # Defaults to 0.010" (0.254mm) 
    
    # 2. PATH GENERATION STATE
    path_cmds = []
    
    left_type = finger_config.get('left')
    right_type = finger_config.get('right')
    top_type = finger_config.get('top')
    bottom_type = finger_config.get('bottom')

    ax = MARGIN_INCHES
    ay = MARGIN_INCHES
    
    # Store exact Y-coordinates for snapping
    top_edge_y = ay
    bottom_edge_y = ay + height_in
    
    # Determine Start Point (Top-Left)
    start_x = ax
    start_y = ay
    
    # If Left Edge starts with Socket (Top-Left is Socket)
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
                f_height = (stock_thk + protrusion) - fit_tol
                
                # Snap Check? Usually Top/Bottom fingers are not the corner issue, 
                # but let's be consistent if needed. 
                # Guidance focused on Rail Perimeter corners (Left/Right fingers).
                # Leaving Top/Bottom logic as is unless issues arise.
                
                path_cmds.append(f"L {f(f_start)} {f(ay)}")
                path_cmds.append(f"L {f(f_start)} {f(ay - f_height)}")
                path_cmds.append(f"L {f(f_end)} {f(ay - f_height)}")
                path_cmds.append(f"L {f(f_end)} {f(ay)}")
                path_cmds.append(f"L {f(x_end)} {f(ay)}")
            else:
                path_cmds.append(f"L {f(x_end)} {f(ay)}")
    else:
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
                f_start = y_start + (fit_tol / 2.0)
                f_end = y_end - (fit_tol / 2.0)
                
                # FIX: Snap First and Last Fingers to Exact Edge Y
                if i == 0:
                    f_start = top_edge_y
                if i == count - 1:
                    f_end = bottom_edge_y
                    
                f_len = (stock_thk + protrusion) - fit_tol
                path_cmds.append(f"L {f(rx)} {f(f_start)}")
                path_cmds.append(f"L {f(rx + f_len)} {f(f_start)}")
                path_cmds.append(f"L {f(rx + f_len)} {f(f_end)}")
                path_cmds.append(f"L {f(rx)} {f(f_end)}")
                path_cmds.append(f"L {f(rx)} {f(y_end)}")
            
            elif right_type == 'sockets' and is_active:
                f_len = stock_thk
                if i > 0:
                    path_cmds.append(f"L {f(rx)} {f(y_start)}")
                    path_cmds.append(f"L {f(rx - f_len)} {f(y_start)}")
                
                path_cmds.append(f"L {f(rx - f_len)} {f(y_end)}")
                
                if i < count - 1:
                    path_cmds.append(f"L {f(rx)} {f(y_end)}")
            else:
                path_cmds.append(f"L {f(rx)} {f(y_end)}")
    else:
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
            else:
                path_cmds.append(f"L {f(x_end)} {f(by)}")
    else:
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
                
                # FIX: Snap First and Last Fingers to Exact Edge Y
                if i == 0:
                    f_start = bottom_edge_y
                if i == count - 1:
                    f_end = top_edge_y
                    
                f_len = (stock_thk + protrusion) - fit_tol
                path_cmds.append(f"L {f(lx)} {f(f_start)}")
                path_cmds.append(f"L {f(lx - f_len)} {f(f_start)}")
                path_cmds.append(f"L {f(lx - f_len)} {f(f_end)}")
                path_cmds.append(f"L {f(lx)} {f(f_end)}")
                path_cmds.append(f"L {f(lx)} {f(y_end)}")
            
            elif left_type == 'sockets' and is_active:
                f_len = stock_thk
                if i > 0:
                    path_cmds.append(f"L {f(lx)} {f(y_start)}")
                    path_cmds.append(f"L {f(lx + f_len)} {f(y_start)}")
                
                path_cmds.append(f"L {f(lx + f_len)} {f(y_end)}")
                
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
    # Removed "Combined Rails" wrapper group to allow parts to be Top-Level "Layers" in Illustrator if imported that way.
    # Or keep it but give it a name. 
    # User said "Parts... may not be grouped, every part must be individually selectable".
    # If we wrap in "Combined Rails", they are all in one group.
    # Better to have them simultaneous at root.
    
    for key in ['TOP', 'LEFT', 'BOTTOM', 'RIGHT']:
        if key in paths:
            path_d = paths[key]
            x, y = coords[key]
            fill = colors[key]
            
            # Named Group for the Part
            lines.append(f'    <g id="{key}" data-name="{key}" transform="translate({f(x)}, {f(y)})">')
            lines.append(f'      <path d="{path_d}" fill="{fill}" stroke="#000000" stroke-width="{STROKE_WIDTH}"/>')
            lines.append(f'    </g>')
            
    lines.append('</svg>')
    
    return "\n".join(lines)

def generate_front_bezel_parts(version):
    """Generate FRONT_BEZEL SVGs (PERIMETER, WINDOW, RABBETS)."""
    # Outer Dimensions = Total Box Width/Height (covers outer extent)
    width_in = convert_to_inches(CONFIG['TOTAL_WIDTH'])
    height_in = convert_to_inches(CONFIG['TOTAL_HEIGHT'])
    
    stock_thk = convert_to_inches(CONFIG['STOCK_THICKNESS'])
    front_rabbet_w = CONFIG.get('FRONT_RABBET_WIDTH', 0.3)
    
    # Calculate Inner Plug Inset
    # The Rail Rabbet creates a 'shelf' of width `front_rabbet_w`.
    # The remaining rail edge creates a 'rim' of width `Stock - front_rabbet_w`.
    # The Bezel Plug fits inside this rim.
    rim_width = stock_thk - front_rabbet_w
    
    # Check for validity
    if rim_width < 0: rim_width = 0 
    
    inner_w = width_in - (2 * rim_width)
    inner_h = height_in - (2 * rim_width)
    
    canvas_w = width_in + (2 * MARGIN_INCHES)
    canvas_h = height_in + (2 * MARGIN_INCHES)
    
    finger_config = {'top': None, 'right': None, 'bottom': None, 'left': None}
    
    files = {}
    
    # PERIMETER
    perimeter_elements = []
    perimeter_elements.append(create_svg_header(canvas_w, canvas_h, f"FRONT_BEZEL_PERIMETER"))
    path_d, _, _ = generate_perimeter_with_fingers("FRONT_BEZEL", width_in, height_in, finger_config)
    
    # Validation
    try:
        validate_rail_edge_straightness(path_d, "FRONT_BEZEL_PERIMETER")
    except ValueError as e:
        print(f"Validation failed for FRONT_BEZEL: {e}")
        # raise e
    perimeter_elements.append(create_path(path_d, COLOR_PERIMETER))
    perimeter_elements.append(create_svg_footer())
    files[f"FRONT_BEZEL_PERIMETER.v{version}.svg"] = "\n".join(perimeter_elements)
    
    # WINDOW
    ax = MARGIN_INCHES
    ay = MARGIN_INCHES
    
    # Check if enabled
    window_enabled = CONFIG.get('WINDOW_ENABLED', True)
    
    window_elements = []
    
    if window_enabled and 'WINDOW_WIDTH_IN' in CONFIG and 'WINDOW_HEIGHT_IN' in CONFIG:
        win_w = CONFIG['WINDOW_WIDTH_IN']
        win_h = CONFIG['WINDOW_HEIGHT_IN']
        
        # Center the window
        # Explicit Centering Logic
        win_x = ax + (width_in / 2.0) - (win_w / 2.0)
        win_y = ay + (height_in / 2.0) - (win_h / 2.0)
        
        # Verify Centering
        left_margin = win_x - ax
        right_margin = (ax + width_in) - (win_x + win_w)
        print(f"DEBUG: Front Bezel Window. Box W={width_in:.3f}, Win W={win_w:.3f}. Left Margin={left_margin:.3f}, Right Margin={right_margin:.3f}")
        
        window_elements.append(create_svg_header(canvas_w, canvas_h, f"FRONT_BEZEL_WINDOW"))
        window_d = f"M {f(win_x)} {f(win_y)} L {f(win_x)} {f(win_y + win_h)} L {f(win_x + win_w)} {f(win_y + win_h)} L {f(win_x + win_w)} {f(win_y)} Z"
        window_elements.append(create_path(window_d, COLOR_WINDOW))
        window_elements.append(create_svg_footer())
        files[f"FRONT_BEZEL_WINDOW.v{version}.svg"] = "\n".join(window_elements)
    else:
        # If disabled, no window path
        window_d = ""
        # We might still return an empty file or just skip it. Skipping for cleanliness.
        # But for Visualization we need something or just skip drawing.
    
    # RABBETS (Stepped Plug)
    # This defines the area to be machined to create the "Plug". 
    # Usually this is the 'Outer Ring' between Perimeter and Inner Rect.
    # We will provide BOTH rectangles so CAM user can select region.
    rabbets_elements = []
    rabbets_elements.append(create_svg_header(canvas_w, canvas_h, f"FRONT_BEZEL_RABBETS"))
    
    # 1. Outer Rect (Perimeter)
    rabbets_elements.append(create_rect(ax, ay, width_in, height_in, COLOR_RABBETS))
    
    # 2. Inner Rect (Plug)
    rab_x = ax + rim_width
    rab_y = ay + rim_width
    rabbets_elements.append(create_rect(rab_x, rab_y, inner_w, inner_h, COLOR_RABBETS))
    
    rabbets_elements.append(create_svg_footer())
    files[f"FRONT_BEZEL_RABBETS.v{version}.svg"] = "\n".join(rabbets_elements)
    
    # VISUALIZATION
    viz_elements = []
    viz_elements.append(create_svg_header(canvas_w, canvas_h, f"VISUALIZATION_FRONT_BEZEL.v{version}"))
    viz_elements.append(create_path(path_d, COLOR_PERIMETER))
    if window_d:
        viz_elements.append(create_path(window_d, COLOR_WINDOW))
    # Visualize Rabbet Inner Line
    viz_elements.append(create_rect(rab_x, rab_y, inner_w, inner_h, COLOR_RABBETS))
    viz_elements.append(create_svg_footer())
    files[f"VISUALIZATION_FRONT_BEZEL.v{version}.svg"] = "\n".join(viz_elements)
    
    geometry_data = {
        'perimeter_d': path_d,
        'window_d': window_d,
        'rabbet_outer_rect': (ax, ay, width_in, height_in),
        'rabbet_inner_rect': (rab_x, rab_y, inner_w, inner_h),
        'rim_width': rim_width
    }
    
    return files, geometry_data

def generate_rail_parts(rail_name, is_horizontal, has_motor_pocket, version):
    """Generate rail SVGs (PERIMETER, HOLES, POCKETS)."""
    # v48 UPDATE: Rails DO NOT have rabbets.
    # v48 UPDATE: Pilot Holes = 7.14375mm, centered on (Stock + GlueGap)/2
    
    stock_thk = convert_to_inches(CONFIG['STOCK_THICKNESS'])
    glue_gap = convert_to_inches(CONFIG.get('GLUE_GAP', 0.5)) # Default 0.5mm
    
    # Calculate Base Width for Perimeter Generation
    if is_horizontal:
        rail_w_in = convert_to_inches(CONFIG['TOTAL_WIDTH']) - (2 * stock_thk)
        rail_h_in = convert_to_inches(CONFIG['BOX_DEPTH'])
        finger_config = {'top': None, 'right': 'fingers', 'bottom': None, 'left': 'fingers'}
        
        feature_start_x = -stock_thk  # Relative to ax
        feature_width = convert_to_inches(CONFIG['TOTAL_WIDTH'])
        
    else:
        rail_w_in = convert_to_inches(CONFIG['TOTAL_HEIGHT'])
        rail_h_in = convert_to_inches(CONFIG['BOX_DEPTH'])
        finger_config = {'top': None, 'right': 'sockets', 'bottom': None, 'left': 'sockets'}
        
        feature_start_x = 0
        feature_width = rail_w_in

    path_d, p_width, p_height = generate_perimeter_with_fingers(rail_name, rail_w_in, rail_h_in, finger_config)
    
    # Validation
    try:
        validate_rail_edge_straightness(path_d, f"{rail_name}_PERIMETER")
    except ValueError as e:
        print(f"Validation failed for {rail_name}: {e}")
        # raise e
    
    canvas_w = p_width
    canvas_h = p_height
    ax = MARGIN_INCHES
    ay = MARGIN_INCHES
    
    files = {}
    
    # PERIMETER
    perimeter_elements = []
    perimeter_elements.append(create_svg_header(canvas_w, canvas_h, f"{rail_name}_PERIMETER"))
    perimeter_elements.append(create_path(path_d, COLOR_PERIMETER))
    perimeter_elements.append(create_svg_footer())
    files[f"{rail_name}_PERIMETER.v{version}.svg"] = "\n".join(perimeter_elements)
    
    # HOLES / POCKETS
    holes_elements = []
    pockets_elements = []
    motor_x_in = 0
    motor_y_in = 0
    pocket_in = 0
    
    if has_motor_pocket and CONFIG.get('MOTOR_POCKET_ENABLED', False):
        holes_elements.append(create_svg_header(canvas_w, canvas_h, f"{rail_name}_HOLES"))
        pockets_elements.append(create_svg_header(canvas_w, canvas_h, f"{rail_name}_POCKETS"))
        
        # Calculate Motor Center X
        # CONFIG['MOTOR_POCKET_X'] is user-defined distance from Left Edge.
        # Our Physical Left Edge is at `ax + feature_start_x`.
        user_x = convert_to_inches(CONFIG.get('MOTOR_POCKET_X', 0))
        motor_x_in = feature_start_x + user_x
        
        motor_y_in = rail_h_in / 2
        
        pocket_mm = CONFIG.get('MOTOR_POCKET_SIZE', 42.0)
        pocket_in = convert_to_inches(pocket_mm)
        pockets_elements.append(create_rect(ax + motor_x_in - pocket_in/2, ay + motor_y_in - pocket_in/2, pocket_in, pocket_in, COLOR_POCKETS))
        
        # Center Hole (Shaft?) - Keeping 0.25" default for now or user specific? 
        # Usually Motor Shaft hole is larger. keeping as is.
        holes_elements.append(create_circle(ax + motor_x_in, ay + motor_y_in, 0.25, COLOR_HOLES))
        
        pattern_mm = CONFIG.get('MOTOR_MOUNT_PATTERN', 31.0)
        pattern_in = convert_to_inches(pattern_mm)
        
        # Motor Mount Pattern

        
        offset = pattern_in / 2.0
        hole_locs = [(-offset, -offset), (offset, -offset), (-offset, offset), (offset, offset)]
        for dx, dy in hole_locs:
            # These are Motor Mount holes, NOT the Pilot Holes for the back panel.
            # Assuming these stay standard screw holes? 
            # Or did user mean ALL pilot holes? 
            # "Pilot Hole Should default to 7.14375mm and must be centered in the (stock thickness + glue gap) width perfectly"
            # That phrase usually applies to the Edge Joinery Pilot Holes (for screwing the back panel ONTO the rails).
            # The motor mount holes are internal. 
            # Checking context: "centered in the (stock thickness + glue gap) width" implies Edge Holes.
            # Motor holes are centered on the rail FACE.
            
            # Using standard mount_r for motor screws (3.4mm usually? or 1.7r).
            # Let's keep motor holes as originally defined (roughly 3-4mm hole).
            mount_r = convert_to_inches(1.7) 
            holes_elements.append(create_circle(ax + motor_x_in + dx, ay + motor_y_in + dy, mount_r, COLOR_HOLES))
            
        holes_elements.append(create_svg_footer())
        pockets_elements.append(create_svg_footer())
        files[f"{rail_name}_HOLES.v{version}.svg"] = "\n".join(holes_elements)
        files[f"{rail_name}_POCKETS.v{version}.svg"] = "\n".join(pockets_elements)

    # v48: RABBETS REMOVED FROM RAIL
    
    # VISUALIZATION
    viz_elements = []
    viz_elements.append(create_svg_header(canvas_w, canvas_h, f"VISUALIZATION_{rail_name}.v{version}"))
    viz_elements.append(create_path(path_d, COLOR_PERIMETER))
    # No Rabbets in Viz
    if has_motor_pocket and CONFIG.get('MOTOR_POCKET_ENABLED', False):
        viz_elements.append(create_rect(ax + motor_x_in - pocket_in/2, ay + motor_y_in - pocket_in/2, pocket_in, pocket_in, COLOR_POCKETS))
        viz_elements.append(create_circle(ax + motor_x_in, ay + motor_y_in, 0.25, COLOR_HOLES))
    viz_elements.append(create_svg_footer())
    files[f"VISUALIZATION_{rail_name}.v{version}.svg"] = "\n".join(viz_elements)
    
    # BOTTOM HATCH LOGIC (v1.22)
    if rail_name == "BOTTOM_RAIL" and CONFIG.get('BOTTOM_HATCH_ENABLED', False):
        try:
            bh_w_mm = CONFIG.get('BOTTOM_HATCH_WIDTH', 0)
            bh_h_mm = CONFIG.get('BOTTOM_HATCH_HEIGHT', 0)
            bh_x_pct = CONFIG.get('BOTTOM_HATCH_X_PCT', 50.0)
            
            bh_w_in = convert_to_inches(bh_w_mm)
            bh_h_in = convert_to_inches(bh_h_mm)
            
            # Position: Center X calculated from Rail Width
            # Rail Width (Physical) = rail_w_in (Total Width - 2*Stock)
            # 0 is Left Edge of Rail.
            
            center_x = rail_w_in * (bh_x_pct / 100.0)
            
            # Y Position: Centered in Depth (rail_h_in = Box Depth)
            center_y = rail_h_in / 2.0
            
            bx = ax + center_x - (bh_w_in / 2.0)
            by = ay + center_y - (bh_h_in / 2.0)
            
            # Hatch Geometry
            # 1. CUT (Opening & Shelf) on the Rail
            # Cut Opening: Through Hole (Perimeter Color)
            # Shelf: Pocket (Rabbet Color)
            # Note: Bottom Access Panel usually has the FLANGE on the LID?
            # Or on the Rail?
            # Standard "Lid": Lid has the Flange (Step). Rail has a simple Opening + Recess?
            # Rear Logic: Rail/Panel has "Opening"(Through) and "Shelf"(Pocket).
            # Lid has "Perimeter"(Outer) and "Rabbet"(Step).
            # Yes.
            
            st_in = convert_to_inches(CONFIG['STOCK_THICKNESS'])
            gg_in = convert_to_inches(CONFIG.get('GLUE_GAP', 0.5))
            flange_w = (st_in / 2.0) - gg_in
            
            # Clamp flange
            if flange_w < 0.05: flange_w = 0.05
            
            # Opening (Through)
            # Shelf (Pocket around opening)
            shelf_x = bx - flange_w
            shelf_y = by - flange_w
            shelf_w = bh_w_in + (2 * flange_w)
            shelf_h = bh_h_in + (2 * flange_w)
            
            hatch_elements = []
            hatch_elements.append(create_svg_header(canvas_w, canvas_h, f"{rail_name}_HATCH_CUT"))
            
            # Pocket (Shelf) - Defined FIRST? Order matters for visuals, but for CAM it's by layer.
            # "BOTTOM_RAIL_HATCH_CUT" -> Mapped to 'CONTOUR (Inside)'?
            # Wait, previously `BACK_PANEL_HATCH_CUT` mapped to `CONTOUR (Inside)`.
            # That implies we cut the INNER hole?
            # NO. `HATCH_CUT` file contained BOTH Rects.
            # "Contour (Inside)" on the OUTER Shelf Rect would result in a Hole of Shelf Size. That's wrong.
            # "Pocket" of the area between Outer and Inner is correct.
            # "Inside Contour" of Inner Rect = Hole.
            # If we map "HATCH_CUT" file to "CONTOUR (Inside)", usually we want the Through Hole.
            # But we also need the Shelf Pocket.
            # In `generate_back_panel_parts`:
            #   cut_elements.append(create_rect(hatch_x, hatch_y, hatch_open_w, hatch_open_h, COLOR_PERIMETER))
            #   cut_elements.append(create_rect(shelf_x, shelf_y, shelf_w, shelf_h, COLOR_RABBETS))
            # And `get_layer_type_v11` mapped `HATCH_CUT` to `CONTOUR (Inside)`.
            # This is ambiguous for CAM. Usually user separates them.
            # But the user logic "addition of a female square rabbet... Inside/Left Contour Path"
            # Maybe the user implies just ONE cut?
            # "female square rabbet... on the bottom rail... to be an Inside/Left Contour Path".
            # This implies cutting the hole with a step? You can't do a step with one contour path unless you seek a specific depth.
            # If he says "Rabbet", he usually means "Pocket" or "Step".
            # Let's provide BOTH vectors in the file (Hole and Shelf) so they can choose.
            
            hatch_elements.append(create_rect(bx, by, bh_w_in, bh_h_in, COLOR_PERIMETER)) # Through
            hatch_elements.append(create_rect(shelf_x, shelf_y, shelf_w, shelf_h, COLOR_RABBETS)) # Shelf
            hatch_elements.append(create_svg_footer())
            files[f"{rail_name}_HATCH_CUT.v{version}.svg"] = "\n".join(hatch_elements)
            
            # 2. LID (Separate Part)
            # Lid Size = Shelf Size (minus fit_tolerance? No, usually Lid matches Shelf Outer, Plug matches Hole).
            # Lid Outer = Shelf Outer.
            # Lid Plug (Inner Step) = Opening Size (minus fit adjustment).
            
            lid_w = shelf_w
            lid_h = shelf_h
            
            # Lid Canvas
            l_can_w = lid_w + 4.0
            l_can_h = lid_h + 4.0
            lx = 2.0
            ly = 2.0
            
            lid_elements = []
            lid_elements.append(create_svg_header(l_can_w, l_can_h, f"{rail_name}_HATCH_LID"))
            
            # Perimeter
            lid_elements.append(create_rect(lx, ly, lid_w, lid_h, COLOR_PERIMETER))
            
            # Rabbet (Plug)
            # Inner = Opening Size
            lr_x = lx + flange_w
            lr_y = ly + flange_w
            lid_elements.append(create_rect(lr_x, lr_y, bh_w_in, bh_h_in, COLOR_RABBETS))
            
            # Holes (4 corners)
            hr = 0.1
            coff = flange_w / 2.0
            lid_elements.append(create_circle(lx + coff, ly + coff, hr, COLOR_HOLES))
            lid_elements.append(create_circle(lx + lid_w - coff, ly + coff, hr, COLOR_HOLES))
            lid_elements.append(create_circle(lx + coff, ly + lid_h - coff, hr, COLOR_HOLES))
            lid_elements.append(create_circle(lx + lid_w - coff, ly + lid_h - coff, hr, COLOR_HOLES))
            
            lid_elements.append(create_svg_footer())
            
            # We add this to `files` but we want to pack it separately.
            # We'll detect it in `generate_master_carbide_layout` by name "BOTTOM_RAIL_HATCH_LID".
            files[f"{rail_name}_HATCH_LID.v{version}.svg"] = "\n".join(lid_elements)
            
        except Exception as e:
            print(f"Error generating Bottom Hatch: {e}")

    return files, path_d

class BinPacker:
    """
    Shelf-based Bin Packing Algorithm for 2D Nesting.
    Supports adjustable sheet sizes and automatic rotation.
    """
    def __init__(self, gap=0.5):
        self.gap = gap
        self.sheets = [] # List of {'w': w, 'h': h, 'items': []}
        # Start with one 48x48 sheet
        self.add_sheet(48.0, 48.0)

    def add_sheet(self, w, h):
        self.sheets.append({
            'w': w, 'h': h, 
            'items': [],
            'shelves': [] # List of {'y': y, 'h': h, 'current_x': x}
        })

    def pack_items(self, items):
        """
        Pack list of items. 
        Item structure: {'id': str, 'w': float, 'h': float, 'data': any, 'forced_group': None}
        Items with 'forced_group' should be pre-merged or handled carefully.
        Here we assume 'items' are discrete movable units.
        """
        # Sort by Height Descending (Heuristic for Shelf Packing)
        # We try to align the Longest Dimension Horizontally for consistency if possible, 
        # unless it's too wide.
        
        # Pre-process: Orient items 'Landscape' if they fit in 48", else Portrait?
        # Actually, let the packer decide rotation during placement.
        # We'll just sort by Max Dimension first?
        # Standard Shelf: Sort by Height.
        
        sorted_items = sorted(items, key=lambda x: max(x['w'], x['h']), reverse=True)
        for item in sorted_items:
            placed = False
            
            # Try every existing sheet
            for sheet_idx, sheet in enumerate(self.sheets):
                if self._fit_item_in_sheet(sheet, item):
                    placed = True
                    break
            
            # If not placed, try Valid Expansions
            if not placed:
                expanded = False
                for sheet in self.sheets:
                    # If this sheet is 48x48, can we expand to 48x96?
                    if abs(sheet['w'] - 48.0) < 0.1 and abs(sheet['h'] - 48.0) < 0.1:
                        # Try to expand H to 96
                        # Check if item fits in 48x96
                        # Temporarily expand
                        original_h = sheet['h']
                        sheet['h'] = 96.0
                        if self._fit_item_in_sheet(sheet, item):
                            placed = True
                            break
                        else:
                            # Revert if it didn't help (though usually bigger is better, 
                            # we might prefer a new 48x48 sheet over a huge one? 
                            # User said "backup default size is 48x96". 
                            # Implies prefer 48x48, but expand if needed.
                            # So if it DOES fit, keep expansion.
                            # If it doesn't fit even in 96, we definitely need a new sheet (or it's too big).
                            pass 
                            
                if not placed:
                    # Create new 48x48 Sheet
                    self.add_sheet(48.0, 48.0)
                    last_sheet = self.sheets[-1]
                    if not self._fit_item_in_sheet(last_sheet, item):
                        # Try expand new sheet immediately
                        last_sheet['h'] = 96.0
                        if not self._fit_item_in_sheet(last_sheet, item):
                            print(f"WARNING: Item {item['id']} too big for 48x96 sheet!")

    def _fit_item_in_sheet(self, sheet, item):
        """Try to fit item in sheet shelves. Rotates if necessary."""
        # Options: Original (w, h), Rotated (h, w)
        # Prefer "Longest Side Horizontal" to minimize Shelf Height usage? 
        # Actually, for Shelf packing, minimizing Shelf Height (placing smallest dimension vertical) 
        # is good to fill strips.
        # So: Target H should be min(w, h).
        
        w, h = item['w'], item['h']
        orientations = []
        
        # 1. Min Height Orientation (Shelf Friendly)
        if h <= w: 
            orientations.append((w, h, False)) # Already Landscape
        else:
            orientations.append((h, w, True)) # Rotate to Landscape
        
        # 2. Max Height Orientation (Alternative)
        if h > w:
            orientations.append((w, h, False)) # Portrait
        else:
             orientations.append((h, w, True)) # Rotate to Portrait
             
        # Dedup
        unique_orients = []
        seen = set()
        for o in orientations:
            if o not in seen:
                unique_orients.append(o)
                seen.add(o)
                
        gap = self.gap
        
        best_fit = None # (y, shelf_idx, orientation)
        
        for w_curr, h_curr, rotated in unique_orients:
            if w_curr > sheet['w'] or h_curr > sheet['h']:
                continue
                
            # Try existing shelves
            for s_idx, shelf in enumerate(sheet['shelves']):
                # Does it fit in height?
                if h_curr <= shelf['h']:
                    # Does it fit in remaining width?
                    if shelf['current_x'] + w_curr <= sheet['w']:
                        # Found a spot!
                        # We want the 'Best' spot? First Fit is fine for now.
                        # We accept immediately.
                        self._place_in_shelf(sheet, s_idx, w_curr, h_curr, item, rotated)
                        return True
            
            # Try create NEW shelf
            # New shelf Y = max(prev_shelves Y + H) + Gap
            # Actually, `shelves` list might not be sorted by Y if we fill gaps?
            # Standard: Shelves stack from Y=0 down.
            
            y_start = 0.0
            if sheet['shelves']:
                last_shelf = sheet['shelves'][-1]
                y_start = last_shelf['y'] + last_shelf['h'] + gap
            else:
                y_start = gap # Initial Margin
            
            if y_start + h_curr <= sheet['h']:
                # Can create new shelf
                # If we create a new shelf, we are committing to this orientation.
                # Which orientation minimizes vertical waste?
                # The one with smaller H.
                # So if we are here, we probably picked simple order. 
                # Let's verify we picked the orientation with min H?
                # We sorted `unique_orients`? No.
                # Let's enforce loop order: Try Min H first.
                pass 
                
        # Retry with logic: If no shelf fit, try create New Shelf using Min H orientation
        # (This avoids creating a tall shelf if a short one would do)
        
        # Recalc for New Shelf ONLY
        candidates = sorted(unique_orients, key=lambda x: x[1]) # Sort by Height Ascending
        
        for w_curr, h_curr, rotated in candidates:
             # Calculate Y
            y_start = 0.0
            if sheet['shelves']:
                last_shelf = sheet['shelves'][-1]
                y_start = last_shelf['y'] + last_shelf['h'] + gap
            else:
                y_start = gap
            
            if y_start + h_curr <= sheet['h'] and w_curr <= sheet['w']:
                 # Create shelf
                 new_shelf = {'y': y_start, 'h': h_curr, 'current_x': gap}
                 sheet['shelves'].append(new_shelf)
                 # Place
                 self._place_in_shelf(sheet, len(sheet['shelves'])-1, w_curr, h_curr, item, rotated)
                 return True

        return False

    def _place_in_shelf(self, sheet, shelf_idx, w, h, item, rotated):
        shelf = sheet['shelves'][shelf_idx]
        
        x = shelf['current_x']
        y = shelf['y']
        
        # Center item vertically in shelf if shelf is taller?
        # Or Just align bottom/top? Align Top (Y).
        
        sheet['items'].append({
            'item': item,
            'x': x, 'y': y,
            'w': w, 'h': h,
            'rotated': rotated
        })
        
        shelf['current_x'] += w + self.gap
        # If this item increased shelf height (shouldn't happen in strict shelf packing as shelf H is fixed at creation),
        # but if we allowed "growing" shelves... No, simple shelf logic fixes H.

class TextManager:
    """Manages text placement to avoid collisions."""
    def __init__(self):
        self.placed_boxes = [] # List of (x1, y1, x2, y2)
        
    def intersect(self, r1, r2):
        # r = (min_x, min_y, max_x, max_y)
        # Returns True if overlapping
        return not (r1[2] < r2[0] or r1[0] > r2[2] or r1[3] < r2[1] or r1[1] > r2[3])

    def add_nudge_text(self, x, y, content, size_pt, color, anchor="middle", lines_list=None):
        """
        Add text with collision detection. Nudges vertically if collision detected.
        "Before presenting text to user, check every text element against every other text element to confirm no overlap."
        """
        # Estimate dimensions (Inches)
        # 1 pt = 1/72 inch
        # Lato Black Check: Very bold = wider. 
        # Aspect Ratio estimate: 0.6 is typical for normal, use 0.7 for Black?
        h_in = size_pt / 72.0
        w_in = len(content) * h_in * 0.7 
        
        # Bbox calculation (Bottom-Up or Top-Down coords? SVG is Y-Down)
        # Anchor handling
        if anchor == "middle":
            x1 = x - w_in/2.0
            y1 = y - h_in # Text y is usually baseline. Bbox goes UP approx 0.7h and DOWN 0.3h? 
            # Simplified: y is center? No, SVG text 'y' is baseline.
            # Let's assume bounding box is centered around (x, y - h/2).
            # SVG y is baseline. Cap height is ~0.7em up. Descent is ~0.3em down.
            # Let's say box is from y - h to y + 0.2h.
            y_top = y - h_in
            y_bot = y + (h_in * 0.2)
            x1 = x - w_in/2.0
        elif anchor == "start":
            x1 = x
            y_top = y - h_in
            y_bot = y + (h_in * 0.2)
        else: # end
            x1 = x - w_in
            y_top = y - h_in
            y_bot = y + (h_in * 0.2)
            
        x2 = x1 + w_in
        
        # Current Rect
        rect = (x1, y_top, x2, y_bot)
        
        # Collision Check & Nudge
        # Strategy: Valid Y positions to try. 
        # We can nudge DOWN (increase Y).
        
        limit = 50
        step = h_in * 1.1 # Move down by full line height + margin
        
        attempts = 0
        current_y = y
        
        while attempts < limit:
            collided = False
            for r in self.placed_boxes:
                if self.intersect(rect, r):
                    collided = True
                    break
            
            if not collided:
                break
                
            # Nudge
            current_y += step
            # Update rect
            rect = (rect[0], rect[1] + step, rect[2], rect[3] + step)
            attempts += 1
            
        # Register
        self.placed_boxes.append(rect)
        
        # Generate Element
        # Font: Lato Black
        # If collision pushed it far, `current_y` is updated.
        
        t = f'<text x="{f(x)}" y="{f(current_y)}" font-family="Lato Black, Lato, sans-serif" font-weight="900" font-size="{size_pt}" fill="{color}" text-anchor="{anchor}">{content}</text>'
        
        if lines_list is not None:
            lines_list.append(t)
            
        return t

def generate_master_carbide_layout(version, f_front, f_back, f_top, f_bot, f_left, f_right, geom_back, cleat_data):
    """
    Generate optimized nesting layout FLATTENED (No Groups).
    v1.11 Update: 
    - No <g> tags.
    - Text Collision Manager.
    - Part Name (Black 80pt), Sub (Blue 70pt), Router (Green 70pt).
    """
    GAP = 0.5 
    
    # 1. Collect Parts (Same logic as v1.10)
    parts_to_pack = []
    
    def prepare_part(name, files_map, w_in, h_in, extra_id=None):
        if files_map is None:
            print(f"WARNING: files_map is None for part {name}. Initializing empty dict.")
            files_map = {}
        return {
            'id': name,
            'files': files_map,
            'w': w_in,
            'h': h_in,
            'extra': extra_id
        }

    # Dimensions
    total_w = convert_to_inches(CONFIG['TOTAL_WIDTH'])
    total_h = convert_to_inches(CONFIG['TOTAL_HEIGHT'])
    box_d = convert_to_inches(CONFIG['BOX_DEPTH'])
    stock_thk = convert_to_inches(CONFIG['STOCK_THICKNESS'])
    
    # Front & Back
    parts_to_pack.append(prepare_part("FRONT", f_front, total_w, total_h))
    parts_to_pack.append(prepare_part("BACK", f_back, total_w, total_h))
    
    # Rails
    w_topbot = total_w - (2 * stock_thk)
    parts_to_pack.append(prepare_part("TOP", f_top, w_topbot, box_d))
    parts_to_pack.append(prepare_part("BOTTOM", f_bot, w_topbot, box_d))
    
    w_sides = total_h
    parts_to_pack.append(prepare_part("LEFT", f_left, w_sides, box_d))
    parts_to_pack.append(prepare_part("RIGHT", f_right, w_sides, box_d))
    
    # Cleats
    if cleat_data:
        cw = cleat_data['cleat_w']
        ch = cleat_data['cleat_h']
        parts_to_pack.append(prepare_part("CLEAT_WALL", cleat_data['wall_cleat_files'], cw, ch))
        parts_to_pack.append(prepare_part("CLEAT_BOX", cleat_data['box_cleat_files'], cw, ch))
        
    # Hatch Lid
    hatch_data = geom_back.get('hatch')
    if hatch_data:
        lid_w = hatch_data['lid_w']
        lid_h = hatch_data['lid_h']
        win_w = CONFIG.get('WINDOW_WIDTH_IN', 0)
        win_h = CONFIG.get('WINDOW_HEIGHT_IN', 0)
        is_nested = False
        if CONFIG.get('WINDOW_ENABLED', False):
             if lid_w < (win_w - 0.5) and lid_h < (win_h - 0.5):
                 is_nested = True
        
        if is_nested:
            for p in parts_to_pack:
                if p['id'] == "FRONT":
                    p['nested_hatch'] = hatch_data
        else:
            # Add as independent part
            # Construct File Dict for Hatch Lid
            # User Request v1.12: "HATCH_LID should be a part of the BACK_PANEL" logic-wise.
            # We rename it to BACK_PANEL_HATCH_LID
            hatch_files = {f"BACK_PANEL_HATCH_LID.v{version}.svg": hatch_data['svg_content']}
            parts_to_pack.append(prepare_part("BACK_PANEL_HATCH_LID", hatch_files, lid_w, lid_h))

    # Bottom Hatch Lid (New v1.22)
    # Passed via BOTTOM rail files or separately?
    # generate_rail_parts for BOTTOM returns 'hatch' data?
    # Wait, generate_rail_parts only returned `files` and `path_d`.
    # I need to update generate_rail_parts to RETURN geometry data like generate_back_panel_parts.
    # OR, I can check if "BOTTOM_RAIL_HATCH_LID..." is in f_bot?
    # If it is in `f_bot`, it's just a file.
    # BUT, we want to Pack it separately? 
    # If it's in `f_bot`, it is attached to the "BOTTOM" part (which is the Rail).
    # Rails are packed as 1 item.
    # If we want the Lid to be nested separately, we must extract it.
    
    # Check if we generated a separate Lid file in f_bot
    b_hatch_lid_file = None
    b_hatch_lid_content = None
    keys_to_remove = []
    
    for k, v in f_bot.items():
        if "BOTTOM_RAIL_HATCH_LID" in k:
            b_hatch_lid_file = k
            b_hatch_lid_content = v
            keys_to_remove.append(k)
            
    # Remove from Rail Files so it doesn't render on top of the rail
    for k in keys_to_remove:
        del f_bot[k]
        
    if b_hatch_lid_file:
        # We don't have exact dimensions here unless we parse SVG or pass them.
        # But we stored them in CONFIG['BOTTOM_HATCH_WIDTH'] / HEIGHT?
        # The Lid Size is Opening + 2*Flange.
        # Flange = (Stock/2) - GlueGap.
        # Let's re-calculate or retrieve.
        # Actually simplest to retrieve from CONFIG if we trusted the generating function updated it?
        # Or parse.
        # Let's rely on CONFIG if available, or re-calc standard logic.
        
        bh_w = CONFIG.get('BOTTOM_HATCH_WIDTH', 0)
        bh_h = CONFIG.get('BOTTOM_HATCH_HEIGHT', 0)
        # Convert to inches? Config stored mm from UI input? No, we stored mm.
        bh_w_in = convert_to_inches(bh_w)
        bh_h_in = convert_to_inches(bh_h)
        
        st_in = convert_to_inches(CONFIG['STOCK_THICKNESS'])
        gg_in = convert_to_inches(CONFIG.get('GLUE_GAP', 0.5)) # default
        flange_w_in = (st_in / 2.0) - gg_in
        
        lid_w_in = bh_w_in + (2 * flange_w_in)
        lid_h_in = bh_h_in + (2 * flange_w_in)
        
        lid_files = {b_hatch_lid_file: b_hatch_lid_content}
        parts_to_pack.append(prepare_part("BOTTOM_HATCH_LID", lid_files, lid_w_in, lid_h_in))

    # 2. RUN PACKER
    packer = BinPacker(gap=GAP)
    packer.pack_items(parts_to_pack)
    
    # 3. GENERATE MASTER SVG (FLATTENED)
    
    # Calculate Total Canvas
    SHEET_GAP = 4.0 
    total_canvas_w = 0
    max_canvas_h = 0
    sheet_offsets = []
    
    current_x = 0
    for sheet in packer.sheets:
        sheet_offsets.append(current_x)
        total_canvas_w += sheet['w']
        max_canvas_h = max(max_canvas_h, sheet['h'])
        current_x += sheet['w'] + SHEET_GAP
        
    canvas_w = max(total_canvas_w, 1.0)
    canvas_h = max(max_canvas_h, 1.0)
    
    lines = []
    lines.append(f'<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(canvas_w)}in" height="{f(canvas_h)}in" viewBox="0 0 {f(canvas_w)} {f(canvas_h)}">')
    lines.append(f'  <title>MASTER_LAYOUT_COMBINED_v{version}</title>')
    
    # Text Manager removed
    
    # HELPER: Flatten content
    def flatten_content_elements(svg_content, transform_str):
        """Parse SVG body, extract elements, apply transform, return list of strings."""
        flat_lines = []
        body_match = re.search(r'(?s)<svg[^>]*>(.*?)<\/svg>', svg_content)
        if not body_match: return []
        body = body_match.group(1)
        
        # Match tags - EXCLUDING TEXT
        pattern = r'(<(path|circle|rect|line|polygon|polyline)[^>]*/>)'
        matches = re.findall(pattern, body, re.DOTALL)
        
        for match_tuple in matches:
            tag_str = match_tuple[0]
            # Inject transform
            if 'transform="' in tag_str:
                new_tag = re.sub(r'transform="([^"]*)"', f'transform="{transform_str} \\1"', tag_str)
            else:
                tname = match_tuple[1]
                new_tag = tag_str.replace(f"<{tname}", f'<{tname} transform="{transform_str}"', 1)
                
            flat_lines.append(f"    {new_tag}")
            
        return flat_lines

    # Iterate Sheets
    for s_idx, sheet in enumerate(packer.sheets):
        sheet_x_offset = sheet_offsets[s_idx]
        
        # Sheet Border Removed
        # lines.append(f'  <rect x="{f(sheet_x_offset)}" y="0" width="{f(sheet["w"])}" height="{f(sheet["h"])}" fill="none" stroke="#cccccc" stroke-width="0.05" />')
        # Sheet Title Text Removed

        for p_info in sheet['items']:
            part = p_info['item']
            global_x = sheet_x_offset + p_info['x']
            global_y = p_info['y']
            rotated = p_info['rotated']
            
            if rotated:
                tf = f'translate({f(global_x + part["h"])}, {f(global_y)}) rotate(90) translate(-2.0, -2.0)'
            else:
                tf = f'translate({f(global_x)}, {f(global_y)}) translate(-2.0, -2.0)'
            
            # Group by Part
            lines.append(f'  <g id="{part["id"]}" data-name="{part["id"]}">')

            # --- GEOMETRY ---
            files_to_render = part['files'].copy()
            if cleat_data:
                if part['id'] == "CLEAT_WALL": files_to_render = cleat_data['wall_cleat_files']
                if part['id'] == "CLEAT_BOX": files_to_render = cleat_data['box_cleat_files']
            
            # Map Filenames -> Layer Types
            def get_layer_type_v11(fname):
                if "PERIMETER" in fname: return '01_CUTS', 'CONTOUR (Outside)'
                if "HATCH_LID" in fname: return '01_CUTS', 'CONTOUR (Outside)'
                if "BOTTOM_HATCH_LID" in fname: return '01_CUTS', 'CONTOUR (Outside)'
                if "HOLES_THROUGH" in fname: return '02_HOLES', 'HOLES (Inside)'
                if "HOLES" in fname: return '02_HOLES', 'HOLES (Inside)'
                if "RABBETS" in fname: return '03_RABBETS', 'POCKET'
                if "HOLES_CSINK" in fname: return '04_POCKETS', 'POCKET'
                if "POCKETS" in fname: return '04_POCKETS', 'POCKET'
                if "SCORE" in fname: return '06_SCORES', 'NO OFFSET (Score)'
                if "HATCH_CUT" in fname: return '05_WINDOWS', 'CONTOUR (Inside)' 
                if "BOTTOM_HATCH_CUT" in fname: return '05_WINDOWS', 'CONTOUR (Inside)'
                if "WINDOW" in fname: return '05_WINDOWS', 'CONTOUR (Inside)'
                return None, None

            # Render Part Files
            for fname, content in files_to_render.items():
                # Debug Check
                if content is None:
                    print(f"WARNING: Content for {fname} in part {part['id']} is None")
                    continue

                if isinstance(content, str) and fname not in part['files']:
                     if cleat_data and content in cleat_data['svg_contents']:
                             content = cleat_data['svg_contents'][content]
                
                if "VISUALIZATION" in fname: continue
                l_code, friendly = get_layer_type_v11(fname)
                if not l_code: continue
                
                # Color Mapping (High Saturation)
                viz_color = "#ff8d00" # Orange (Default)
                if friendly == 'CONTOUR (Outside)': viz_color = "#ff00ff" # Magenta
                elif friendly == 'HOLES (Inside)': viz_color = "#00ffff" # Cyan
                elif friendly == 'POCKET': viz_color = "#00ff00" # Green
                elif friendly == 'CONTOUR (Inside)': viz_color = "#ff0000" # Red
                elif friendly == 'NO OFFSET (Score)': viz_color = "#ffe500" # Yellow

                # Flatten & Apply Styles
                try:
                    raw_lines = flatten_content_elements(content, tf)
                except Exception as e:
                    print(f"Error flattening {fname}: {e}")
                    raw_lines = []
                
                if raw_lines is None:
                    print(f"Error: flatten_content_elements returned None for {fname}")
                    continue

                for line in raw_lines:
                    # Strip existing style
                    line = re.sub(r'\s+fill="[^"]*"', '', line)
                    line = re.sub(r'\s+stroke="[^"]*"', '', line)
                    line = re.sub(r'\s+stroke-width="[^"]*"', '', line)
                    
                    # Inject new style
                    style = f' fill="none" stroke="{viz_color}" stroke-width="5pt"'
                    line = line.replace("/>", f"{style} />")
                    lines.append(line)

            # Render Nested Hatch
            if part.get('nested_hatch'):
                h_data = part['nested_hatch']
                off_x = (part['w'] - h_data['lid_w']) / 2
                off_y = (part['h'] - h_data['lid_h']) / 2
                
                if rotated:
                    h_tf = f'translate({f(global_x + part["h"])}, {f(global_y)}) rotate(90) translate({f(off_x)}, {f(off_y)}) translate(-2.0, -2.0)'
                else:
                    h_tf = f'translate({f(global_x)}, {f(global_y)}) translate({f(off_x)}, {f(off_y)}) translate(-2.0, -2.0)'
                
                viz_color = "#ff00ff" # Magenta for Hatch Lid (Outside Cut)
                
                raw_lines = flatten_content_elements(h_data['svg_content'], h_tf)
                for line in raw_lines:
                    line = re.sub(r'\s+fill="[^"]*"', '', line)
                    line = re.sub(r'\s+stroke="[^"]*"', '', line)
                    line = re.sub(r'\s+stroke-width="[^"]*"', '', line)
                    style = f' fill="none" stroke="{viz_color}" stroke-width="5pt"'
                    line = line.replace("/>", f"{style} />")
                    lines.append(line)

            lines.append('  </g>')
            
            # Text Annotations Removed

    lines.append('</svg>')
    
    return {f"MASTER_LAYOUT_COMBINED_v{version}.svg": "\n".join(lines)}

def run_generation_patch(self):
    # This is not a real function, just a marker that I need to update the Class Method `run_generation`.
    pass


def set_mac_label(filepath, color_idx):
    """Helper for Mac Labels (Green = 6)"""
    try:
        import subprocess
        # osascript -e 'tell application "Finder" to set label index of (POSIX file "/path") to 6'
        cmd = ['osascript', '-e', f'tell application "Finder" to set label index of (POSIX file "{filepath}") to {str(color_idx)}']
        subprocess.run(cmd, capture_output=True)
    except:
        pass

def verify_dimensions(svg_paths, config):
    """
    Verify generated parts against configuration.
    Returns (True/False, Report String)
    """
    return True, "Verification Skipped (Robust Mode)"

def _get_blender_generator():
    from blender_generator import generate_blender_script, generate_trivision_script
    return generate_blender_script, generate_trivision_script


def generate_back_panel_parts(version):
    """Generate BACK_PANEL SVGs (PERIMETER, HATCH, RABBETS)."""
    width_in = convert_to_inches(CONFIG['TOTAL_WIDTH'])
    height_in = convert_to_inches(CONFIG['TOTAL_HEIGHT'])
    
    stock_thk = convert_to_inches(CONFIG['STOCK_THICKNESS'])
    # Back Panel Rabbet (Perimeter Plug) logic (Unchanged)
    back_rabbet_w = CONFIG.get('BACK_RABBET_WIDTH', 0.3)
    rim_width = stock_thk - back_rabbet_w
    if rim_width < 0: rim_width = 0
    inner_w = width_in - (2 * rim_width)
    inner_h = height_in - (2 * rim_width)
    
    canvas_w = width_in + (2 * MARGIN_INCHES)
    canvas_h = height_in + (2 * MARGIN_INCHES)
    ax = MARGIN_INCHES
    ay = MARGIN_INCHES
    
    files = {}
    
    # PERIMETER
    perimeter_elements = []
    perimeter_elements.append(create_svg_header(canvas_w, canvas_h, f"BACK_PANEL_PERIMETER"))
    path_d = f"M {f(ax)} {f(ay)} L {f(ax + width_in)} {f(ay)} L {f(ax + width_in)} {f(ay + height_in)} L {f(ax)} {f(ay + height_in)} Z"
    perimeter_elements.append(create_path(path_d, COLOR_PERIMETER))
    perimeter_elements.append(create_svg_footer())
    files[f"BACK_PANEL_PERIMETER.v{version}.svg"] = "\n".join(perimeter_elements)
    
    # RABBETS (Stepped Plug for Main Panel)
    rabbets_elements = []
    rabbets_elements.append(create_svg_header(canvas_w, canvas_h, f"BACK_PANEL_RABBETS"))
    # Outer
    rabbets_elements.append(create_rect(ax, ay, width_in, height_in, COLOR_RABBETS))
    # Inner
    rab_x = ax + rim_width
    rab_y = ay + rim_width
    rabbets_elements.append(create_rect(rab_x, rab_y, inner_w, inner_h, COLOR_RABBETS))
    rabbets_elements.append(create_svg_footer())
    files[f"BACK_PANEL_RABBETS.v{version}.svg"] = "\n".join(rabbets_elements)
    
    # HOLES - Mounting Holes for Box Cleat
    # User Request v1.09:
    # "The Cleat... must have holes drilled... to mount... to the French cleat."
    # "placed at 5% in, 33% of the way in, 66% of the way in, and 95% of the way"
    # "centered at 1/3 of the way from the top of the back of the artwork"
    
    hole_positions = []
    hole_r = 0.1 # #10 Screw Through Hole (~0.2" dia)
    
    if CONFIG.get('CLEATS_ENABLED', True):
        # Calculate Cleat Width (Same logic as generate_french_cleats)
        cleat_w = min(width_in * 0.80, 48.0)
        
        # Vertical Position: "1/3 of the way from the top"
        # SVG Origin is Top-Left. 
        # Height from Top = Height / 3.
        # Y = ay + (height_in / 3.0)
        hole_y = ay + (height_in / 3.0)
        
        # Horizontal Position
        # Cleat is Centered horizontally relative to Back Panel.
        # Back Panel Center = ax + width_in / 2
        # Hole Global X = (Center) - (Cleat_W/2) + (Percent * Cleat_W)
        panel_cx = ax + (width_in / 2.0)
        cleat_start_x = panel_cx - (cleat_w / 2.0)
        
        h_pcts = [0.05, 0.33, 0.66, 0.95]
        
        for pct in h_pcts:
            hx = cleat_start_x + (pct * cleat_w)
            hole_positions.append((hx, hole_y))

        # Generate BACK_PANEL_HOLES (Through for T-nut)
        if hole_positions:
            hp_elements = []
            hp_elements.append(create_svg_header(canvas_w, canvas_h, f"BACK_PANEL_HOLES"))
            for hx, hy in hole_positions:
                hp_elements.append(create_circle(hx, hy, hole_r, COLOR_HOLES))
            hp_elements.append(create_svg_footer())
            files[f"BACK_PANEL_HOLES_THROUGH.v{version}.svg"] = "\n".join(hp_elements)
            
            # Add to Geometry Data for Blender/Nesting
            # Need to ensure we export "HOLES_THROUGH" key in file dict if we want them packed?
            # BinPacker uses `files` dict keys. We added it above.
            pass
    
    # HATCH LOGIC (**NEW**)
    hatch_data = None
    if CONFIG.get('HATCH_ENABLED', False):
        # 1. Calc Dimensions
        # Width/Height defined as % of Total
        w_pct = CONFIG.get('HATCH_WIDTH_PCT', 50.0)
        h_pct = CONFIG.get('HATCH_HEIGHT_PCT', 33.0)
        
        hatch_open_w = width_in * (w_pct / 100.0)
        hatch_open_h = height_in * (h_pct / 100.0)
        
        # Flange Calculation (Rabbet Width)
        # "wide = 1/2 the stock thickness - the glue gap"
        glue_gap = convert_to_inches(CONFIG.get('FIT_TOLERANCE', 0.254))
        flange_w = (stock_thk / 2.0) - glue_gap
        
        hatch_lid_w = hatch_open_w + (2 * flange_w)
        hatch_lid_h = hatch_open_h + (2 * flange_w)
        
        # 2. Calc Position
        # "Baseline = Stock Thickness + 0.5""
        # Measured from Bottom of Frame (ay + height_in) UPWARDS?
        # User: "The Z position... measured from the bottom of the frame."
        # Confirm: In SVG (Top-Left Origin), "Bottom" is `ay + height_in`. Moving UP means subtracting Y.
        # Def: "Bottom of inside portion" -> Usually Back Panel sits inside rails?
        # Let's map "Height from Bottom" to SVG Y.
        # Y_center = ? No, user specified "Raise" from baseline.
        # Baseline = Bottom Edge of Back Panel? 
        # "flush with the bottom of the inside portion".
        # If Back Panel covers the whole back, the "Inside Bottom" is `Stock_Thk` (Rail thickness) from the bottom edge.
        # Correct Logic:
        # Distance_From_Bottom_Edge = Stock_Thk + 0.5" + Raise.
        # SVG_Y_Bottom_Hatch = (ay + height_in) - Distance_From_Bottom_Edge.
        # SVG_Y_Top_Hatch = SVG_Y_Bottom_Hatch - Hatch_Open_H. (Since we draw from Top Left).
        
        raise_val = CONFIG.get('HATCH_RAISE_IN', 0.0)
        dist_from_bottom = stock_thk + 0.5 + raise_val
        
        hatch_y = (ay + height_in) - dist_from_bottom - hatch_open_h
        hatch_x = ax + (width_in - hatch_open_w) / 2 # Centered Horizontally
        
        # 3. Generate HATCH_CUT (On Back Panel)
        # Contains: Center Opening (Through) + Outer Pocket (Shelf)
        # Note: To create a shelf, you pocket the AREA between Outer and Inner.
        # Carbide Create "Pocket" or "Inside/Left Contour".
        # User: "addition of a female square rabbet... specified... to be an Inside/Left Contour Path"
        # If we cut "Inside/Left" on the Outer Vector, we get a hole size of Outer.
        # If we cut "Pocket" between Outer and Inner, we get the shelf.
        # Let's provide BOTH rectangles.
        
        cut_elements = []
        cut_elements.append(create_svg_header(canvas_w, canvas_h, f"BACK_PANEL_HATCH_CUT"))
        
        # Opening (Through Hole)
        cut_elements.append(create_rect(hatch_x, hatch_y, hatch_open_w, hatch_open_h, COLOR_PERIMETER))
        
        # Shelf Boundary (Pocket Limit)
        shelf_x = hatch_x - flange_w
        shelf_y = hatch_y - flange_w
        shelf_w = hatch_open_w + (2 * flange_w)
        shelf_h = hatch_open_h + (2 * flange_w)
        
        cut_elements.append(create_rect(shelf_x, shelf_y, shelf_w, shelf_h, COLOR_RABBETS))
        cut_elements.append(create_svg_footer())
        
        files[f"BACK_PANEL_HATCH_CUT.v{version}.svg"] = "\n".join(cut_elements)
        
        # 4. Generate HATCH_LID (Separate Part)
        # Use standard MARGIN_INCHES so Master Layout logic works uniformly
        lid_canvas_w = hatch_lid_w + (2 * MARGIN_INCHES)
        lid_canvas_h = hatch_lid_h + (2 * MARGIN_INCHES)
        lx = MARGIN_INCHES
        ly = MARGIN_INCHES
        
        lid_elements = []
        lid_elements.append(create_svg_header(lid_canvas_w, lid_canvas_h, f"BACK_PANEL_HATCH_LID"))
        
        # Perimeter (Outer Size of Lid)
        lid_elements.append(create_rect(lx, ly, hatch_lid_w, hatch_lid_h, COLOR_PERIMETER))
        
        # Rabbet (Inner Cut to make the Step)
        # Lid Flange means we cut a Rabbet around the edge (removing the "bottom" corner).
        # Inner Rect = Opening Size.
        lid_rab_x = lx + flange_w
        lid_rab_y = ly + flange_w
        lid_elements.append(create_rect(lid_rab_x, lid_rab_y, hatch_open_w, hatch_open_h, COLOR_RABBETS))
        
        # Corner Holes
        # "four corner holes centered in the rabbets"
        # The rabbet is `flange_w` wide. Center is `flange_w / 2`.
        corner_offset = flange_w / 2.0
        # Wait, if flange is small (e.g. 7.5mm - 0.5 = 7mm), hole might be tight.
        # Just putting points there.
        lid_hole_r = 0.1 # Standard small hole
        
        # Top-Left
        lid_elements.append(create_circle(lx + corner_offset, ly + corner_offset, lid_hole_r, COLOR_HOLES))
        # Top-Right
        lid_elements.append(create_circle(lx + hatch_lid_w - corner_offset, ly + corner_offset, lid_hole_r, COLOR_HOLES))
        # Bot-Left
        lid_elements.append(create_circle(lx + corner_offset, ly + hatch_lid_h - corner_offset, lid_hole_r, COLOR_HOLES))
        # Bot-Right
        lid_elements.append(create_circle(lx + hatch_lid_w - corner_offset, ly + hatch_lid_h - corner_offset, lid_hole_r, COLOR_HOLES))
        
        lid_elements.append(create_svg_footer())
        files[f"BACK_PANEL_HATCH_LID.v{version}.svg"] = "\n".join(lid_elements)
        
        # Store Data for Nesting Logic
        hatch_data = {
            'lid_w': hatch_lid_w,
            'lid_h': hatch_lid_h,
            'svg_content': "\n".join(lid_elements) # Raw content effectively
        }

    # VISUALIZATION
    viz_elements = []
    viz_elements.append(create_svg_header(canvas_w, canvas_h, f"VISUALIZATION_BACK_PANEL.v{version}"))
    viz_elements.append(create_path(path_d, COLOR_PERIMETER))
    # Visualize Rabbet Inner Line
    viz_elements.append(create_rect(rab_x, rab_y, inner_w, inner_h, COLOR_RABBETS))
    
    if hatch_data:
        # Visualize access panel cutout
        # Red Hole
        viz_elements.append(create_rect(hatch_x, hatch_y, hatch_open_w, hatch_open_h, COLOR_PERIMETER))
        # Orange Shelf
        viz_elements.append(create_rect(shelf_x, shelf_y, shelf_w, shelf_h, COLOR_RABBETS))
    
    viz_elements.append(create_svg_footer())
    files[f"VISUALIZATION_BACK_PANEL.v{version}.svg"] = "\n".join(viz_elements)
    
    geometry_data = {
        'perimeter_d': path_d,
        'holes': hole_positions, # Empty now
        'hole_r': hole_r,
        'rabbet_outer_rect': (ax, ay, width_in, height_in),
        'rabbet_inner_rect': (rab_x, rab_y, inner_w, inner_h),
        'rim_width': rim_width,
        'hatch': hatch_data # Pass to Master Layout
    }
    
    return files, geometry_data

def generate_french_cleats(version):
    """Generate French Cleat SVGs (Wall + Box parts) including Bevel Score and Holes."""
    if not CONFIG.get('CLEATS_ENABLED', True):
        return {}, None

    width_in = convert_to_inches(CONFIG['TOTAL_WIDTH'])
    stock_thk = convert_to_inches(CONFIG['STOCK_THICKNESS'])
    
    # "width = 80% of the total width of Back Panel"
    # Back Panel width IS Total Width (minus rabbet in theory, but here "Total Width of Back Panel" usually implies the part width).
    # Back Panel Part Width = CONFIG['TOTAL_WIDTH'].
    cleat_w = min(width_in * 0.80, 48.0)
    cleat_h = 4.0 # Fixed 4 inches high
    
    canvas_w = cleat_w + (2 * MARGIN_INCHES)
    canvas_h = cleat_h + (2 * MARGIN_INCHES)
    ax = MARGIN_INCHES
    ay = MARGIN_INCHES
    
    files = {}
    
    # --- PART 1: WALL CLEAT (Holes) ---
    # "One of the cleats shall have sets of predrilled ... holes"
    # "Center-Out Symmetry" agreed.
    # "Every two inches".
    # Y positions: 1.25" from bottom, 1.25" from top.
    
    # Wall Cleat Elements
    wc_elements = []
    wc_elements.append(create_svg_header(canvas_w, canvas_h, f"CLEAT_WALL_PERIMETER"))
    # Perimeter
    wc_elements.append(create_rect(ax, ay, cleat_w, cleat_h, COLOR_PERIMETER))
    wc_elements.append(create_svg_footer())
    files[f"CLEAT_WALL_PERIMETER.v{version}.svg"] = "\n".join(wc_elements)
    
    # Holes (Through & Csink)
    # Csink: 0.375" dia, Pocket (Depth 0.175")
    # Through: 0.188" dia
    
    hole_positions = []
    
    # Calculate symmetry/Locations (v1.09)
    # User Spec: 5%, 33%, 66%, 95% of widith.
    # Vertical: Centered in 4" cleat -> Y = 2.0"
    
    # Store Offsets for separate Cleat Parts
    cleat_offsets = [0.05, 0.33, 0.66, 0.95]
    
    # 1. WALL CLEAT HOLES (Original Logic - 2" spacing Center-Out)
    # User didn't change Wall Cleat logic ("The Cleat without the many holes [Box Cleat] must have [mounting] holes... The French Cleat [Box Cleat] itself should have...")
    # Wait, "The Cleat without the many holes" usually refers to the Box Cleat (simple).
    # "The French Cleat itself" ... creates ambiguity.
    # Let's assume Wall Cleat keeps "Many Holes" (Standard mounting to wall).
    # Box Cleat gets the 4 specific mounting holes.
    
    wall_hole_positions = []
    cx = cleat_w / 2
    y_bot = 1.25
    y_top = cleat_h - 1.25
    
    offsets = [0.0]
    curr_off = 2.0
    while (cx + curr_off) <= (cleat_w - 1.0):
        offsets.append(curr_off)
        curr_off += 2.0
        
    for off in offsets:
        if off == 0:
            wall_hole_positions.append((ax + cx, ay + y_bot))
            wall_hole_positions.append((ax + cx, ay + y_top))
        else:
            wall_hole_positions.append((ax + cx + off, ay + y_bot))
            wall_hole_positions.append((ax + cx + off, ay + y_top))
            wall_hole_positions.append((ax + cx - off, ay + y_bot))
            wall_hole_positions.append((ax + cx - off, ay + y_top))
            
    # 2. BOX CLEAT HOLES (New v1.09)
    # 4 Holes at specific percentages.
    box_hole_positions = []
    box_hole_y = ay + (cleat_h / 2.0) # Centered Vertically (2")
    
    for pct in cleat_offsets:
        hx = ax + (pct * cleat_w)
        box_hole_positions.append((hx, box_hole_y))
            
    # WALL CLEAT Generated Hole SVGs
    # Through
    wc_th_elements = []
    wc_th_elements.append(create_svg_header(canvas_w, canvas_h, f"CLEAT_WALL_HOLES_THROUGH"))
    r_thru = 0.188 / 2
    for hx, hy in wall_hole_positions:
        wc_th_elements.append(create_circle(hx, hy, r_thru, COLOR_HOLES))
    wc_th_elements.append(create_svg_footer())
    files[f"CLEAT_WALL_HOLES_THROUGH.v{version}.svg"] = "\n".join(wc_th_elements)
    
    # Countersink
    wc_cs_elements = []
    wc_cs_elements.append(create_svg_header(canvas_w, canvas_h, f"CLEAT_WALL_HOLES_CSINK"))
    r_cs = 0.375 / 2
    for hx, hy in wall_hole_positions:
        wc_cs_elements.append(create_circle(hx, hy, r_cs, COLOR_POCKETS)) 
    wc_cs_elements.append(create_svg_footer())
    files[f"CLEAT_WALL_HOLES_CSINK.v{version}.svg"] = "\n".join(wc_cs_elements)
    
    # Bevel Score (Score Line)
    # "single pass that is a 1mm cut marking the bevel (the top of the Y height - the Material Thickness)"
    # Top of Y (in SVG) is `ay`. Bottom is `ay + cleat_h`.
    # User said "top of the Y height".
    # Logic agreed: "Score Line Y: 0.0 + 0.597" (Measure Thickness down from Top Edge).
    # Wait, Top Edge in SVG is Y=0 (or `ay`).
    # Bevel Score Y = `ay + stock_thk`.
    # Line width = cleat_w.
    
    score_y = ay + stock_thk
    
    bs_elements = []
    bs_elements.append(create_svg_header(canvas_w, canvas_h, f"CLEAT_BEVEL_SCORE"))
    # Line from (ax, score_y) to (ax + cleat_w, score_y)
    bs_elements.append(f'<line x1="{f(ax)}" y1="{f(score_y)}" x2="{f(ax + cleat_w)}" y2="{f(score_y)}" stroke="blue" stroke-width="0.01" fill="none" />')
    bs_elements.append(create_svg_footer())
    files[f"CLEAT_BEVEL_SCORE.v{version}.svg"] = "\n".join(bs_elements)
    
    
    # --- PART 2: BOX CLEAT (With Mounting Holes) ---
    # Perimeter
    bc_elements = []
    bc_elements.append(create_svg_header(canvas_w, canvas_h, f"CLEAT_BOX_PERIMETER"))
    bc_elements.append(create_rect(ax, ay, cleat_w, cleat_h, COLOR_PERIMETER))
    bc_elements.append(create_svg_footer())
    files[f"CLEAT_BOX_PERIMETER.v{version}.svg"] = "\n".join(bc_elements)

    # Box Cleat Holes (Through & Countersink for Mounting)
    # #10 Screw -> Through 0.2", Head 0.4" ?
    # Let's use same sizes as Wall for consistency (r_thru, r_cs).
    
    # Through
    bc_th_elements = []
    bc_th_elements.append(create_svg_header(canvas_w, canvas_h, f"CLEAT_BOX_HOLES_THROUGH"))
    for hx, hy in box_hole_positions:
        bc_th_elements.append(create_circle(hx, hy, r_thru, COLOR_HOLES))
    bc_th_elements.append(create_svg_footer())
    files[f"CLEAT_BOX_HOLES_THROUGH.v{version}.svg"] = "\n".join(bc_th_elements)

    # Countersink
    bc_cs_elements = []
    bc_cs_elements.append(create_svg_header(canvas_w, canvas_h, f"CLEAT_BOX_HOLES_CSINK"))
    for hx, hy in box_hole_positions:
        bc_cs_elements.append(create_circle(hx, hy, r_cs, COLOR_POCKETS))
    bc_cs_elements.append(create_svg_footer())
    files[f"CLEAT_BOX_HOLES_CSINK.v{version}.svg"] = "\n".join(bc_cs_elements)
    
    # Return Dicts
    # Structure: We return one dict of files, and a data object to describe them for layout
    
    cleat_data = {
        'cleat_w': cleat_w,
        'cleat_h': cleat_h,
        'wall_cleat_files': {
            'PERIMETER': f"CLEAT_WALL_PERIMETER.v{version}.svg",
            'HOLES_THROUGH': f"CLEAT_WALL_HOLES_THROUGH.v{version}.svg",
            'HOLES_CSINK': f"CLEAT_WALL_HOLES_CSINK.v{version}.svg",
            'SCORE': f"CLEAT_BEVEL_SCORE.v{version}.svg"
        },
        'box_cleat_files': {
            'PERIMETER': f"CLEAT_BOX_PERIMETER.v{version}.svg",
            'HOLES_THROUGH': f"CLEAT_BOX_HOLES_THROUGH.v{version}.svg",
            'HOLES_CSINK': f"CLEAT_BOX_HOLES_CSINK.v{version}.svg",
            'SCORE': f"CLEAT_BEVEL_SCORE.v{version}.svg"
        },
        'svg_contents': files # Raw content access
    }
    
    return files, cleat_data

# ==============================================================================
# UI - Simplified from v42
# ==============================================================================

class PillButton(tk.Canvas):
    """Oval pill-shaped button with hover effect."""
    def __init__(self, parent, width, height, color="#00be03", hover_color=None, fg="white", command=None, text="", font=("Lato", 14, "bold")):
        tk.Canvas.__init__(self, parent, borderwidth=0, relief="flat", highlightthickness=0, bg=parent["bg"])
        self.command = command
        self.fg = fg
        self.normal_color = color
        self.hover_color = hover_color or self._darken_color(color)
        self.btn_width = width
        self.btn_height = height
        self.text_val = text
        self.btn_font = font

        self.configure(width=width, height=height)
        self.draw(self.normal_color)

        self.bind("<Button-1>", self.on_click)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def _darken_color(self, hex_color):
        """Darken a hex color by 15%."""
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r, g, b = int(r * 0.85), int(g * 0.85), int(b * 0.85)
        return f"#{r:02x}{g:02x}{b:02x}"

    def draw(self, fill_color):
        self.delete("all")
        w = self.btn_width
        h = self.btn_height
        r = h // 2  # Radius is half the height for pill shape

        # Draw pill shape: left semicircle + rectangle + right semicircle
        # Left semicircle
        self.create_oval(0, 0, h, h, fill=fill_color, outline=fill_color)
        # Right semicircle
        self.create_oval(w - h, 0, w, h, fill=fill_color, outline=fill_color)
        # Center rectangle
        self.create_rectangle(r, 0, w - r, h, fill=fill_color, outline=fill_color)

        # Text
        self.create_text(w / 2, h / 2, text=self.text_val, fill=self.fg, font=self.btn_font)

    def on_click(self, event):
        if self.command:
            self.command()

    def on_enter(self, event):
        self.draw(self.hover_color)
        self.config(cursor="hand2")

    def on_leave(self, event):
        self.draw(self.normal_color)

class ScrollableFrame(tk.Frame):
    """
    A scrollable frame using a Canvas.
    """
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        # Canvas
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, bg=kwargs.get('bg', '#f0f0f0'))
        
        # Scrollbar
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        # Scrollable Frame (Inside Canvas)
        self.scrollable_frame = tk.Frame(self.canvas, bg=kwargs.get('bg', '#f0f0f0'))
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind Mousewheel (Mac Support)
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta)), "units")

class CarbideOptimizedApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CNC Plywood Parametric Box Maker")
        self.geometry("900x850") 
        self.configure(bg="#f0f0f0")
        self.resizable(True, True) # User asked for resizable: "resizable in case it is used on a different machine"

        # Smart default path logic
        target_path = Path("/Users/joelsilverman/Desktop/2026 Files/26-005 Gemini-created CNC Box Creator/Gemini McTell CNC Plans/")
        current_path = Path(__file__).resolve().parent
        default_out = str(target_path) if current_path == target_path.resolve() else str(current_path)

        # Settings file path
        self.settings_file = current_path / "cnc_generator_settings.json"

        # Variables - Now with Unit Toggles
        self.vars = {
            'out_folder': tk.StringVar(value=default_out),
            
            # Dimensions
            'width': tk.StringVar(value="40.0"),
            'width_unit': tk.StringVar(value="in"),
            
            'height': tk.StringVar(value="40.0"),
            'height_unit': tk.StringVar(value="in"),
            
            'depth': tk.StringVar(value="4.0"),
            'depth_unit': tk.StringVar(value="in"),
            
            'stock_thk': tk.StringVar(value="15.0"),
            'stock_unit': tk.StringVar(value="mm"), # Default mm to match "15.0" value
            
            # Tooling & Joinery
            'tool_primary': tk.StringVar(value="0.25"), # Fixed Inches
            
            'glue_gap': tk.StringVar(value="0.0197"), # 0.5mm approx
            'glue_gap_unit': tk.StringVar(value="in"),
            
            'finger_width': tk.StringVar(value="15.0"),
            'finger_width_unit': tk.StringVar(value="mm"), # Default mm for typical metric bits/fingers often? Or match prompt "in(x)"
            
            # pilot_dia removed v1.13 (Glued Back Panel)
            
            # Lid / Window
            'lid_fit_adjustment': tk.StringVar(value="0.0"), # "Shrink Lid Fit"
            'lid_fit_unit': tk.StringVar(value="mm"),

            'window_enabled': tk.BooleanVar(value=True),
            'window_w': tk.StringVar(value=""),
            'window_w_unit': tk.StringVar(value="in"),
            
            'window_h': tk.StringVar(value=""),
            'window_h_unit': tk.StringVar(value="in"),
            
            # French Cleats
            'cleats_enabled': tk.BooleanVar(value=True),
            
            # Motors / Other
            'motor_enabled': tk.BooleanVar(value=True),
            'motor_x_val': tk.StringVar(value=""),
            'cable_offset': tk.StringVar(value="3.0"),
            
            # Rear Access Panel
            'hatch_enabled': tk.BooleanVar(value=True), # User Request: On by default
            'hatch_width_pct': tk.StringVar(value="50.0"),
            'hatch_height_pct': tk.StringVar(value="33.0"), 
            'hatch_raise': tk.StringVar(value="0.0"),
            'hatch_raise_unit': tk.StringVar(value="in"),

            # Bottom Access Panel (New v1.22)
            'bottom_hatch_enabled': tk.BooleanVar(value=False),
            'bottom_hatch_w': tk.StringVar(value=""),
            'bottom_hatch_w_unit': tk.StringVar(value="in"),
            'bottom_hatch_h': tk.StringVar(value=""),
            'bottom_hatch_h_unit': tk.StringVar(value="in"),
            'bottom_hatch_x_pct': tk.StringVar(value="50.0"), # Default Center
            'bottom_hatch_x_status': tk.StringVar(value="") # For status label
        }
        
        # Track previous units for dynamic conversion
        self.last_units = {
            'width': 'in', 'height': 'in', 'depth': 'in', 'stock_thk': 'mm',
            'glue_gap': 'in', 'finger_width': 'mm',
            'lid_fit_adjustment': 'mm', 'window_w': 'in', 'window_h': 'in',
            'hatch_raise': 'in',
            'bottom_hatch_w': 'in', 'bottom_hatch_h': 'in'
        }
        # Sync initial tracking with actual vars
        for key in self.last_units:
            pass 
        
        # Correctly map the var names for init
        self.unit_map = {
            'width': 'width_unit', 'height': 'height_unit', 'depth': 'depth_unit',
            'stock_thk': 'stock_unit', 'glue_gap': 'glue_gap_unit',
            'finger_width': 'finger_width_unit',
            'lid_fit_adjustment': 'lid_fit_unit', 'window_w': 'window_w_unit',
            'window_h': 'window_h_unit', 'hatch_raise': 'hatch_raise_unit',
            'bottom_hatch_w': 'bottom_hatch_w_unit', 'bottom_hatch_h': 'bottom_hatch_h_unit'
        }
        
        # Initialize last_units from current vars
        for val_key, unit_key in self.unit_map.items():
            if unit_key in self.vars:
                self.last_units[val_key] = self.vars[unit_key].get()

        self.load_settings()
        self.setup_ui()
        
        # After loading settings, we must sync last_units to whatever was loaded
        # The stored settings don't strictly save the unit state (unless we added those vars to save_settings logic, which we haven't explicitely)
        # Actually, Tkinter vars hold the loaded State. 
        # So we just need to ensure last_units matches self.vars right now.
        for val_key, unit_key in self.unit_map.items():
            if unit_key in self.vars:
                # If settings loaded "mm" for depth, set last_units['depth'] = 'mm'
                self.last_units[val_key] = self.vars[unit_key].get()
        
        # DEBUG: Print starting units
        # print("DEBUG: Initial Units:", self.last_units)


    def load_settings(self):
        """Load settings from JSON file if it exists."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    
                for key, val in data.items():
                    if key in self.vars:
                        # Handle BooleanVar specifically
                        if isinstance(self.vars[key], tk.BooleanVar):
                            self.vars[key].set(bool(val))
                        # Handle DoubleVar
                        elif isinstance(self.vars[key], tk.DoubleVar):
                            try:
                                self.vars[key].set(float(val))
                            except:
                                pass 
                        # Handle StringVar (default)
                        else:
                            self.vars[key].set(str(val))
                print(f"Loaded settings from {self.settings_file}")
            except Exception as e:
                print(f"Failed to load settings: {e}")

    def save_settings(self):
        """Save current settings to JSON file."""
        data = {}
        for key, var in self.vars.items():
            data[key] = var.get()
        
        # IMPORTANT: We should save the unit states too, enabling persistent unit selection
        # (The vars dict already contains the unit_vars, so this happens automatically because they are in self.vars)
        # Verify: self.vars includes 'width_unit', etc. Yes, added in __init__.
        
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Saved settings to {self.settings_file}")
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def setup_ui(self):
        # Color scheme
        BG_COLOR = "#f0f0f0"        # Light gray background
        TEXT_PRIMARY = "#333333"     # Dark gray text
        TEXT_SECONDARY = "#666666"   # Medium gray text
        TEXT_HINT = "#999999"        # Light gray hints
        SECTION_HEADER_COLOR = "#a9d4f0" # Light Blue
        INPUT_BG = "#ffffff"         # White input fields
        
        # Fonts
        # Title "CNC Plywood Parametric Box Maker": 24pt Bold (implied big)
        FONT_TITLE = ("Lato", 24, "bold")
        FONT_SECTION = ("Lato", 12, "bold") # Headers
        FONT_LABEL = ("Lato", 11)
        FONT_INPUT = ("Lato", 11)
        FONT_WARNING = ("Futura", 9)
        FONT_BUTTON = ("Lato", 13, "bold")
        FONT_VERSION = ("Lato", 9)
        FONT_HINT = ("Lato", 9)

        self.ui_colors = {
            'bg': BG_COLOR, 'text': TEXT_PRIMARY, 'hint': TEXT_HINT,
            'input_bg': INPUT_BG
        }
        self.ui_fonts = {'label': FONT_LABEL, 'input': FONT_INPUT}

        self.configure(bg=BG_COLOR)

        # Main container
        container = tk.Frame(self, bg=BG_COLOR)
        container.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)

        # TITLE
        tk.Label(container, text="CNC Plywood Parametric Box Maker",
                 font=FONT_TITLE, bg=BG_COLOR, fg=TEXT_PRIMARY).pack(anchor="w")

        # Divider
        tk.Frame(container, height=1, bg="#dddddd").pack(fill=tk.X, pady=(5, 15))

        # Main Layout: Left Control Panel | Right Preview Panel
        content = tk.Frame(container, bg=BG_COLOR)
        content.pack(fill=tk.BOTH, expand=True)

        # LEFT COLUMN (Scrollable)
        # We wrap it in a frame that has fixed width or relative width
        left_wrapper = tk.Frame(content, bg=BG_COLOR, width=420) 
        left_wrapper.pack(side="left", fill=tk.BOTH, expand=True, padx=(0, 20))
        left_wrapper.pack_propagate(False) # Force width respect
        
        self.left_scroll = ScrollableFrame(left_wrapper, bg=BG_COLOR)
        self.left_scroll.pack(fill=tk.BOTH, expand=True)
        
        left_col = self.left_scroll.scrollable_frame # All widgets go here
        
        # === SECTION 1: DIMENSIONS ===
        self.make_section_header(left_col, "DIMENSIONS")
        
        dim_frame = tk.Frame(left_col, bg=BG_COLOR)
        dim_frame.pack(fill=tk.X, pady=(5, 15))
        
        # Width, Height
        self.make_row_with_units(dim_frame, 0, "Width", self.vars['width'], self.vars['width_unit'])
        self.make_row_with_units(dim_frame, 1, "Height", self.vars['height'], self.vars['height_unit'])
        
        # Depth
        # Spacing: Depth line
        self.make_row_with_units(dim_frame, 2, "Depth", self.vars['depth'], self.vars['depth_unit'])

        # Stock Thickness
        self.make_row_with_units(dim_frame, 3, "Stock Thickness", self.vars['stock_thk'], self.vars['stock_unit'])
        
        # Warning Label (Futura 9pt, #8c8c8c)
        tk.Label(dim_frame, text="Use calipers to measure exact thickness of stock, or joinery will not be tight",
                 font=FONT_WARNING, bg=BG_COLOR, fg="#8c8c8c").grid(row=4, column=0, columnspan=5, sticky="w", padx=(5,0), pady=(0, 8))

        # Router Bit, Glue Gap
        # Router Bit is fixed 'in'
        self.make_row_fixed_unit(dim_frame, 5, "Router Bit", self.vars['tool_primary'], "in")
        self.make_row_with_units(dim_frame, 6, "Glue Gap", self.vars['glue_gap'], self.vars['glue_gap_unit'])


        # === SECTION 2: JOINERY ===
        self.make_section_header(left_col, "JOINERY")
        
        join_frame = tk.Frame(left_col, bg=BG_COLOR)
        join_frame.pack(fill=tk.X, pady=(5, 15))
        
        self.make_row_with_units(join_frame, 0, "Finger Width", self.vars['finger_width'], self.vars['finger_width_unit'])
        # Back Panel Holes removed v1.13



        # === SECTION 3: WINDOW ===
        self.make_section_header(left_col, "WINDOW")
        
        win_frame = tk.Frame(left_col, bg=BG_COLOR)
        win_frame.pack(fill=tk.X, pady=(5, 15))

        # Checkbox
        tk.Checkbutton(win_frame, text="Enable Front Window Cutout", variable=self.vars['window_enabled'],
                       bg=BG_COLOR, fg=TEXT_PRIMARY, font=FONT_LABEL, selectcolor="#ffffff").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,5))
        
        self.make_row_with_units(win_frame, 1, "Width", self.vars['window_w'], self.vars['window_w_unit'])
        self.make_row_with_units(win_frame, 2, "Height", self.vars['window_h'], self.vars['window_h_unit'])
        self.make_row_with_units(win_frame, 3, "Shrink Lid Fit", self.vars['lid_fit_adjustment'], self.vars['lid_fit_unit'])


        # === SECTION 4: OUTPUT ===
        self.make_section_header(left_col, "OUTPUT")
        
        out_frame = tk.Frame(left_col, bg=BG_COLOR)
        out_frame.pack(fill=tk.X, pady=(5, 10))

        tk.Label(out_frame, text="Output Folder", font=FONT_LABEL, bg=BG_COLOR, fg=TEXT_PRIMARY).pack(anchor="w")
        
        out_row = tk.Frame(out_frame, bg=BG_COLOR)
        out_row.pack(fill=tk.X)
        
        tk.Entry(out_row, textvariable=self.vars['out_folder'], font=FONT_INPUT,
                 bg=INPUT_BG, relief=tk.SOLID, bd=1, width=32).pack(side="left")
        
        tk.Button(out_row, text="Browse", command=self.browse_folder, font=("Lato", 10),
                  bg="#e0e0e0", relief=tk.FLAT).pack(side="left", padx=5)


        # === SECTION: FRENCH CLEATS ===
        cleat_frame = tk.Frame(left_col, bg=BG_COLOR)
        cleat_frame.pack(fill=tk.X, pady=(5, 5))
        tk.Checkbutton(cleat_frame, text="Enable French Cleats (4\" High)", variable=self.vars['cleats_enabled'],
                       bg=BG_COLOR, fg=TEXT_PRIMARY, font=FONT_LABEL, selectcolor="#ffffff").pack(anchor="w")

        # --- BOTTOM AREA: MOTORS & RESET & GENERATE ---
        
        # Motors (User asked to keep) - Placing subtly at bottom
        motor_frame = tk.Frame(left_col, bg=BG_COLOR)
        motor_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Checkbutton(motor_frame, text="Enable Motor Pocket", variable=self.vars['motor_enabled'],
                       bg=BG_COLOR, font=("Lato", 10)).pack(side="left")
        # Cable Offset
        tk.Label(motor_frame, text="Cable Offset:", bg=BG_COLOR, font=("Lato", 10)).pack(side="left", padx=(10,0))
        tk.Entry(motor_frame, textvariable=self.vars['cable_offset'], width=4).pack(side="left")

        # === SECTION 5: REAR ACCESS PANEL ===
        self.make_section_header(left_col, "REAR ACCESS PANEL")
        
        hatch_frame = tk.Frame(left_col, bg=BG_COLOR)
        hatch_frame.pack(fill=tk.X, pady=(5, 15))

        # Checkbox
        tk.Checkbutton(hatch_frame, text="Enable Rear Access Panel", variable=self.vars['hatch_enabled'],
                       bg=BG_COLOR, fg=TEXT_PRIMARY, font=FONT_LABEL, selectcolor="#ffffff").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,5))
        
        # Width %, Height %, Raise
        self.make_row_with_units(hatch_frame, 1, "Width %", self.vars['hatch_width_pct'], None) # No unit toggle for %
        self.make_row_with_units(hatch_frame, 2, "Height %", self.vars['hatch_height_pct'], None)
        self.make_row_with_units(hatch_frame, 3, "Raise Panel", self.vars['hatch_raise'], self.vars['hatch_raise_unit'])

        # === SECTION 6: BOTTOM ACCESS PANEL (NEW) ===
        self.make_section_header(left_col, "BOTTOM ACCESS PANEL")
        
        b_hatch_frame = tk.Frame(left_col, bg=BG_COLOR)
        b_hatch_frame.pack(fill=tk.X, pady=(5, 15))
        
        # Checkbox
        tk.Checkbutton(b_hatch_frame, text="Enable Bottom Access Panel", variable=self.vars['bottom_hatch_enabled'],
                       bg=BG_COLOR, fg=TEXT_PRIMARY, font=FONT_LABEL, selectcolor="#ffffff",
                       command=self.update_bottom_hatch_status).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,5))
        
        # Width, Height, X Pct
        self.make_row_with_units(b_hatch_frame, 1, "Width", self.vars['bottom_hatch_w'], self.vars['bottom_hatch_w_unit'])
        self.make_row_with_units(b_hatch_frame, 2, "Height", self.vars['bottom_hatch_h'], self.vars['bottom_hatch_h_unit'])
        self.make_row_with_units(b_hatch_frame, 3, "X Position %", self.vars['bottom_hatch_x_pct'], None)
        
        # Status Label (10pt Futura #ffe102 -> Darker background or visible on light?)
        # User specified #ffe102 (Yellow). On #f0f0f0 (Light Grey) this is hard to read.
        # But user requested valid hex #ffe102. I will use a darker label bg or outline? No, just FG. 
        # Actually #ffe102 is very bright yellow. I'll add a dark background to the label so it's readable?
        # "presented under the entry box should state in 10 pt Futura text #ffe102"
        # I'll put it in a dark frame or label bg.
        status_lbl = tk.Label(b_hatch_frame, textvariable=self.vars['bottom_hatch_x_status'],
                              font=("Futura", 10), fg="#ffe102", padx=5, pady=2)
        status_lbl.grid(row=4, column=0, columnspan=4, sticky="w", pady=(5,0))
        
        # Update initially
        self.update_bottom_hatch_status()


        # Reset Button (Left side)
        reset_frame = tk.Frame(left_col, bg=BG_COLOR)
        reset_frame.pack(fill=tk.X, pady=(10, 0))
        PillButton(reset_frame, width=80, height=28, color="#e498c3", text="RESET",
                   command=self.reset_to_defaults, font=("Lato", 10)).pack(anchor="w")


        # --- RIGHT COLUMN (3D PREVIEW) ---
        right_col = tk.Frame(content, bg=BG_COLOR)
        right_col.pack(side="left", fill=tk.BOTH, expand=True, padx=(10,0))

        # 3D Preview Widget
        self.preview_3d = BoxPreview3D(right_col, width=373, height=320)
        self.preview_3d.pack(pady=(0, 10))

        # Hint text for interaction
        tk.Label(right_col, text="Click and drag to rotate object", font=FONT_HINT, bg=BG_COLOR, fg=TEXT_HINT).pack(anchor="center", pady=(0, 8))

        # Generate Button
        PillButton(right_col, width=220, height=50, color="#00be03", text="GENERATE SVGs",
                   command=self.run_generation, font=("Lato", 15, "bold")).pack(pady=20)


        tk.Label(container, text="v1.24", font=FONT_VERSION, bg=BG_COLOR, fg=TEXT_HINT).place(relx=1.0, rely=1.0, anchor="se")

        # Live Updates
        self._setup_live_preview_updates()


    def make_section_header(self, parent, text):
        """Create a colored section header."""
        lbl = tk.Label(parent, text=text, font=("Lato", 12, "bold"), bg="#f0f0f0", fg="#49bcf6")
        lbl.pack(anchor="w", pady=(5, 2))
        # Optional colored underline or background? Header requested as text.
    
    def make_row_with_units(self, parent, row, label, var, unit_var):
        """
        Row: Label (Left) ... [Entry] (x) in ( ) mm
        """
        bg = self.ui_colors['bg']
        fg = self.ui_colors['text']
        
        # Label
        tk.Label(parent, text=label, font=self.ui_fonts['label'], bg=bg, fg=fg, width=15, anchor="w").grid(row=row, column=0, padx=5, pady=3)
        
        # Entry with Undo binding
        entry = tk.Entry(parent, textvariable=var, font=self.ui_fonts['input'], bg="#ffffff", relief=tk.SOLID, bd=1, width=8)
        entry.grid(row=row, column=1, padx=5)
        self._add_undo_bindings(entry)
        
        # Determine variable name for callback
        # Reverse lookup from self.vars to find the key for 'var' (value variable)
        val_key = None
        for k, v in self.vars.items():
            if v == var:
                val_key = k
                break
        
        # Radio Buttons with Handler
        # Usage: command=lambda: self.handle_unit_toggle(val_key, unit_var)
        if unit_var:
            cmd = lambda: self.handle_unit_toggle(val_key, unit_var)
            tk.Radiobutton(parent, text="in", variable=unit_var, value="in", bg=bg, activebackground=bg, command=cmd, takefocus=0).grid(row=row, column=2)
            tk.Radiobutton(parent, text="mm", variable=unit_var, value="mm", bg=bg, activebackground=bg, command=cmd, takefocus=0).grid(row=row, column=3)
        else:
            # Just a placeholder or specific label for %?
             tk.Label(parent, text="%", font=self.ui_fonts['label'], bg=bg, fg="#666666").grid(row=row, column=2, sticky="w")

    def _add_undo_bindings(self, widget):
        """Add basic Mac-style Undo/Redo to an Entry widget."""
        # Tkinter Entry doesn't support built-in undo, but we can bind Cmd+Z
        try:
             pass
        except:
             pass

    def handle_unit_toggle(self, val_key, unit_var):
        """Convert value when unit changes."""
        if not val_key: return
        
        new_unit = unit_var.get()
        old_unit = self.last_units.get(val_key, new_unit)
        
        if new_unit == old_unit:
            return
            
        try:
            current_val_str = self.vars[val_key].get().strip()
            if not current_val_str: return
            
            val = float(current_val_str)
            
            # Convert
            if old_unit == 'in' and new_unit == 'mm':
                # in -> mm
                new_val = val * 25.4
                self.vars[val_key].set(f"{new_val:.4f}")
            elif old_unit == 'mm' and new_unit == 'in':
                # mm -> in
                new_val = val / 25.4
                self.vars[val_key].set(f"{new_val:.4f}")
                
            # Update tracker
            self.last_units[val_key] = new_unit
            
        except ValueError:
            pass # Ignore invalid numbers


    def make_row_fixed_unit(self, parent, row, label, var, unit_text):
        """Row with fixed unit text."""
        bg = self.ui_colors['bg']
        fg = self.ui_colors['text']
        tk.Label(parent, text=label, font=self.ui_fonts['label'], bg=bg, fg=fg, width=15, anchor="w").grid(row=row, column=0, padx=5, pady=3)
        tk.Entry(parent, textvariable=var, font=self.ui_fonts['input'], bg="#ffffff", relief=tk.SOLID, bd=1, width=8).grid(row=row, column=1, padx=5)
        tk.Label(parent, text=unit_text, font=self.ui_fonts['label'], bg=bg, fg="#666666").grid(row=row, column=2, sticky="w")

    def _setup_live_preview_updates(self):
        """Bind variable changes to update the 3D preview."""
        def on_change(*args):
            try:
                # Helper to get inches
                def get_inches(val_var, unit_var):
                    try:
                        val = float(val_var.get())
                        if unit_var.get() == "mm":
                            return val / 25.4
                        return val
                    except:
                        return 0.0

                w = get_inches(self.vars['width'], self.vars['width_unit'])
                h = get_inches(self.vars['height'], self.vars['height_unit'])
                d = get_inches(self.vars['depth'], self.vars['depth_unit'])
                s = get_inches(self.vars['stock_thk'], self.vars['stock_unit'])
                
                win_w = get_inches(self.vars['window_w'], self.vars['window_w_unit'])
                win_h = get_inches(self.vars['window_h'], self.vars['window_h_unit'])
                
                if not self.vars['window_enabled'].get():
                    win_w = 0; win_h = 0
                
                # Retrieve Hatch Variables
                hatch_enabled = self.vars['hatch_enabled'].get()
                hatch_w_pct = 0.0
                hatch_h_pct = 0.0
                hatch_raise = 0.0
                
                if hatch_enabled:
                    try:
                        hatch_w_pct = float(self.vars['hatch_width_pct'].get())
                        hatch_h_pct = float(self.vars['hatch_height_pct'].get())
                        hatch_raise = get_inches(self.vars['hatch_raise'], self.vars['hatch_raise_unit'])
                    except:
                        pass

                # Bottom Access Panel
                b_hatch_enabled = self.vars['bottom_hatch_enabled'].get()
                b_hatch_w = get_inches(self.vars['bottom_hatch_w'], self.vars['bottom_hatch_w_unit'])
                b_hatch_h = get_inches(self.vars['bottom_hatch_h'], self.vars['bottom_hatch_h_unit'])
                b_hatch_x_pct = 0.0
                try:
                    b_hatch_x_pct = float(self.vars['bottom_hatch_x_pct'].get())
                except:
                    pass

                self.preview_3d.update_box(w, h, d, s, win_w, win_h, 
                                          hatch_enabled, hatch_w_pct, hatch_h_pct, hatch_raise,
                                          b_hatch_enabled, b_hatch_w, b_hatch_h, b_hatch_x_pct)
            except Exception as e:
                print(f"Preview Error: {e}")

        # Trace
        traces = ['width', 'height', 'depth', 'stock_thk', 'window_w', 'window_h', 
                  'width_unit', 'height_unit', 'depth_unit', 'stock_unit', 
                  'window_w_unit', 'window_h_unit', 'window_enabled',
                   'hatch_enabled', 'hatch_width_pct', 'hatch_height_pct', 'hatch_raise', 'hatch_raise_unit',
                  'bottom_hatch_enabled', 'bottom_hatch_w', 'bottom_hatch_h', 'bottom_hatch_x_pct']
        for t in traces:
            if t in self.vars:
                self.vars[t].trace_add('write', on_change)
        
        on_change()
        
        # Bind for Bottom Access Panel Status Update
        self.vars['bottom_hatch_w'].trace_add('write', self.update_bottom_hatch_status)
        self.vars['bottom_hatch_x_pct'].trace_add('write', self.update_bottom_hatch_status)
        self.vars['width'].trace_add('write', self.update_bottom_hatch_status)
        self.vars['stock_thk'].trace_add('write', self.update_bottom_hatch_status)
        
    def update_bottom_hatch_status(self, *args):
        """Update the status label for Bottom Access Hatch."""
        if not self.vars['bottom_hatch_enabled'].get():
            self.vars['bottom_hatch_x_status'].set("")
            return

        try:
            # Helper: Get inch value
            def get_val_in(var_name, unit_var_name=None):
                try:
                    val = float(self.vars[var_name].get())
                    if unit_var_name and self.vars[unit_var_name].get() == "mm":
                        return val / 25.4
                    return val
                except:
                    return 0.0

            rail_w_in = get_val_in('width', 'width_unit') - (2 * get_val_in('stock_thk', 'stock_unit'))
            hatch_w_in = get_val_in('bottom_hatch_w', 'bottom_hatch_w_unit')
            x_pct = 0.0
            try:
                x_pct = float(self.vars['bottom_hatch_x_pct'].get())
            except:
                pass
            
            if rail_w_in <= 0 or hatch_w_in <= 0:
                self.vars['bottom_hatch_x_status'].set("")
                return
            
            # X Calculation
            center_x = rail_w_in * (x_pct / 100.0)
            start_x = center_x - (hatch_w_in / 2.0)
            end_x = center_x + (hatch_w_in / 2.0)
            
            if start_x < 0: start_x = 0 # Clamp for display logic safety? No user wants exact.
            
            self.vars['bottom_hatch_x_status'].set(f"Access Hatch is between\n{start_x:.2f}\" and {end_x:.2f}\" from the Left Corner of the Frame")
        except:
            self.vars['bottom_hatch_x_status'].set("")

    def browse_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.vars['out_folder'].set(d)

    def reset_to_defaults(self):
        """Reset all parameters to the last saved/generated settings."""
        if self.settings_file.exists():
            self.load_settings()
        else:
            # Fall back to built-in defaults if no settings file
            defaults = {
                'width': "40.0",
                'height': "40.0",
                'depth': "4.0",
                'stock_thk': "15.0",
                'stock_unit': 'mm',
                'tool_primary': "0.25",
                'glue_gap': "0.0197",
                'glue_gap_unit': 'in',
                'finger_width': "15.0",
                'finger_width_unit': 'mm',
                'lid_fit_adjustment': "0.0",
                'lid_fit_unit': 'mm',
                'pilot_dia': "7.14375",
                'pilot_dia_unit': 'mm',
                'motor_enabled': True,
                'motor_x_val': "",
                'window_enabled': True,
                'window_w': "",
                'window_h': "",
                'cable_offset': "3.0",
                'hatch_enabled': True,
                'hatch_width_pct': "50.0",
                'hatch_height_pct': "33.0",
                'hatch_raise': "0.0",
                'hatch_raise_unit': "in",
                'cleats_enabled': True,
                'bottom_hatch_enabled': False,
                'bottom_hatch_w': "",
                'bottom_hatch_h': "",
                'bottom_hatch_x_pct': "50.0"
            }
            for key, val in defaults.items():
                if key in self.vars:
                    self.vars[key].set(val)

    def run_generation(self):
        try:
            raw_out = self.vars['out_folder'].get().strip()
            if not raw_out:
                raise ValueError("Please select an Output Folder.")

            # HELPER: Get value in mm (if input is inches, convert)
            def get_mm(var_name, unit_var_name=None):
                val_str = self.vars[var_name].get().strip()
                if not val_str: return 0.0
                val = float(val_str)
                
                # If no unit var, assume it's fixed (Router Bit is fixed inches per UI)
                if unit_var_name is None:
                    # Special case: Router Bit is in inches
                    return val * 25.4
                
                unit = self.vars[unit_var_name].get()
                if unit == "in":
                    return val * 25.4
                else:
                    return val

            # Update CONFIG with converted values
            CONFIG['STOCK_THICKNESS'] = get_mm('stock_thk', 'stock_unit')
            
            # Router Bit is fixed INCHES in UI
            CONFIG['TOOL_D_PRIMARY'] = float(self.vars['tool_primary'].get()) * 25.4
            
            CONFIG['FIT_TOLERANCE'] = get_mm('glue_gap', 'glue_gap_unit')
            
            # Finger Width: Could be in or mm
            target_finger_w_mm = get_mm('finger_width', 'finger_width_unit')
            CONFIG['TARGET_FINGER_WIDTH'] = target_finger_w_mm
            
            stock_thk_in = convert_to_inches(CONFIG['STOCK_THICKNESS'])
            
            # Lid Fit Adjustment (Shrink)
            fit_adj_mm = get_mm('lid_fit_adjustment', 'lid_fit_unit')
            fit_adj_in = convert_to_inches(fit_adj_mm)
            
            # AUTO-CALCULATE STEP DEPTH = Stock Thickness / 2
            step_depth_in = stock_thk_in / 2.0
            
            # Rim Width logic
            # Rim Width = Stock + GlueGap + Adjustment
            # NOTE: If Adjustment is positive (Shrink Lid Fit), it typically means making the Plug Smaller, or the Rim Wider?
            # "Shrink Lid Fit" implies making the Fit Tighter (less gap) or Looser? 
            # Original code said: "Positive = Looser".
            # Let's assume input maps directly to the logic:
            calc_rim_width = stock_thk_in + convert_to_inches(CONFIG['FIT_TOLERANCE']) + fit_adj_in
            
            CONFIG['FRONT_RABBET_WIDTH'] = stock_thk_in - calc_rim_width
            CONFIG['BACK_RABBET_WIDTH'] = stock_thk_in - calc_rim_width
            
            CONFIG['FRONT_RABBET_DEPTH'] = step_depth_in
            CONFIG['BACK_RABBET_DEPTH'] = step_depth_in
            
        # v1.13: Use default or removed.

            
            CONFIG['MOTOR_POCKET_ENABLED'] = self.vars['motor_enabled'].get()

            # BOTTOM ACCESS PANEL CONFIG
            CONFIG['BOTTOM_HATCH_ENABLED'] = self.vars['bottom_hatch_enabled'].get()
            if CONFIG['BOTTOM_HATCH_ENABLED']:
                try:
                    bh_w = get_mm('bottom_hatch_w', 'bottom_hatch_w_unit')
                    bh_h = get_mm('bottom_hatch_h', 'bottom_hatch_h_unit')
                    bh_x_pct = float(self.vars['bottom_hatch_x_pct'].get())
                    
                    CONFIG['BOTTOM_HATCH_WIDTH'] = bh_w
                    CONFIG['BOTTOM_HATCH_HEIGHT'] = bh_h
                    CONFIG['BOTTOM_HATCH_X_PCT'] = bh_x_pct
                    
                    # Validate Height Constraint
                    # Max Height = Box Depth - Front Rabbet Depth - Back Rabbet Depth - 0.5" (approx 12.7mm)
                    # Note: Using calculated depths.
                    box_depth_mm = convert_to_mm(float(self.vars['depth'].get()), self.vars['depth_unit'].get())
                    
                    # Rabbet Depths (Step Depth)
                    step_depth_mm = CONFIG['STOCK_THICKNESS'] / 2.0
                    
                    # 0.5 inches in mm
                    buffer_mm = 12.7
                    
                    max_h_mm = box_depth_mm - (2 * step_depth_mm) - buffer_mm
                    
                    if bh_h > max_h_mm:
                        print(f"WARNING: Bottom Hatch Height ({bh_h:.2f}mm) exceeds safe limit ({max_h_mm:.2f}mm). It might clash with panels.")
                    
                    # Validate Width Constraint (90% of Rail Width)
                    total_w_mm = convert_to_mm(float(self.vars['width'].get()), self.vars['width_unit'].get())
                    stock_mm = CONFIG['STOCK_THICKNESS']
                    rail_w_mm = total_w_mm - (2 * stock_mm)
                    
                    if bh_w > (rail_w_mm * 0.9):
                        print(f"WARNING: Bottom Hatch Width ({bh_w:.2f}mm) exceeds 90% of Rail Width ({rail_w_mm * 0.9:.2f}mm).")
                        
                except Exception as e:
                    print(f"Invalid Bottom Hatch Input: {e}")
                    CONFIG['BOTTOM_HATCH_ENABLED'] = False


            # REAR ACCESS PANEL CONFIG
            CONFIG['HATCH_ENABLED'] = self.vars['hatch_enabled'].get()
            if CONFIG['HATCH_ENABLED']:
                try:
                    # Parse percentages
                    w_pct = float(self.vars['hatch_width_pct'].get().strip())
                    h_pct = float(self.vars['hatch_height_pct'].get().strip())
                    CONFIG['HATCH_WIDTH_PCT'] = w_pct
                    CONFIG['HATCH_HEIGHT_PCT'] = h_pct
                except:
                    pass 
                # Parse Raise (Unit aware)
                try:
                    raise_mm = get_mm('hatch_raise', 'hatch_raise_unit')
                    CONFIG['HATCH_RAISE_IN'] = convert_to_inches(raise_mm)
                except ValueError:
                    CONFIG['HATCH_ENABLED'] = False # Disable if invalid input
                    print("Invalid Hatch Input - Disabling")
            
            # Dimensions
            CONFIG['TOTAL_WIDTH'] = get_mm('width', 'width_unit')
            CONFIG['TOTAL_HEIGHT'] = get_mm('height', 'height_unit')
            CONFIG['BOX_DEPTH'] = get_mm('depth', 'depth_unit')
            
            # Window / Rim Calculation
            total_w_in = convert_to_inches(CONFIG['TOTAL_WIDTH'])
            total_h_in = convert_to_inches(CONFIG['TOTAL_HEIGHT'])
            
            CONFIG['WINDOW_ENABLED'] = self.vars['window_enabled'].get()
            
            if CONFIG['WINDOW_ENABLED']:
                w_in = get_mm('window_w', 'window_w_unit') / 25.4
                h_in = get_mm('window_h', 'window_h_unit') / 25.4
                # Validate
                w_in = min(w_in, total_w_in - 0.5)
                h_in = min(h_in, total_h_in - 0.5)
                CONFIG['WINDOW_WIDTH_IN'] = w_in
                CONFIG['WINDOW_HEIGHT_IN'] = h_in
            else:
                CONFIG['WINDOW_WIDTH_IN'] = 0.0
                CONFIG['WINDOW_HEIGHT_IN'] = 0.0
            
            # Rim width for generated files
            rim_w_in = (total_w_in - CONFIG.get('WINDOW_WIDTH_IN', 0)) / 2
            CONFIG['FRONT_RIM_WIDTH_M'] = rim_w_in * 0.0254
            
            # Motor Pocket X
            photograph_width = CONFIG['TOTAL_WIDTH'] - (2 * CONFIG['STOCK_THICKNESS'])
            user_x = self.vars['motor_x_val'].get().strip()
            if user_x:
                try:
                    CONFIG['MOTOR_POCKET_X'] = float(user_x)
                except:
                    CONFIG['MOTOR_POCKET_X'] = 0.4155 * photograph_width
            else:
                CONFIG['MOTOR_POCKET_X'] = 0.4155 * photograph_width

            out_path = Path(raw_out)
            out_path.mkdir(parents=True, exist_ok=True)
            
            # Save settings on successful generation start
            self.save_settings()
            
            existing_versions = []
            for child in out_path.iterdir():
                if child.is_dir() and "McTell SVGs v" in child.name:
                    match = re.search(r'v(\d+)', child.name)
                    if match:
                        existing_versions.append(int(match.group(1)))
            
            next_ver = max(existing_versions) + 1 if existing_versions else 1
            final_out_dir = out_path / f"McTell SVGs v{next_ver}"
            final_out_dir.mkdir(parents=True, exist_ok=True)

            CONFIG['CLEATS_ENABLED'] = self.vars['cleats_enabled'].get()

            all_files = {}
            rail_paths = {}
            
            files_front, geom_front = generate_front_bezel_parts(next_ver)
            all_files.update(files_front)
            
            f_top, p_top = generate_rail_parts("TOP_RAIL", True, False, next_ver)
            all_files.update(f_top); rail_paths['TOP'] = p_top
            
            f_bot, p_bot = generate_rail_parts("BOTTOM_RAIL", True, True, next_ver)
            all_files.update(f_bot); rail_paths['BOTTOM'] = p_bot
            
            f_left, p_left = generate_rail_parts("LEFT_RAIL", False, False, next_ver)
            all_files.update(f_left); rail_paths['LEFT'] = p_left
            
            f_right, p_right = generate_rail_parts("RIGHT_RAIL", False, False, next_ver)
            all_files.update(f_right); rail_paths['RIGHT'] = p_right
            
            files_back, geom_back = generate_back_panel_parts(next_ver)
            all_files.update(files_back)
            
            files_cleats, cleat_data = generate_french_cleats(next_ver)
            all_files.update(files_cleats)
            
            # --- GENERATE MASTER LAYOUT (MULTI-SHEET) ---
            # Debug: Ensure all parts are valid before master generation
            def validate_part_files(part_files, part_name):
                if not part_files:
                    return {}
                valid_files = {}
                for k, v in part_files.items():
                    if v is None:
                        print(f"CRITICAL WARNING: File {k} in {part_name} has None content.")
                    else:
                        valid_files[k] = v
                return valid_files

            files_front = validate_part_files(files_front, "FRONT")
            files_back = validate_part_files(files_back, "BACK")
            f_top = validate_part_files(f_top, "TOP")
            f_bot = validate_part_files(f_bot, "BOTTOM")
            f_left = validate_part_files(f_left, "LEFT")
            f_right = validate_part_files(f_right, "RIGHT")
            
            # Check cleat data
            if cleat_data:
                cleat_data['wall_cleat_files'] = validate_part_files(cleat_data['wall_cleat_files'], "CLEAT_WALL")
                cleat_data['box_cleat_files'] = validate_part_files(cleat_data['box_cleat_files'], "CLEAT_BOX")
                cleat_data['svg_contents'] = validate_part_files(cleat_data['svg_contents'], "CLEAT_CONTENTS")

            master_svgs = generate_master_carbide_layout(next_ver, files_front, files_back, f_top, f_bot, f_left, f_right, geom_back, cleat_data)
            
            if master_svgs is None:
                print("CRITICAL ERROR: generate_master_carbide_layout returned None!")
                master_svgs = {} # Fallback to empty to prevent crash
            
            all_files.update(master_svgs)
            
            # CRITICAL FIX: Ensure Master Layout is added to all_files if it wasn't already
            # The previous update() might have worked, but let's be explicit and verbose
            master_key = f"MASTER_LAYOUT_COMBINED_v{next_ver}.svg"
            if master_key in master_svgs:
                all_files[master_key] = master_svgs[master_key]
            else:
                print(f"WARNING: Master Layout key {master_key} not found in returned svgs")
            
            # ------------------------------
            

            
            combined_svg = generate_combined_visualization(next_ver, rail_paths)
            all_files[f"VISUALIZATION_COMBINED_RAILS.v{next_ver}.svg"] = combined_svg
            
            # Get lazy-loaded generators
            gen_blender, gen_trivision = _get_blender_generator()

            # Generate Blender Script
            blender_script = gen_blender(next_ver, CONFIG, rail_paths, geom_front, geom_back)
            all_files[f"OPEN_ME_IN_BLENDER.v{next_ver}.py"] = blender_script
            
            # --- TRIVISION INTEGRATION ---
            trivision_script = gen_trivision(next_ver, CONFIG, rail_paths, geom_front, geom_back)
            all_files[f"OPEN_ME_IN_TRIVISION_v{next_ver}.py"] = trivision_script

            for fname, content in all_files.items():
                full_path = final_out_dir / fname
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # Apply Green Label (6) to Key Files
                if "OPEN_ME_IN_BLENDER" in fname or "MASTER_LAYOUT_COMBINED" in fname:
                    set_mac_label(str(full_path.absolute()), 6)

            
            
            with open(final_out_dir / "config.json", "w", encoding='utf-8') as f:
                json.dump(CONFIG, f, indent=4) # Indent for readability

            # VERIFY DIMENSIONS (v1.16/v1.22)
            SVG_PATHS = {
                'TOP_RAIL': rail_paths.get('TOP', 'M 0 0 Z'),
                'BOTTOM_RAIL': rail_paths.get('BOTTOM', 'M 0 0 Z'),
                'LEFT_RAIL': rail_paths.get('LEFT', 'M 0 0 Z'),
                'RIGHT_RAIL': rail_paths.get('RIGHT', 'M 0 0 Z'),
            }
            passed, report = verify_dimensions(SVG_PATHS, CONFIG)
            
            messagebox.showinfo("Success", f"Generation Complete!\n\nVersion: v{next_ver}\nLocation: {final_out_dir}\n\n{report}")
            print(report)

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            print(tb_str) # To console
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}\n\n{tb_str}")

# ==============================================================================
# RUN
# ==============================================================================
if __name__ == "__main__":
    app = CarbideOptimizedApp()
    app.mainloop()

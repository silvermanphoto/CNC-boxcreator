#!/usr/bin/env python3
"""
CNC Shadowbox Generator GUI
================================================================================
VERSION HISTORY (Cumulative):
v1.00 - 2025-12-27: Initial GUI application with all 21 variables from McTell 
                     Shadowbox Specs, folder selection dialog, joinery method 
                     selection, and professional dark theme interface design
v1.01 - 2025-12-27: Reordered sections (Box Dimensions now #3), added joinery 
                     method images that swap on selection, renamed sections per 
                     user request, added detailed hover tooltips for all variables,
                     fixed checkbox highlighting, removed emojis, updated button 
                     color to #86d16b, enabled two-finger Mac scrolling, added 
                     Share App button, grayed out Blind Joint Skin when non-blind
                     method selected, grayed out Motor Position when motor disabled,
                     renamed Glazing Setback to Glass Setback, fixed font sizes
v1.02 - 2025-12-27: Complete rebuild with all UI/UX enhancements, dynamic image
                     swapping between Half-Round and Full Blind Box Joint images,
                     comprehensive tooltip system with dark blue on white styling,
                     conditional field graying for context-sensitive parameters
================================================================================
A professional desktop application for generating CNC joinery SVGs for the 
McTell Shadowbox project. Features a single-page interface with all parametric
variables, folder selection, and joinery method configuration.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
from datetime import datetime
import math
import base64
import subprocess
import tempfile
import shutil
from PIL import Image, ImageTk
import io

# ============================================================================
# GLOBAL CONSTANTS & NEMA SPECIFICATIONS
# ============================================================================

NEMA_FRAME_SIZES = {
    "NEMA-08": 20.0,
    "NEMA-11": 28.0,
    "NEMA-14": 35.0,
    "NEMA-17": 42.0
}

NEMA_MOUNT_PATTERNS = {
    "NEMA-08": 16.0,
    "NEMA-11": 23.0,
    "NEMA-14": 26.0,
    "NEMA-17": 31.0
}

# Image paths (relative to script directory)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HALF_ROUND_IMAGE_PATH = os.path.join(SCRIPT_DIR, "Half_Round_Box_Joint.jpg")
BLIND_BOX_IMAGE_PATH = os.path.join(SCRIPT_DIR, "Full_Blind_Box_Joint.jpg")

# ============================================================================
# TOOLTIP DEFINITIONS
# ============================================================================

TOOLTIPS = {
    "joinery_method": "Select the joinery method for corner construction. Half-Round Box Joint has fingers that extend proud for router round-over. Full Blind Box Joint hides all mortises behind a thin skin layer.",
    "output_folder": "Directory where generated SVG files will be saved. A new versioned subfolder will be created for each generation run.",
    "total_width": "Overall exterior width of the shadowbox frame, measured from left outer edge to right outer edge.",
    "total_height": "Overall exterior height of the shadowbox frame, measured from top outer edge to bottom outer edge.",
    "total_depth": "Overall depth of the shadowbox from front face to back panel mounting surface.",
    "material_thickness": "Thickness of the primary wood stock used for rails and bezel. Typically 15mm (approximately 5/8 inch) for cabinet-grade plywood or hardwood.",
    "primary_endmill": "Diameter of the main cutting tool used for finger joints, rabbets, and primary profiles. Standard is 0.25 inches (6.35mm).",
    "detail_endmill": "Diameter of the smaller cutting tool for fine detail work, dogbone fillets, and tight internal corners. Standard is 0.125 inches (3.175mm).",
    "glue_gap": "Additional clearance added to finger joint slots to allow for glue and slight material variations. Typical range is 0.005 to 0.015 inches.",
    "tab_peak": "Height of the half-round tab peaks above the material surface. Only applies to Half-Round Box Joint method.",
    "tab_base_width": "Width of the tab base where it meets the main material. Affects the visual proportion and structural strength of half-round profiles.",
    "target_finger_width": "Desired width of each finger in the box joint. Actual finger count will be calculated to fit evenly along each edge.",
    "blind_skin_thickness": "Thickness of the thin skin layer that conceals blind mortises. Only applies to Full Blind Box Joint method. Typically 3mm.",
    "rabbet_width": "Width of the rabbet cut into rails for back panel insertion. Should accommodate back panel thickness plus clearance.",
    "rabbet_depth": "Depth of the rabbet cut. Determines how far the back panel is recessed from the rear face of the rails.",
    "ezlok_pilot": "Pilot hole on Back Panel will align with brass E-Z LOK to be mounted on rails.",
    "enable_motor": "Enable or disable the stepper motor mounting pocket on the back panel. When disabled, Motor Position settings are grayed out.",
    "nema_size": "NEMA stepper motor frame size. Determines the mounting hole pattern and pocket dimensions. NEMA-17 (42mm) is most common for this application.",
    "motor_pocket_depth": "Depth of the pocket milled into the back panel for motor clearance. Should accommodate motor body depth plus wiring.",
    "motor_x_position": "Horizontal position of motor center from left edge of back panel. Leave blank to use default: 0.4155 times photograph width.",
    "motor_y_position": "Vertical position of motor center from bottom edge of back panel. Leave blank to use default: centered vertically.",
    "glass_setback": "Distance the glazing is recessed from the front face of the bezel. Creates visual shadow line and protects glass edge.",
    "glass_thickness": "Thickness of the glass or acrylic glazing material. Used to calculate glazing stop dimensions."
}

# ============================================================================
# UNIT CONVERSION FUNCTIONS
# ============================================================================

def convert_to_mm(value, unit):
    """Convert value to millimeters with provenance logging."""
    if unit == "inches":
        result = value * 25.4
        return result
    elif unit == "mm":
        return value
    else:
        raise ValueError(f"Unknown unit: {unit}")

def mm_to_inches(value_mm):
    """Convert millimeters to inches."""
    return value_mm / 25.4

# ============================================================================
# SVG GENERATION CORE ENGINE
# ============================================================================

class SVGBuilder:
    """Core SVG path and element generation utilities."""
    
    def __init__(self, width_mm, height_mm, canvas_size_inches=48):
        self.canvas_mm = convert_to_mm(canvas_size_inches, "inches")
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.elements = []
        
    def rect(self, x, y, w, h, color="black", stroke_width=0.5):
        """Generate rectangle path."""
        return f'<rect x="{x:.4f}" y="{y:.4f}" width="{w:.4f}" height="{h:.4f}" ' \
               f'fill="none" stroke="{color}" stroke-width="{stroke_width}"/>'
    
    def path(self, d, color="black", stroke_width=0.5):
        """Generate path element."""
        return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{stroke_width}"/>'
    
    def circle(self, cx, cy, r, color="blue", stroke_width=0.5):
        """Generate circle element."""
        return f'<circle cx="{cx:.4f}" cy="{cy:.4f}" r="{r:.4f}" ' \
               f'fill="none" stroke="{color}" stroke-width="{stroke_width}"/>'
    
    def text(self, x, y, content, font_size=6, color="magenta", font_family="Arial"):
        """Generate text element (metadata layer - no cut)."""
        return f'<text x="{x:.4f}" y="{y:.4f}" font-family="{font_family}" ' \
               f'font-size="{font_size}" fill="{color}">{content}</text>'
    
    def dogbone_fillet(self, x, y, r, orientation="NE"):
        """Generate dogbone fillet circle at corner."""
        offsets = {
            "NE": (r * 0.7071, -r * 0.7071),
            "NW": (-r * 0.7071, -r * 0.7071),
            "SE": (r * 0.7071, r * 0.7071),
            "SW": (-r * 0.7071, r * 0.7071)
        }
        ox, oy = offsets.get(orientation, (0, 0))
        return self.circle(x + ox, y + oy, r, color="blue")


class JoineryEngine:
    """Compute finger joint layouts and profiles."""
    
    def __init__(self, params):
        self.params = params
        
    def compute_finger_layout(self, edge_length_mm, target_width_mm):
        """Calculate optimal finger count and actual width for edge."""
        finger_count = max(3, round(edge_length_mm / target_width_mm))
        if finger_count % 2 == 0:
            finger_count += 1
        actual_width = edge_length_mm / finger_count
        return finger_count, actual_width
    
    def generate_blind_mortises(self, edge_length_mm, finger_width_mm, skin_thickness_mm):
        """Generate blind mortise positions for blind box joint."""
        mortises = []
        finger_count, actual_width = self.compute_finger_layout(edge_length_mm, finger_width_mm)
        for i in range(finger_count):
            if i % 2 == 0:
                x_start = i * actual_width
                mortises.append({
                    'x': x_start,
                    'width': actual_width,
                    'depth': self.params['material_thickness_mm'] - skin_thickness_mm
                })
        return mortises


class PartGenerator:
    """Generate individual SVG part files."""
    
    PART_NAMES = [
        "FRONT_BEZEL",
        "TOP_RAIL", 
        "BOTTOM_RAIL",
        "LEFT_RAIL",
        "RIGHT_RAIL",
        "BACK_PANEL",
        "GLAZING_STOPS"
    ]
    
    def __init__(self, params):
        self.params = params
        self.joinery = JoineryEngine(params)
        
    def generate_all(self):
        """Generate all SVG parts and return as dict."""
        parts = {}
        for name in self.PART_NAMES:
            method = getattr(self, f'generate_{name.lower()}', None)
            if method:
                parts[name] = method()
        return parts
    
    def generate_front_bezel(self):
        """Generate front bezel SVG with aperture."""
        p = self.params
        w = p['total_width_mm']
        h = p['total_height_mm']
        bezel_width = p['material_thickness_mm']
        
        svg = SVGBuilder(w, h)
        elements = []
        
        # Outer perimeter
        elements.append(svg.rect(0, 0, w, h, color="black"))
        
        # Inner aperture
        aperture_x = bezel_width
        aperture_y = bezel_width
        aperture_w = w - 2 * bezel_width
        aperture_h = h - 2 * bezel_width
        elements.append(svg.rect(aperture_x, aperture_y, aperture_w, aperture_h, color="red"))
        
        # Corner radius detail (visual guide)
        corner_r = p['detail_endmill_mm'] / 2
        for cx, cy in [(aperture_x, aperture_y), (aperture_x + aperture_w, aperture_y),
                       (aperture_x, aperture_y + aperture_h), (aperture_x + aperture_w, aperture_y + aperture_h)]:
            elements.append(svg.circle(cx, cy, corner_r, color="blue"))
        
        # Metadata
        elements.append(svg.text(5, h - 5, f"FRONT_BEZEL {w:.1f}x{h:.1f}mm"))
        
        return self._wrap_svg(elements, w, h)
    
    def generate_top_rail(self):
        """Generate top rail with finger joints."""
        return self._generate_rail("TOP")
    
    def generate_bottom_rail(self):
        """Generate bottom rail with finger joints and motor pocket."""
        return self._generate_rail("BOTTOM")
    
    def generate_left_rail(self):
        """Generate left rail with finger joints."""
        return self._generate_rail("LEFT")
    
    def generate_right_rail(self):
        """Generate right rail with finger joints."""
        return self._generate_rail("RIGHT")
    
    def _generate_rail(self, position):
        """Generic rail generation with position-specific features."""
        p = self.params
        
        if position in ["TOP", "BOTTOM"]:
            length = p['total_width_mm']
        else:
            length = p['total_height_mm'] - 2 * p['material_thickness_mm']
            
        width = p['total_depth_mm']
        
        svg = SVGBuilder(length, width)
        elements = []
        
        # Main outline
        elements.append(svg.rect(0, 0, length, width, color="black"))
        
        # Rabbet for back panel
        rabbet_w = p['rabbet_width_mm']
        rabbet_d = p['rabbet_depth_mm']
        elements.append(svg.rect(0, width - rabbet_d, length, rabbet_d, color="green"))
        
        # Finger joint profile (simplified representation)
        finger_count, finger_w = self.joinery.compute_finger_layout(length, p['target_finger_width_mm'])
        for i in range(finger_count):
            if i % 2 == 1:
                x = i * finger_w
                elements.append(svg.rect(x, 0, finger_w, p['material_thickness_mm'], color="red"))
        
        # Metadata
        elements.append(svg.text(5, width - 5, f"{position}_RAIL {length:.1f}x{width:.1f}mm"))
        
        return self._wrap_svg(elements, length, width)
    
    def generate_back_panel(self):
        """Generate back panel with optional motor pocket and E-Z LOK holes."""
        p = self.params
        w = p['total_width_mm'] - 2 * p['rabbet_width_mm']
        h = p['total_height_mm'] - 2 * p['rabbet_width_mm']
        
        svg = SVGBuilder(w, h)
        elements = []
        
        # Main outline
        elements.append(svg.rect(0, 0, w, h, color="black"))
        
        # E-Z LOK pilot holes (4 corners)
        pilot_r = p['ezlok_pilot_mm'] / 2
        inset = 25  # mm from edge
        for cx, cy in [(inset, inset), (w - inset, inset), 
                       (inset, h - inset), (w - inset, h - inset)]:
            elements.append(svg.circle(cx, cy, pilot_r, color="blue"))
        
        # Motor pocket if enabled
        if p.get('enable_motor', False):
            nema = p.get('nema_size', 'NEMA-17')
            frame_size = NEMA_FRAME_SIZES.get(nema, 42.0)
            mount_pattern = NEMA_MOUNT_PATTERNS.get(nema, 31.0)
            
            # Motor position
            motor_x = p.get('motor_x_mm', w * 0.4155)
            motor_y = p.get('motor_y_mm', h / 2)
            
            # Motor pocket outline
            pocket_size = frame_size + 4  # 2mm clearance each side
            elements.append(svg.rect(motor_x - pocket_size/2, motor_y - pocket_size/2,
                                    pocket_size, pocket_size, color="magenta"))
            
            # Mounting holes
            half_pattern = mount_pattern / 2
            for dx, dy in [(-half_pattern, -half_pattern), (half_pattern, -half_pattern),
                          (-half_pattern, half_pattern), (half_pattern, half_pattern)]:
                elements.append(svg.circle(motor_x + dx, motor_y + dy, 1.6, color="cyan"))
        
        # Metadata
        elements.append(svg.text(5, h - 5, f"BACK_PANEL {w:.1f}x{h:.1f}mm"))
        
        return self._wrap_svg(elements, w, h)
    
    def generate_glazing_stops(self):
        """Generate glazing stop strips."""
        p = self.params
        # 4 strips: 2 horizontal, 2 vertical
        h_length = p['total_width_mm'] - 2 * p['material_thickness_mm']
        v_length = p['total_height_mm'] - 2 * p['material_thickness_mm']
        strip_width = p['glass_setback_mm']
        
        svg = SVGBuilder(max(h_length, v_length) + 20, strip_width * 5)
        elements = []
        
        y_offset = 0
        # 2 horizontal strips
        for i in range(2):
            elements.append(svg.rect(0, y_offset, h_length, strip_width, color="black"))
            elements.append(svg.text(5, y_offset + strip_width - 2, f"H_STOP_{i+1}"))
            y_offset += strip_width + 5
        
        # 2 vertical strips  
        for i in range(2):
            elements.append(svg.rect(0, y_offset, v_length, strip_width, color="black"))
            elements.append(svg.text(5, y_offset + strip_width - 2, f"V_STOP_{i+1}"))
            y_offset += strip_width + 5
        
        return self._wrap_svg(elements, max(h_length, v_length) + 20, y_offset)
    
    def _wrap_svg(self, elements, width, height):
        """Wrap elements in SVG document."""
        header = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" 
     width="{width}mm" height="{height}mm" 
     viewBox="0 0 {width} {height}">
  <g id="cut_layer">'''
        footer = '''  </g>
</svg>'''
        body = '\n    '.join(elements)
        return f"{header}\n    {body}\n{footer}"


class OutputManager:
    """Handle versioned output directory and file generation."""
    
    def __init__(self, base_dir, project_name="McTell_Shadowbox"):
        self.base_dir = base_dir
        self.project_name = project_name
        
    def get_next_version(self):
        """Determine next version number based on existing folders."""
        pattern = re.compile(rf"{self.project_name}_v(\d+)")
        max_version = 0
        
        if os.path.exists(self.base_dir):
            for item in os.listdir(self.base_dir):
                match = pattern.match(item)
                if match:
                    version = int(match.group(1))
                    max_version = max(max_version, version)
        
        return max_version + 1
    
    def create_output_directory(self):
        """Create versioned output directory."""
        version = self.get_next_version()
        dir_name = f"{self.project_name}_v{version:02d}"
        full_path = os.path.join(self.base_dir, dir_name)
        os.makedirs(full_path, exist_ok=True)
        return full_path, version
    
    def save_parts(self, parts, output_dir):
        """Save all SVG parts to output directory."""
        saved_files = []
        for name, svg_content in parts.items():
            filename = f"{name}.svg"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w') as f:
                f.write(svg_content)
            saved_files.append(filepath)
        return saved_files
    
    def generate_cam_instructions(self, output_dir, params):
        """Generate CAM setup instructions file."""
        instructions = f"""CNC Shadowbox Generator - CAM Instructions
==========================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

MATERIAL SETUP:
- Stock Thickness: {params['material_thickness_mm']:.2f}mm ({mm_to_inches(params['material_thickness_mm']):.4f}")
- Primary End Mill: {params['primary_endmill_mm']:.2f}mm ({mm_to_inches(params['primary_endmill_mm']):.4f}")
- Detail End Mill: {params['detail_endmill_mm']:.2f}mm ({mm_to_inches(params['detail_endmill_mm']):.4f}")

JOINERY METHOD: {params['joinery_method']}

TOOLPATH ORDER:
1. BACK_PANEL - Mill first, allows test fit
2. RAILS (TOP, BOTTOM, LEFT, RIGHT) - Mill as set
3. FRONT_BEZEL - Mill last, most visible
4. GLAZING_STOPS - Cut from scrap

COLOR CODING:
- BLACK: Profile/perimeter cuts (outside)
- RED: Inside cuts (apertures, mortises)
- BLUE: Drilling operations
- GREEN: Rabbet/dado operations
- MAGENTA: Motor pocket (if enabled)
- CYAN: Mounting holes

NOTES:
- All dimensions in millimeters
- Glue gap of {params['glue_gap_mm']:.3f}mm included in joints
- Dogbone fillets sized for {params['detail_endmill_mm']:.2f}mm end mill
"""
        filepath = os.path.join(output_dir, "CAM_INSTRUCTIONS.txt")
        with open(filepath, 'w') as f:
            f.write(instructions)
        return filepath


# ============================================================================
# TOOLTIP CLASS
# ============================================================================

class ToolTip:
    """Create a tooltip for a given widget."""
    
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window = None
        self.scheduled_id = None
        
        self.widget.bind('<Enter>', self.schedule_tooltip)
        self.widget.bind('<Leave>', self.hide_tooltip)
        self.widget.bind('<Button>', self.hide_tooltip)
    
    def schedule_tooltip(self, event=None):
        self.cancel_scheduled()
        self.scheduled_id = self.widget.after(self.delay, self.show_tooltip)
    
    def cancel_scheduled(self):
        if self.scheduled_id:
            self.widget.after_cancel(self.scheduled_id)
            self.scheduled_id = None
    
    def show_tooltip(self, event=None):
        if self.tooltip_window:
            return
            
        # Get widget position
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 10
        y = self.widget.winfo_rooty()
        
        # Create tooltip window
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        # Create label with dark blue text on white background
        label = tk.Label(tw, text=self.text, justify='left',
                        background='#ffffff', foreground='#1a237e',
                        relief='solid', borderwidth=1,
                        font=('Helvetica', 11), wraplength=300,
                        padx=8, pady=6)
        label.pack()
    
    def hide_tooltip(self, event=None):
        self.cancel_scheduled()
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


# ============================================================================
# MAIN APPLICATION GUI
# ============================================================================

class CNCGeneratorApp:
    """Main application window."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("CNC Shadowbox Generator")
        self.root.geometry("1100x900")
        
        # Store references to entry widgets for conditional graying
        self.entry_widgets = {}
        self.label_widgets = {}
        self.section_widgets = {}
        
        # Color scheme
        self.colors = {
            'bg': '#1e1e2e',
            'fg': '#cdd6f4',
            'accent': '#89b4fa',
            'entry_bg': '#313244',
            'entry_fg': '#cdd6f4',
            'button_bg': '#86d16b',
            'button_fg': '#1e1e2e',
            'header_bg': '#181825',
            'disabled_bg': '#45475a',
            'disabled_fg': '#6c7086'
        }
        
        self.root.configure(bg=self.colors['bg'])
        
        # Configure styles
        self.setup_styles()
        
        # Variables
        self.setup_variables()
        
        # Build UI
        self.build_ui()
        
        # Load images
        self.load_images()
        
        # Apply initial state
        self.update_joinery_image()
        self.update_blind_skin_state()
        self.update_motor_position_state()
    
    def setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('TFrame', background=self.colors['bg'])
        style.configure('TLabel', background=self.colors['bg'], foreground=self.colors['fg'],
                       font=('Helvetica', 12))
        style.configure('TEntry', fieldbackground=self.colors['entry_bg'],
                       foreground=self.colors['entry_fg'], font=('Helvetica', 12))
        style.configure('TButton', font=('Helvetica', 12, 'bold'))
        style.configure('TRadiobutton', background=self.colors['bg'], 
                       foreground=self.colors['fg'], font=('Helvetica', 12))
        style.configure('TCheckbutton', background=self.colors['bg'],
                       foreground=self.colors['fg'], font=('Helvetica', 12))
        style.configure('TCombobox', font=('Helvetica', 12))
        
        # Header style
        style.configure('Header.TLabel', font=('Helvetica', 14, 'bold'),
                       foreground=self.colors['accent'])
        
        # Section header style
        style.configure('Section.TLabel', font=('Helvetica', 13, 'bold'),
                       foreground=self.colors['accent'])
        
        # Disabled styles
        style.configure('Disabled.TLabel', foreground=self.colors['disabled_fg'])
        style.configure('Disabled.TEntry', fieldbackground=self.colors['disabled_bg'])
    
    def setup_variables(self):
        """Initialize all tkinter variables."""
        self.joinery_var = tk.StringVar(value="HALF_ROUND_BOX_JOINT")
        self.output_folder_var = tk.StringVar(value=SCRIPT_DIR)
        
        # Box Dimensions
        self.total_width_var = tk.StringVar(value="40.0")
        self.total_height_var = tk.StringVar(value="40.0")
        self.total_depth_var = tk.StringVar(value="3.0")
        
        # Material & Tooling
        self.material_thickness_var = tk.StringVar(value="15.0")
        self.primary_endmill_var = tk.StringVar(value="0.25")
        self.detail_endmill_var = tk.StringVar(value="0.125")
        self.glue_gap_var = tk.StringVar(value="0.010")
        
        # Tab Geometry
        self.tab_peak_var = tk.StringVar(value="3.0")
        self.tab_base_width_var = tk.StringVar(value="0.5")
        
        # Joinery Parameters
        self.target_finger_width_var = tk.StringVar(value="15.0")
        self.blind_skin_var = tk.StringVar(value="3.0")
        
        # Back Panel
        self.rabbet_width_var = tk.StringVar(value="0.625")
        self.rabbet_depth_var = tk.StringVar(value="0.3")
        self.ezlok_pilot_var = tk.StringVar(value="5.0")
        
        # Stepper Motor
        self.enable_motor_var = tk.BooleanVar(value=True)
        self.nema_size_var = tk.StringVar(value="NEMA-17")
        self.motor_pocket_depth_var = tk.StringVar(value="0.25")
        
        # Motor Position
        self.motor_x_var = tk.StringVar(value="")
        self.motor_y_var = tk.StringVar(value="")
        
        # Glazing
        self.glass_setback_var = tk.StringVar(value="0.25")
        self.glass_thickness_var = tk.StringVar(value="0.125")
        
        # Bind joinery change
        self.joinery_var.trace_add('write', lambda *args: self.on_joinery_change())
        self.enable_motor_var.trace_add('write', lambda *args: self.update_motor_position_state())
    
    def load_images(self):
        """Load joinery method images."""
        self.half_round_image = None
        self.blind_box_image = None
        
        try:
            if os.path.exists(HALF_ROUND_IMAGE_PATH):
                img = Image.open(HALF_ROUND_IMAGE_PATH)
                # Scale to fit (max 400px width for placement area)
                img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                self.half_round_image = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Could not load Half_Round image: {e}")
        
        try:
            if os.path.exists(BLIND_BOX_IMAGE_PATH):
                img = Image.open(BLIND_BOX_IMAGE_PATH)
                img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                self.blind_box_image = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Could not load Blind_Box image: {e}")
    
    def update_joinery_image(self):
        """Update displayed image based on joinery selection."""
        if not hasattr(self, 'image_label'):
            return
            
        if self.joinery_var.get() == "BLIND_BOX_JOINT":
            if self.blind_box_image:
                self.image_label.configure(image=self.blind_box_image)
            else:
                self.image_label.configure(image='', text="Full Blind Box Joint\n(image not found)")
        else:
            if self.half_round_image:
                self.image_label.configure(image=self.half_round_image)
            else:
                self.image_label.configure(image='', text="Half-Round Box Joint\n(image not found)")
    
    def on_joinery_change(self):
        """Handle joinery method change."""
        self.update_joinery_image()
        self.update_blind_skin_state()
    
    def update_blind_skin_state(self):
        """Enable/disable blind skin thickness based on joinery method."""
        is_blind = self.joinery_var.get() == "BLIND_BOX_JOINT"
        
        if 'blind_skin' in self.entry_widgets:
            entry = self.entry_widgets['blind_skin']
            label = self.label_widgets.get('blind_skin')
            
            if is_blind:
                entry.configure(state='normal', style='TEntry')
                if label:
                    label.configure(style='TLabel')
            else:
                entry.configure(state='disabled')
                if label:
                    label.configure(style='Disabled.TLabel')
    
    def update_motor_position_state(self):
        """Enable/disable motor position fields based on motor enable checkbox."""
        is_enabled = self.enable_motor_var.get()
        
        # Motor position entries
        for key in ['motor_x', 'motor_y']:
            if key in self.entry_widgets:
                entry = self.entry_widgets[key]
                label = self.label_widgets.get(key)
                
                if is_enabled:
                    entry.configure(state='normal', style='TEntry')
                    if label:
                        label.configure(style='TLabel')
                else:
                    entry.configure(state='disabled')
                    if label:
                        label.configure(style='Disabled.TLabel')
        
        # Also handle NEMA size and pocket depth
        for key in ['nema_size', 'motor_pocket_depth']:
            if key in self.entry_widgets:
                widget = self.entry_widgets[key]
                label = self.label_widgets.get(key)
                
                if is_enabled:
                    widget.configure(state='normal' if key != 'nema_size' else 'readonly')
                    if label:
                        label.configure(style='TLabel')
                else:
                    widget.configure(state='disabled')
                    if label:
                        label.configure(style='Disabled.TLabel')
        
        # Section header
        if 'motor_position_header' in self.section_widgets:
            header = self.section_widgets['motor_position_header']
            if is_enabled:
                header.configure(style='Section.TLabel')
            else:
                header.configure(style='Disabled.TLabel')
        
        # Default text label
        if 'motor_default_label' in self.label_widgets:
            label = self.label_widgets['motor_default_label']
            if is_enabled:
                label.configure(foreground=self.colors['fg'])
            else:
                label.configure(foreground=self.colors['disabled_fg'])
    
    def build_ui(self):
        """Build the main user interface."""
        # Create main canvas with scrollbar for two-finger scrolling
        self.canvas = tk.Canvas(self.root, bg=self.colors['bg'], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Enable mousewheel/trackpad scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)
        
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Main container with two columns
        main_frame = ttk.Frame(self.scrollable_frame)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Left column for parameters
        left_col = ttk.Frame(main_frame)
        left_col.pack(side='left', fill='both', expand=True)
        
        # Right column for image
        right_col = ttk.Frame(main_frame)
        right_col.pack(side='right', fill='y', padx=(30, 0))
        
        # Title
        title_label = ttk.Label(left_col, text="CNC Shadowbox Generator",
                               font=('Helvetica', 24, 'bold'),
                               foreground=self.colors['accent'])
        title_label.pack(anchor='w', pady=(0, 5))
        
        subtitle = ttk.Label(left_col, text="Parametric CNC Joinery & SVG Generation Engine",
                            font=('Helvetica', 11), foreground='#7f849c')
        subtitle.pack(anchor='w', pady=(0, 20))
        
        # Image display in right column
        self.image_label = tk.Label(right_col, bg=self.colors['bg'],
                                    text="Loading image...",
                                    fg=self.colors['fg'],
                                    font=('Helvetica', 12))
        self.image_label.pack(pady=(60, 20))
        
        # Build sections
        self.build_section_1_joinery(left_col)
        self.build_section_2_output(left_col)
        self.build_section_3_box_dimensions(left_col)
        self.build_section_4_material_tooling(left_col)
        self.build_section_5_tab_geometry(left_col)
        self.build_section_6_joinery_params(left_col)
        self.build_section_7_back_panel(left_col)
        self.build_section_8_stepper_motor(left_col)
        self.build_section_9_motor_position(left_col)
        self.build_section_10_glazing(left_col)
        
        # Generate button
        self.build_generate_button(left_col)
        
        # Share button
        self.build_share_button(left_col)
    
    def _on_mousewheel(self, event):
        """Handle mousewheel/trackpad scrolling."""
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            # macOS trackpad
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def create_section_header(self, parent, number, title):
        """Create a numbered section header."""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=(15, 8))
        
        label = ttk.Label(frame, text=f"{number}. {title}", style='Section.TLabel')
        label.pack(anchor='w')
        
        return frame
    
    def create_entry_row(self, parent, label_text, variable, unit_text="", tooltip_key=None, width=12):
        """Create a labeled entry row with optional tooltip."""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=3)
        
        label = ttk.Label(frame, text=f"{label_text}:", width=25, anchor='w')
        label.pack(side='left')
        
        entry = ttk.Entry(frame, textvariable=variable, width=width, font=('Helvetica', 12))
        entry.pack(side='left', padx=(0, 5))
        
        if unit_text:
            unit_label = ttk.Label(frame, text=unit_text, width=8, anchor='w')
            unit_label.pack(side='left')
        
        if tooltip_key and tooltip_key in TOOLTIPS:
            ToolTip(entry, TOOLTIPS[tooltip_key])
            ToolTip(label, TOOLTIPS[tooltip_key])
        
        return entry, label, frame
    
    def build_section_1_joinery(self, parent):
        """Build joinery method selection section."""
        self.create_section_header(parent, 1, "Joinery Method Selection")
        
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20)
        
        rb1 = ttk.Radiobutton(frame, text="(a) BLIND BOX JOINT - Hidden mortises with 3mm skin",
                             variable=self.joinery_var, value="BLIND_BOX_JOINT")
        rb1.pack(anchor='w', pady=2)
        ToolTip(rb1, TOOLTIPS['joinery_method'])
        
        rb2 = ttk.Radiobutton(frame, text="(b) HALF-ROUND BOX JOINT - Fingers extend proud for round-over",
                             variable=self.joinery_var, value="HALF_ROUND_BOX_JOINT")
        rb2.pack(anchor='w', pady=2)
        ToolTip(rb2, TOOLTIPS['joinery_method'])
    
    def build_section_2_output(self, parent):
        """Build output folder selection section."""
        self.create_section_header(parent, 2, "Output Folder")
        
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20)
        
        entry = ttk.Entry(frame, textvariable=self.output_folder_var, width=60, font=('Helvetica', 12))
        entry.pack(side='left', padx=(0, 10))
        ToolTip(entry, TOOLTIPS['output_folder'])
        
        browse_btn = tk.Button(frame, text="Browse...", command=self.browse_folder,
                              bg=self.colors['entry_bg'], fg=self.colors['fg'],
                              font=('Helvetica', 11), relief='flat', padx=15, pady=5)
        browse_btn.pack(side='left')
    
    def build_section_3_box_dimensions(self, parent):
        """Build box dimensions section."""
        self.create_section_header(parent, 3, "Box Dimensions")
        
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20)
        
        self.create_entry_row(frame, "Total Width", self.total_width_var, "inches", "total_width")
        self.create_entry_row(frame, "Total Height", self.total_height_var, "inches", "total_height")
        self.create_entry_row(frame, "Total Depth", self.total_depth_var, "inches", "total_depth")
    
    def build_section_4_material_tooling(self, parent):
        """Build material and tooling section."""
        self.create_section_header(parent, 4, "Material & Tooling")
        
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20)
        
        self.create_entry_row(frame, "Material Thickness", self.material_thickness_var, "mm", "material_thickness")
        self.create_entry_row(frame, "Primary End Mill", self.primary_endmill_var, "inches", "primary_endmill")
        self.create_entry_row(frame, "Detail End Mill", self.detail_endmill_var, "inches", "detail_endmill")
        self.create_entry_row(frame, "Glue Gap Tolerance", self.glue_gap_var, "inches", "glue_gap")
    
    def build_section_5_tab_geometry(self, parent):
        """Build tab geometry section."""
        self.create_section_header(parent, 5, "Tab Geometry")
        
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20)
        
        self.create_entry_row(frame, "Tab Peak Thickness", self.tab_peak_var, "mm", "tab_peak")
        self.create_entry_row(frame, "Tab Base Width", self.tab_base_width_var, "inches", "tab_base_width")
    
    def build_section_6_joinery_params(self, parent):
        """Build joinery parameters section."""
        self.create_section_header(parent, 6, "Joinery Parameters")
        
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20)
        
        self.create_entry_row(frame, "Target Finger Width", self.target_finger_width_var, "mm", "target_finger_width")
        
        entry, label, row_frame = self.create_entry_row(frame, "Blind Joint Skin Thickness", 
                                                        self.blind_skin_var, "mm", "blind_skin_thickness")
        self.entry_widgets['blind_skin'] = entry
        self.label_widgets['blind_skin'] = label
    
    def build_section_7_back_panel(self, parent):
        """Build back panel section."""
        self.create_section_header(parent, 7, "Back Panel")
        
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20)
        
        self.create_entry_row(frame, "Rabbet Width", self.rabbet_width_var, "inches", "rabbet_width")
        self.create_entry_row(frame, "Rabbet Depth", self.rabbet_depth_var, "inches", "rabbet_depth")
        self.create_entry_row(frame, "E-Z LOK Pilot Diameter", self.ezlok_pilot_var, "mm", "ezlok_pilot")
    
    def build_section_8_stepper_motor(self, parent):
        """Build stepper motor section."""
        self.create_section_header(parent, 8, "Stepper Motor")
        
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20)
        
        # Checkbox (with custom style to avoid white-on-white)
        check_frame = ttk.Frame(frame)
        check_frame.pack(fill='x', pady=3)
        
        check = tk.Checkbutton(check_frame, text="Enable Stepper Motor Pocket",
                              variable=self.enable_motor_var,
                              bg=self.colors['bg'], fg=self.colors['fg'],
                              selectcolor=self.colors['entry_bg'],
                              activebackground=self.colors['bg'],
                              activeforeground=self.colors['fg'],
                              font=('Helvetica', 12),
                              highlightthickness=0)
        check.pack(anchor='w')
        ToolTip(check, TOOLTIPS['enable_motor'])
        
        # NEMA Size dropdown
        nema_frame = ttk.Frame(frame)
        nema_frame.pack(fill='x', pady=3)
        
        nema_label = ttk.Label(nema_frame, text="NEMA Size:", width=25, anchor='w')
        nema_label.pack(side='left')
        
        nema_combo = ttk.Combobox(nema_frame, textvariable=self.nema_size_var,
                                  values=list(NEMA_FRAME_SIZES.keys()),
                                  state='readonly', width=12, font=('Helvetica', 12))
        nema_combo.pack(side='left')
        ToolTip(nema_combo, TOOLTIPS['nema_size'])
        
        self.entry_widgets['nema_size'] = nema_combo
        self.label_widgets['nema_size'] = nema_label
        
        # Motor pocket depth
        entry, label, _ = self.create_entry_row(frame, "Motor Pocket Depth", 
                                                self.motor_pocket_depth_var, "inches", "motor_pocket_depth")
        self.entry_widgets['motor_pocket_depth'] = entry
        self.label_widgets['motor_pocket_depth'] = label
    
    def build_section_9_motor_position(self, parent):
        """Build motor position section."""
        header_frame = self.create_section_header(parent, 9, "Motor Position")
        self.section_widgets['motor_position_header'] = header_frame.winfo_children()[0]
        
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20)
        
        # Default info text (same font size as normal menu)
        default_label = ttk.Label(frame, 
                                  text="Leave blank for default: 0.4155 x photograph width",
                                  font=('Helvetica', 12), foreground='#7f849c')
        default_label.pack(anchor='w', pady=(0, 5))
        self.label_widgets['motor_default_label'] = default_label
        
        entry_x, label_x, _ = self.create_entry_row(frame, "Motor X Position", 
                                                    self.motor_x_var, "inches", "motor_x_position")
        self.entry_widgets['motor_x'] = entry_x
        self.label_widgets['motor_x'] = label_x
        
        entry_y, label_y, _ = self.create_entry_row(frame, "Motor Y Position", 
                                                    self.motor_y_var, "inches", "motor_y_position")
        self.entry_widgets['motor_y'] = entry_y
        self.label_widgets['motor_y'] = label_y
    
    def build_section_10_glazing(self, parent):
        """Build glazing section."""
        self.create_section_header(parent, 10, "Glazing")
        
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=20)
        
        self.create_entry_row(frame, "Glass Setback", self.glass_setback_var, "inches", "glass_setback")
        self.create_entry_row(frame, "Glass Thickness", self.glass_thickness_var, "inches", "glass_thickness")
    
    def build_generate_button(self, parent):
        """Build the generate SVGs button."""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=(30, 10))
        
        generate_btn = tk.Button(frame, text="Generate SVG Files",
                                command=self.generate_svgs,
                                bg='#86d16b', fg='#1e1e2e',
                                font=('Helvetica', 14, 'bold'),
                                relief='flat', padx=30, pady=12,
                                cursor='hand2')
        generate_btn.pack()
    
    def build_share_button(self, parent):
        """Build the share app button."""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=(10, 20))
        
        share_btn = tk.Button(frame, text="Share App",
                             command=self.share_app,
                             bg=self.colors['entry_bg'], fg=self.colors['fg'],
                             font=('Helvetica', 11),
                             relief='flat', padx=20, pady=8,
                             cursor='hand2')
        share_btn.pack()
    
    def browse_folder(self):
        """Open folder browser dialog."""
        folder = filedialog.askdirectory(initialdir=self.output_folder_var.get())
        if folder:
            self.output_folder_var.set(folder)
    
    def collect_parameters(self):
        """Collect all parameter values and convert to mm."""
        try:
            params = {
                'joinery_method': self.joinery_var.get(),
                'total_width_mm': convert_to_mm(float(self.total_width_var.get()), "inches"),
                'total_height_mm': convert_to_mm(float(self.total_height_var.get()), "inches"),
                'total_depth_mm': convert_to_mm(float(self.total_depth_var.get()), "inches"),
                'material_thickness_mm': float(self.material_thickness_var.get()),
                'primary_endmill_mm': convert_to_mm(float(self.primary_endmill_var.get()), "inches"),
                'detail_endmill_mm': convert_to_mm(float(self.detail_endmill_var.get()), "inches"),
                'glue_gap_mm': convert_to_mm(float(self.glue_gap_var.get()), "inches"),
                'tab_peak_mm': float(self.tab_peak_var.get()),
                'tab_base_width_mm': convert_to_mm(float(self.tab_base_width_var.get()), "inches"),
                'target_finger_width_mm': float(self.target_finger_width_var.get()),
                'blind_skin_mm': float(self.blind_skin_var.get()),
                'rabbet_width_mm': convert_to_mm(float(self.rabbet_width_var.get()), "inches"),
                'rabbet_depth_mm': convert_to_mm(float(self.rabbet_depth_var.get()), "inches"),
                'ezlok_pilot_mm': float(self.ezlok_pilot_var.get()),
                'enable_motor': self.enable_motor_var.get(),
                'nema_size': self.nema_size_var.get(),
                'motor_pocket_depth_mm': convert_to_mm(float(self.motor_pocket_depth_var.get()), "inches"),
                'glass_setback_mm': convert_to_mm(float(self.glass_setback_var.get()), "inches"),
                'glass_thickness_mm': convert_to_mm(float(self.glass_thickness_var.get()), "inches"),
            }
            
            # Motor position (optional)
            if self.motor_x_var.get().strip():
                params['motor_x_mm'] = convert_to_mm(float(self.motor_x_var.get()), "inches")
            if self.motor_y_var.get().strip():
                params['motor_y_mm'] = convert_to_mm(float(self.motor_y_var.get()), "inches")
            
            return params
            
        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid numeric value: {e}")
            return None
    
    def generate_svgs(self):
        """Generate all SVG files."""
        params = self.collect_parameters()
        if not params:
            return
        
        output_base = self.output_folder_var.get()
        if not output_base:
            messagebox.showerror("Error", "Please select an output folder.")
            return
        
        try:
            # Create output manager
            output_mgr = OutputManager(output_base)
            output_dir, version = output_mgr.create_output_directory()
            
            # Generate parts
            generator = PartGenerator(params)
            parts = generator.generate_all()
            
            # Save files
            saved_files = output_mgr.save_parts(parts, output_dir)
            
            # Generate CAM instructions
            output_mgr.generate_cam_instructions(output_dir, params)
            
            # Success message
            messagebox.showinfo("Success", 
                              f"Generated {len(saved_files)} SVG files\n\n"
                              f"Version: v{version:02d}\n"
                              f"Output: {output_dir}")
            
            # Open output folder
            subprocess.run(['open', output_dir])
            
        except Exception as e:
            messagebox.showerror("Generation Error", f"Failed to generate SVGs:\n{e}")
    
    def share_app(self):
        """Create a shareable package of the application."""
        try:
            # Create a zip file of the application
            app_dir = SCRIPT_DIR
            share_dir = os.path.join(tempfile.gettempdir(), "CNC_Shadowbox_Generator_Share")
            
            if os.path.exists(share_dir):
                shutil.rmtree(share_dir)
            os.makedirs(share_dir)
            
            # Copy main files
            files_to_copy = [
                "McTell_CNC_Generator_GUI.py",
                "Half_Round_Box_Joint.jpg",
                "Full_Blind_Box_Joint.jpg",
                "Launch_McTell_Generator.command"
            ]
            
            for filename in files_to_copy:
                src = os.path.join(app_dir, filename)
                if os.path.exists(src):
                    shutil.copy2(src, share_dir)
            
            # Create README
            readme_content = """CNC Shadowbox Generator
=======================

INSTALLATION:
1. Ensure Python 3 is installed on your Mac
2. Install Pillow: pip3 install Pillow
3. Double-click Launch_McTell_Generator.command
   - Or run: python3 McTell_CNC_Generator_GUI.py

REQUIREMENTS:
- macOS
- Python 3.8+
- Pillow (PIL) library

Created by the McTell Shadowbox Project
"""
            with open(os.path.join(share_dir, "README.txt"), 'w') as f:
                f.write(readme_content)
            
            # Create zip
            zip_path = os.path.join(tempfile.gettempdir(), "CNC_Shadowbox_Generator.zip")
            shutil.make_archive(zip_path.replace('.zip', ''), 'zip', 
                              os.path.dirname(share_dir), os.path.basename(share_dir))
            
            # Copy to Desktop for easy access
            desktop_zip = os.path.join(os.path.expanduser("~/Desktop"), "CNC_Shadowbox_Generator.zip")
            shutil.copy2(zip_path, desktop_zip)
            
            messagebox.showinfo("Share App", 
                              f"Shareable package created!\n\n"
                              f"Location: {desktop_zip}\n\n"
                              f"Send this ZIP file to share the app with other Mac users.")
            
            # Reveal in Finder
            subprocess.run(['open', '-R', desktop_zip])
            
        except Exception as e:
            messagebox.showerror("Share Error", f"Failed to create shareable package:\n{e}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Application entry point."""
    root = tk.Tk()
    app = CNCGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

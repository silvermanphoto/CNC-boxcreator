#!/usr/bin/env python3
"""
5x5 Baltic Birch Nesting Generator v7
- EXPLODED: No groups. Flat list of elements.
- STYLE MATCH:
    - Blue Fill (Part)
    - Black Stroke (Profile)
    - RED CUT BOX (Expanded by 0.3" tab height, matching your snippet)
    - Magenta Tabs
- FONTS: Josefin Sans (80pt / 40pt)
"""

def generate_5x5_layout_v7(filename="Layout_5x5_BalticBirch_v7.svg"):
    # --- CONFIGURATION ---
    sheet_w, sheet_h = 60, 60
    safe_margin = 2.0
    gap_between_sheets = 5
    
    # Part Dimensions
    panel_size = 40
    rail_len = 40
    rail_w = 4
    strip_len = 40
    strip_w = 0.75
    
    # Colors
    col_sheet = "#e3d2b4" 
    col_part_fill = "#d1e8ff"
    col_profile_stroke = "#000000" # Black Profile
    col_cut_box = "#FF0000"        # Red Cut Box (Expanded)
    col_tab = "#FF00FF"            # Magenta
    
    # Stroke: 1pt = 1/72 inch
    stroke_width = 0.013888 
    
    # Fonts (Josefin Sans)
    font_family = "JosefinSans-Regular, Josefin Sans, sans-serif"
    # Font sizes in inches (approx 80pt and 40pt)
    sz_std_inch = 80/72.0
    sz_glz_inch = 40/72.0
    
    # Tab Config
    tab_base = 0.5
    tab_h = 0.3 # Red box will be expanded by this amount

    # --- HELPERS (ABSOLUTE COORDINATES) ---

    def get_abs_tabs(px, py, w, h):
        """Generates ungrouped triangular tab polygons."""
        tabs = []
        def make_tri(cx, cy, direction):
            acx, acy = px + cx, py + cy
            if direction == 'UP': pts = f'{acx-tab_base/2},{acy} {acx+tab_base/2},{acy} {acx},{acy-tab_h}'
            elif direction == 'DOWN': pts = f'{acx-tab_base/2},{acy} {acx+tab_base/2},{acy} {acx},{acy+tab_h}'
            elif direction == 'LEFT': pts = f'{acx},{acy-tab_base/2} {acx},{acy+tab_base/2} {acx-tab_h},{acy}'
            elif direction == 'RIGHT': pts = f'{acx},{acy-tab_base/2} {acx},{acy+tab_base/2} {acx+tab_h},{acy}'
            return f'<polygon points="{pts}" fill="{col_tab}" stroke="none" opacity="0.9"/>'

        # Top/Bottom
        if w > 5:
            for x_pct in [0.20, 0.80]:
                tabs.append(make_tri(w*x_pct, 0, 'UP'))
                tabs.append(make_tri(w*x_pct, h, 'DOWN'))
        else:
             tabs.append(make_tri(w/2, 0, 'UP'))
             tabs.append(make_tri(w/2, h, 'DOWN'))

        # Left/Right
        if h > 5:
            for y_pct in [0.20, 0.80]:
                tabs.append(make_tri(0, h*y_pct, 'LEFT'))
                tabs.append(make_tri(w, h*y_pct, 'RIGHT'))
        
        return "\n".join(tabs)

    def create_exploded_part(label, x, y, w, h, is_waste=False):
        """Returns raw SVG strings with absolute positioning."""
        elements = []
        
        # 1. Fill (Blue)
        elements.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{col_part_fill}" stroke="none" />')
        
        # 2. Profile Stroke (Black) - The Part Dimension
        elements.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{col_profile_stroke}" stroke-width="{stroke_width}" />')
        
        # 3. RED CUT BOX (Expanded by Tab Height)
        # Matches your manual snippet: The red box surrounds the part + tabs
        rx = x - tab_h
        ry = y - tab_h
        rw = w + (tab_h * 2)
        rh = h + (tab_h * 2)
        elements.append(f'<rect x="{rx}" y="{ry}" width="{rw}" height="{rh}" fill="none" stroke="{col_cut_box}" stroke-width="{stroke_width}" />')
        
        # 4. Tabs
        elements.append(get_abs_tabs(x, y, w, h))
        
        # 5. Label
        cx, cy = x + w/2, y + h/2
        f_sz = sz_glz_inch if "GLAZING" in label else sz_std_inch
        elements.append(f'<text x="{cx}" y="{cy}" font-family="{font_family}" font-size="{f_sz}" fill="black" text-anchor="middle" dominant-baseline="middle" transform="rotate(-90 {cx} {cy})">{label}</text>')
        
        # 6. Waste (Optional)
        if is_waste:
            wsz = 36
            wx, wy = x + (w - wsz)/2, y + (h - wsz)/2
            elements.append(f'<rect x="{wx}" y="{wy}" width="{wsz}" height="{wsz}" fill="#ffcccc" stroke="black" stroke-width="{stroke_width}" stroke-dasharray="0.2, 0.2" opacity="0.5"/>')
            elements.append(f'<text x="{cx}" y="{cy + 4}" font-family="{font_family}" font-size="{sz_std_inch}" fill="red" text-anchor="middle">(Waste)</text>')

        return "\n".join(elements)

    # --- LAYOUT LOGIC ---
    
    def get_y(part_h):
        return sheet_h - safe_margin - part_h

    svg_content = [f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{sheet_w*2 + gap_between_sheets + 5}in" height="{sheet_h + 5}in" 
     viewBox="-2 -2 {sheet_w*2 + gap_between_sheets + 5} {sheet_h + 5}" 
     xmlns="http://www.w3.org/2000/svg">
     
  <rect x="0" y="0" width="{sheet_w}" height="{sheet_h}" fill="{col_sheet}" />
  <rect x="{sheet_w + gap_between_sheets}" y="0" width="{sheet_w}" height="{sheet_h}" fill="{col_sheet}" />
  
  <rect x="{safe_margin}" y="{safe_margin}" width="{sheet_w - 2*safe_margin}" height="{sheet_h - 2*safe_margin}" fill="none" stroke="gray" stroke-dasharray="0.5, 0.5" stroke-width="{stroke_width}" />
  <rect x="{sheet_w + gap_between_sheets + safe_margin}" y="{safe_margin}" width="{sheet_w - 2*safe_margin}" height="{sheet_h - 2*safe_margin}" fill="none" stroke="gray" stroke-dasharray="0.5, 0.5" stroke-width="{stroke_width}" />

  <text x="{sheet_w/2}" y="-1" font-family="{font_family}" font-size="2" font-weight="bold" text-anchor="middle">SHEET 1</text>
  <text x="{sheet_w + gap_between_sheets + sheet_w/2}" y="-1" font-family="{font_family}" font-size="2" font-weight="bold" text-anchor="middle">SHEET 2</text>
''']

    # --- SHEET 1 ---
    bezel_x = safe_margin
    bezel_y = get_y(panel_size)
    svg_content.append(create_exploded_part("FRONT BEZEL", bezel_x, bezel_y, panel_size, panel_size, is_waste=True))

    start_x = bezel_x + panel_size
    avail_width = (sheet_w - safe_margin) - start_x
    
    # Add spacing buffer for Red Boxes (0.3" * 2 = 0.6" per part)
    parts_s1 = [("TOP RAIL", rail_w, rail_len)] + [(f"GLAZING {i}", strip_w, strip_len) for i in range(1, 5)]
    total_parts_width = sum([p[1] for p in parts_s1])
    
    # Distribute remaining space
    gap_size = (avail_width - total_parts_width) / (len(parts_s1) + 1)
    
    # Ensure gap is large enough for red boxes (need 0.6" between parts)
    if gap_size < 0.7: gap_size = 0.7
    
    cur_x = start_x + gap_size
    for label, pw, ph in parts_s1:
        svg_content.append(create_exploded_part(label, cur_x, get_y(ph), pw, ph))
        cur_x += pw + gap_size

    # --- SHEET 2 ---
    s2_origin = sheet_w + gap_between_sheets
    back_x = s2_origin + safe_margin
    back_y = get_y(panel_size)
    svg_content.append(create_exploded_part("BACK PANEL", back_x, back_y, panel_size, panel_size))

    start_x = back_x + panel_size
    avail_width = (s2_origin + sheet_w - safe_margin) - start_x
    parts_s2 = [("RIGHT RAIL", rail_w, rail_len), ("LEFT RAIL", rail_w, rail_len), ("BOTTOM RAIL", rail_w, rail_len)]
    total_parts_width = sum([p[1] for p in parts_s2])
    
    gap_size = (avail_width - total_parts_width) / (len(parts_s2) + 1)
    if gap_size < 0.7: gap_size = 0.7
    
    cur_x = start_x + gap_size
    for label, pw, ph in parts_s2:
        svg_content.append(create_exploded_part(label, cur_x, get_y(ph), pw, ph))
        cur_x += pw + gap_size

    svg_content.append('</svg>')

    with open(filename, "w") as f:
        f.write("\n".join(svg_content))
    
    print(f"Generated {filename}")

if __name__ == "__main__":
    generate_5x5_layout_v7()

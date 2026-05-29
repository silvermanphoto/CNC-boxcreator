import math

# ==========================================
# USER CONFIGURATION (EDIT ME)
# ==========================================
# Precision Inputs (Inches)
MAT_THICKNESS = 0.485  # Exact plywood thickness
BIT_DIAMETER  = 0.25   # CNC Bit size
ALLOWANCE     = 0.015  # Glue gap tolerance (0.015 is standard loose fit)

# Box Dimensions (Outer)
BOX_WIDTH  = 45.0
BOX_HEIGHT = 45.0
BOX_DEPTH  = 6.0

# Window / Art Dimensions
WINDOW_W = 43.5
WINDOW_H = 43.5

# Joint Settings
FINGER_WIDTH_TARGET = 1.5  # Approximate size of fingers

# Output Filename
FILENAME = "Shadowbox_Ready_To_Cut.svg"

# ==========================================
# INTERNAL MATH (DO NOT EDIT)
# ==========================================
BIT_RAD = BIT_DIAMETER / 2.0

def get_finger_count(total_len, target):
    """Calculates odd number of fingers for symmetry."""
    count = int(total_len / target)
    if count % 2 == 0: count += 1
    return max(count, 3)

def generate_dogbone_corner(x, y, angle_deg):
    """Generates the SVG path command for a dogbone 'loop' at a corner."""
    offset = (BIT_RAD / math.sqrt(2))
    rad = math.radians(angle_deg)
    
    # We create a 'Keyhole' slot extending 45 degrees into the corner
    depth = BIT_RAD * 1.3 # Go slightly deeper than radius to clear corner
    
    # Calculate the "tip" of the dogbone
    tx = x + math.cos(rad) * depth
    ty = y + math.sin(rad) * depth
    
    # Return a line to the tip and back
    return f"L {tx:.4f} {ty:.4f} L {x:.4f} {y:.4f}"

def svg_header(w, h):
    return f'<svg width="{w}in" height="{h}in" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" version="1.1">\n'

def svg_footer():
    return '</svg>'

def draw_rect(x, y, w, h, color="black"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{color}" stroke-width="0.01" />\n'

def draw_dogboned_rect(x, y, w, h):
    """Draws a rectangle with integrated dogbone overcuts."""
    # Coordinates of corners
    tl = (x, y)
    tr = (x + w, y)
    br = (x + w, y + h)
    bl = (x, y + h)
    
    path = f'<path d="M {tl[0]} {tl[1]} ' # Start Top Left
    
    # Top Edge -> Top Right Corner
    path += f'L {tr[0]} {tr[1]} '
    path += generate_dogbone_corner(tr[0], tr[1], 315) # Dogbone NE
    
    # Right Edge -> Bottom Right Corner
    path += f'L {br[0]} {br[1]} '
    path += generate_dogbone_corner(br[0], br[1], 45) # Dogbone SE
    
    # Bottom Edge -> Bottom Left Corner
    path += f'L {bl[0]} {bl[1]} '
    path += generate_dogbone_corner(bl[0], bl[1], 135) # Dogbone SW
    
    # Left Edge -> Back to Start (TL)
    path += f'L {tl[0]} {tl[1]} '
    path += generate_dogbone_corner(tl[0], tl[1], 225) # Dogbone NW
    
    path += 'Z" fill="none" stroke="red" stroke-width="0.01" />\n'
    return path

# ==========================================
# MAIN GENERATION
# ==========================================

svg_content = svg_header(60, 60) # 60x60 canvas

# --- 1. FACE FRAME (With Dogboned Slots) ---
ff_x, ff_y = 1, 1
# Main Outline
svg_content += draw_rect(ff_x, ff_y, BOX_WIDTH, BOX_HEIGHT, "blue")
# Window
wx = ff_x + (BOX_WIDTH - WINDOW_W)/2
wy = ff_y + (BOX_HEIGHT - WINDOW_H)/2
svg_content += draw_rect(wx, wy, WINDOW_W, WINDOW_H, "blue")

# Slots
fingers_h = get_finger_count(BOX_WIDTH - (MAT_THICKNESS*2), FINGER_WIDTH_TARGET)
finger_w_real = (BOX_WIDTH - (MAT_THICKNESS*2)) / fingers_h

# Top/Bottom Slots
start_x = ff_x + MAT_THICKNESS
for i in range(fingers_h):
    if i % 2 == 0: # It's a slot
        sx = start_x + (i * finger_w_real)
        gap = ALLOWANCE / 2
        # Bottom Row Slot
        svg_content += draw_dogboned_rect(sx - gap, ff_y + MAT_THICKNESS, finger_w_real + ALLOWANCE, MAT_THICKNESS)
        # Top Row Slot
        svg_content += draw_dogboned_rect(sx - gap, ff_y + BOX_HEIGHT - (MAT_THICKNESS*2), finger_w_real + ALLOWANCE, MAT_THICKNESS)

# Left/Right Slots
rail_len_v = BOX_HEIGHT - (MAT_THICKNESS*2)
fingers_v = get_finger_count(rail_len_v, FINGER_WIDTH_TARGET)
finger_h_real = rail_len_v / fingers_v

start_y = ff_y + MAT_THICKNESS
for i in range(fingers_v):
    if i % 2 == 0:
        sy = start_y + (i * finger_h_real)
        gap = ALLOWANCE / 2
        # Left Row Slot
        svg_content += draw_dogboned_rect(ff_x + MAT_THICKNESS, sy - gap, MAT_THICKNESS, finger_h_real + ALLOWANCE)
        # Right Row Slot
        svg_content += draw_dogboned_rect(ff_x + BOX_WIDTH - (MAT_THICKNESS*2), sy - gap, MAT_THICKNESS, finger_h_real + ALLOWANCE)

# --- 2. RAILS & BACK ---
rail_depth = BOX_DEPTH - MAT_THICKNESS
rx = 1
ry = 47 # Move down to clear the Face Frame

# Top Rail
svg_content += f'<text x="{rx}" y="{ry}" font-family="Arial" font-size="1">Rails & Back (Simple Profiles)</text>\n'
svg_content += draw_rect(rx, ry+1, BOX_WIDTH, rail_depth, "green")
svg_content += f'<text x="{rx}" y="{ry+2}" font-size="0.5">Top Rail ({BOX_WIDTH} x {rail_depth})</text>\n'

# Bottom Rail
svg_content += draw_rect(rx, ry+8, BOX_WIDTH, rail_depth, "green")
svg_content += f'<text x="{rx}" y="{ry+9}" font-size="0.5">Bottom Rail</text>\n'

# Left Rail
svg_content += draw_rect(rx, ry+15, BOX_HEIGHT-(MAT_THICKNESS*2), rail_depth, "green")
svg_content += f'<text x="{rx}" y="{ry+16}" font-size="0.5">Left Rail</text>\n'

# Right Rail
svg_content += draw_rect(rx, ry+22, BOX_HEIGHT-(MAT_THICKNESS*2), rail_depth, "green")
svg_content += f'<text x="{rx}" y="{ry+23}" font-size="0.5">Right Rail</text>\n'

# Back Panel
back_w = BOX_WIDTH - (MAT_THICKNESS*2) - 0.125
back_h = BOX_HEIGHT - (MAT_THICKNESS*2) - 0.125
svg_content += draw_rect(rx+20, ry+1, back_w, back_h, "black")
svg_content += f'<text x="{rx+20}" y="{ry+2}" font-size="0.5">Back Panel ({back_w:.2f} x {back_h:.2f})</text>\n'

svg_content += svg_footer()

with open(FILENAME, "w") as f:
    f.write(svg_content)

print(f"Success! {FILENAME} created.")
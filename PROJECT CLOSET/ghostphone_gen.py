import math

# Project: McTell Ghostphone CNC Shadowbox
MAT_THICKNESS = 12 / 25.4  # 12mm (~0.4724")
BIT_DIA = 0.25
BIT_RAD = BIT_DIA / 2
ALLOWANCE = 0.0075  
BOX_OUTSIDE = 45.25
RAIL_DEPTH = 4.0
WINDOW_SIZE = 43.25
RABBET_WIDTH = 0.625
MOTOR_X_FROM_INNER = 19.913
MOTOR_POCKET_SZ = 1.67
MOTOR_SHAFT_DIA = 0.75
MOTOR_MOUNT_SQ = 1.22
MOTOR_MOUNT_DIA = 0.14
CABLE_HOLE_DIA = 0.5
TARGET_FINGER_W = 1.5
CORNER_FINGER_COUNT = 5 
FILENAME = "McTell_Ghostphone_Shadowbox.svg"

def get_odd_count(length, target_w):
    count = round(length / target_w)
    if count % 2 == 0: count += 1
    return max(3, count)

FINGER_COUNT_LONG = get_odd_count(BOX_OUTSIDE, TARGET_FINGER_W)
F_WIDTH_LONG = BOX_OUTSIDE / FINGER_COUNT_LONG 
F_WIDTH_CORNER = RAIL_DEPTH / CORNER_FINGER_COUNT 

def generate_svg():
    svg = ['<svg width="110in" height="85in" viewBox="-5 -5 110 85" xmlns="http://www.w3.org/2000/svg">']
    svg.append('<style>.label { font-family: "Josefin Sans Semibold", sans-serif; font-size: 0.33in; fill: black; }</style>')
    # Safe Zone
    svg.append(f'<rect x="-2" y="-2" width="105" height="80" fill="none" stroke="red" stroke-width="0.05" />')
    # Face Panel
    svg.append(f'<rect x="0" y="0" width="{BOX_OUTSIDE}" height="{BOX_OUTSIDE}" fill="none" stroke="black" stroke-width="0.01"/>')
    svg.append(f'<rect x="1" y="1" width="{WINDOW_SIZE}" height="{WINDOW_SIZE}" fill="none" stroke="blue" stroke-width="0.01"/>')
    svg.append('<text x="0" y="-1" class="label">A. FACE PANEL - 45.25" x 45.25"</text>')
    # Bottom Rail
    svg.append(f'<rect x="0" y="48" width="{BOX_OUTSIDE}" height="{RAIL_DEPTH}" fill="none" stroke="black" stroke-width="0.01"/>')
    inner_x = 0 + MAT_THICKNESS + MOTOR_X_FROM_INNER
    cx, cy = inner_x + (MOTOR_POCKET_SZ/2), 48 + (RAIL_DEPTH/2)
    svg.append(f'<rect x="{inner_x}" y="{cy-0.835}" width="1.67" height="1.67" fill="none" stroke="blue" stroke-width="0.01"/>')
    svg.append(f'<circle cx="{cx}" cy="{cy}" r="0.375" fill="none" stroke="red" stroke-width="0.01"/>')
    svg.append(f'<circle cx="{cx-3}" cy="{cy}" r="0.25" fill="none" stroke="black" stroke-width="0.01"/>')
    svg.append('<text x="0" y="47" class="label">D. BOTTOM RAIL (WITH NEMA 17)</text>')
    # Back Panel
    svg.append(f'<rect x="50" y="0" width="{BOX_OUTSIDE}" height="{BOX_OUTSIDE}" fill="none" stroke="black" stroke-width="0.01"/>')
    svg.append(f'<rect x="{50+RABBET_WIDTH}" y="{RABBET_WIDTH}" width="{BOX_OUTSIDE-RABBET_WIDTH*2}" height="{BOX_OUTSIDE-RABBET_WIDTH*2}" fill="none" stroke="green" stroke-width="0.01"/>')
    svg.append('<text x="50" y="-1" class="label">E. BACK PANEL (RABBETED)</text>')
    svg.append('</svg>')
    with open(FILENAME, 'w') as f: f.write("\n".join(svg))

generate_svg()

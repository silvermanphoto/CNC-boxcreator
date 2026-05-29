import math

CONFIG = {
    'CANVAS_SIZE_STD': 300,
    'TOTAL_WIDTH': 254.0,  # 10 inches
    'TOTAL_HEIGHT': 254.0,
    'BOX_DEPTH': 101.6,    # 4 inches
    'TARGET_FINGER_WIDTH': 25.4, # 1 inch
    'STOCK_THICKNESS': 19.05, # 0.75 inch
    'BLIND_SKIN': 0.5,
    'FIT_TOLERANCE': 0.1,
    'ACTIVE_JOINERY_METHOD': "BLIND_BOX_JOINT",
    'Tab_Base': 6.0,
    'Tab_Tip': 3.0,
    'Tab_Peak': 4.0
}

def f(val):
    return f"{val:.4f}"

def compute_finger_layout(edge_len, target_w):
    count = round(edge_len / target_w)
    if count % 2 == 0: count += 1
    actual_w = edge_len / count
    return count, actual_w

def draw_blind_finger_geometry_open(x, y, w, h, blind_skin, glue_gap, direction):
    w_finger = w - glue_gap
    shift = (w - w_finger) / 2.0
    finger_len = h - blind_skin
    cmds = []
    
    if direction == 'UP':
        fx = x + shift; fy = y; tip_y = y - finger_len
        # OPEN PATH: Start at base -> Go to tip -> Across tip -> Back to base
        # IMPORTANT: This assumes the previous command ended at (fx, fy) or we L-move there?
        # The main loop does `L {pattern_start} {anchor_y}`, so we are on the line.
        # We need to draw: L to start of finger BASE -> L to TIP -> L across TIP -> L back to BASE
        
        # Actually, looking at the main loop:
        # It does: `path_cmds.append(f"L {f(pattern_start_x + ((i + 1) * width_face))} {f(anchor_y)}")` for gaps.
        # So we just need to provide the segments for the finger itself.
        
        cmds = [
            f"L {f(fx)} {f(fy)}",          # Move along baseline to finger start
            f"L {f(fx)} {f(tip_y)}",       # Go OUT (Up)
            f"L {f(fx + w_finger)} {f(tip_y)}", # Go ACROSS
            f"L {f(fx + w_finger)} {f(fy)}" # Go BACK (Down)
        ]
        
    return cmds

def generate_test_rail():
    # Simulate a TOP_RAIL (Horizontal)
    rail_w = CONFIG['TOTAL_WIDTH']
    rail_h = CONFIG['BOX_DEPTH']
    anchor_x = 10.0
    anchor_y = 100.0 # Shift down a bit
    
    count_face, width_face = compute_finger_layout(rail_w, CONFIG['TARGET_FINGER_WIDTH'])
    
    path_cmds = []
    path_cmds.append(f"M {f(anchor_x)} {f(anchor_y)}")
    
    # 1. TOP EDGE (The one with fingers)
    center_rail_x = anchor_x + (rail_w / 2.0)
    total_pattern_w = count_face * width_face
    pattern_start_x = center_rail_x - (total_pattern_w / 2.0)
    
    if pattern_start_x > anchor_x: 
        path_cmds.append(f"L {f(pattern_start_x)} {f(anchor_y)}")
        
    for i in range(count_face):
        x_abs = pattern_start_x + (i * width_face)
        if i % 2 == 1:
            # draw OPEN finger
            cmds = draw_blind_finger_geometry_open(x_abs, anchor_y, width_face, CONFIG['STOCK_THICKNESS'], CONFIG['BLIND_SKIN'], CONFIG['FIT_TOLERANCE'], 'UP')
            path_cmds += cmds
        else:
            # Draw spacer line
            path_cmds.append(f"L {f(pattern_start_x + ((i + 1) * width_face))} {f(anchor_y)}")
            
    path_cmds.append(f"L {f(anchor_x + rail_w)} {f(anchor_y)}")
    
    # Close the box for the other 3 sides (simplified)
    path_cmds.append(f"L {f(anchor_x + rail_w)} {f(anchor_y + rail_h)}")
    path_cmds.append(f"L {f(anchor_x)} {f(anchor_y + rail_h)}")
    path_cmds.append("Z")
    
    svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="300mm" viewBox="0 0 300 300">
  <path d="{' '.join(path_cmds)}" fill="none" stroke="#000000" stroke-width="0.5"/>
</svg>'''

    with open("TEST_OPEN_FINGERS.svg", "w") as outfile:
        outfile.write(svg_content)
    print("Generated TEST_OPEN_FINGERS.svg")

if __name__ == "__main__":
    generate_test_rail()

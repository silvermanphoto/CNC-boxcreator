import sys
import os
import importlib.util
import re
import math

# Path to the v50 generator
GEN_PATH = "/Users/joelsilverman/Desktop/2026 Files/26-005 Gemini-created CNC Box Creator/Gemini McTell CNC Plans/CNC GENERATOR - CARBIDE-OPTIMIZED v50.py"

def load_generator():
    spec = importlib.util.spec_from_file_location("cnc_gen", GEN_PATH)
    cnc_gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cnc_gen)
    return cnc_gen

def parse_path_d(d_str):
    # Very basic parser for M L commands
    # Split by commands
    # Returns list of points (x, y)
    commands = re.findall(r'([MLZ])\s*([^MLZ]*)', d_str)
    points = []
    current_pos = (0,0)
    
    for cmd, args in commands:
        if cmd == 'Z':
            break
        coords = [float(x) for x in args.strip().split()]
        if len(coords) >= 2:
            x, y = coords[0], coords[1]
            points.append((x, y))
            current_pos = (x, y)
    return points

def measure_fingers():
    cnc_gen = load_generator()
    
    # Configure for ~0.61" target
    # Stock 0.61" = 15.494mm
    cnc_gen.CONFIG.clear()
    cnc_gen.CONFIG.update({
        'TOTAL_WIDTH': 254.0, # 10 inches
        'TOTAL_HEIGHT': 254.0,
        'BOX_DEPTH': 100.0,
        'STOCK_THICKNESS': 15.5, # ~0.61 inch
        'TARGET_FINGER_WIDTH': 15.5, # Target 0.61 inch
        'FIT_TOLERANCE': 0.0, # Zero tolerance for measurement
        'BLIND_SKIN': 0.0,
        'ACTIVE_JOINERY_METHOD': "BLIND_BOX_JOINT",
        'MARGIN_INCHES': 1.0,
        'FRONT_RIM_WIDTH_M': 20.0, 
        'BACK_RIM_WIDTH_M': 20.0
    })
    
    # Generate RIGHT RAIL (Vertical rail, horizontal profile?) which has fingers
    # Top Edge is usually the one with fingers if it's a Top/Bottom rail? 
    # Let's check TOP_RAIL (Horizontal rail).
    # generate_rail_parts -> returns files
    
    print("--- Generating TOP_RAIL ---")
    files, _ = cnc_gen.generate_rail_parts("TOP_RAIL", True, False, "TEST")
    key = [k for k in files.keys() if "PERIMETER" in k][0]
    svg_content = files[key]
    
    # Extract D
    match = re.search(r' d="([^"]+)"', svg_content)
    if not match:
        print("Could not find d attribute")
        return
        
    d_str = match.group(1)
    points = parse_path_d(d_str)
    
    # Analyze X segments along the Top Edge (First few points?)
    # Path usually starts M (ax, ay).
    # Then draws Top Edge (Left to Right).
    # Fingers alternate "Up" and "Down" relative to the line?
    # Or "Out" and "In"?
    # Top Rail: Fingers point Up (Recessed or Protruding?).
    
    # Let's just print the first 10 X-deltas to seeing the spacing.
    print(f"Total Points: {len(points)}")
    if len(points) < 5: return

    # Identify "Finger" vs "Gap"
    # Fingers are excursions in Y?
    # Or segments along X?
    
    current_x = points[0][0]
    segments = []
    
    # We expect a sequence of x steps.
    # scan for x changes
    x_vals = [p[0] for p in points]
    y_vals = [p[1] for p in points]
    
    print("First 20 Points:")
    for i in range(min(20, len(points))):
        print(f"{i}: ({points[i][0]:.4f}, {points[i][1]:.4f})")
        
    # Calculate widths of segments
    # Filter for points that share Y (horizontal segments)
    # The "Top Edge" is the first sequence.
    # It usually alternates Y (Base, Tip, Base, Tip).
    
    # Find Y-min and Y-max in the first half?
    # Base Y vs Tip Y.
    
    # Just calculate distance between consecutive X where Y changes?
    
if __name__ == "__main__":
    measure_fingers()

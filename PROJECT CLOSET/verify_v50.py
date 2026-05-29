import sys
import os
import importlib.util
import re

# Path to the v50 generator
GEN_PATH = "/Users/joelsilverman/Desktop/2026 Files/26-005 Gemini-created CNC Box Creator/Gemini McTell CNC Plans/CNC GENERATOR - CARBIDE-OPTIMIZED v50.py"

def load_generator():
    spec = importlib.util.spec_from_file_location("cnc_gen", GEN_PATH)
    cnc_gen = importlib.util.module_from_spec(spec)
    # prevent ensures_dependencies from killing us if possible, but it runs on import.
    # It checks for numpy/matplotlib. If they are installed, it proceeds.
    # It might create a Tk root? No, that's in __main__.
    # It sets matplotlib backend.
    spec.loader.exec_module(cnc_gen)
    return cnc_gen

def test_rail_glitch():
    cnc_gen = load_generator()
    
    # Mock CONFIG
    # Use simple numbers: Stock=10, Width=100.
    cnc_gen.CONFIG.clear()
    cnc_gen.CONFIG.update({
        'TOTAL_WIDTH': 100.0,
        'TOTAL_HEIGHT': 100.0,
        'BOX_DEPTH': 50.0,
        'STOCK_THICKNESS': 10.0,
        'FINGER_WIDTH': 10.0,
        'FIT_TOLERANCE': 0.0,
        'BLIND_SKIN': 0.0, # Simple through cuts or blind 0
        'LID_FIT_ADJUSTMENT': 0.0,
        'LID_STEP_DEPTH': 5.0,
        'PILOT_DIA': 3.0,
        'WINDOW_WIDTH_IN': 2.0,
        'WINDOW_HEIGHT_IN': 2.0,
        'MARGIN_INCHES': 1.0,
        'ACTIVE_JOINERY_METHOD': "BLIND_BOX_JOINT",
        'FRONT_RIM_WIDTH_M': 100.0, # Dummy Value
        'BACK_RIM_WIDTH_M': 100.0   # Dummy Value
    })
    
    # Test RIGHT_RAIL
    # In v50 Logic, Right Rail usually has 'sockets' on the right side if it mates with Back Panel (which has Fingers)
    # Let's verify what generate_rail_parts does for RIGHT_RAIL.
    # It usually sets left_type='sockets', right_type='sockets' (depending on parity).
    
    print("--- Generating RIGHT_RAIL ---")
    files, paths = cnc_gen.generate_rail_parts("RIGHT_RAIL", False, False, "TEST")
    print("Generated Keys:", files.keys())
    # Try to find the right key
    target_key = [k for k in files.keys() if "PERIMETER" in k][0]
    svg = files[target_key]
    
    # Check for the specific corner fix.
    # The fix was: if right_type == 'sockets', the bottom-right corner point should be recessed.
    # The path usually goes Clockwise or Counter-Clockwise.
    # Bottom edge is drawn Right-to-Left.
    # Start of Bottom Edge: should be (Right_X - Stock, Box_H - Stock) if bottom is socket?
    # Actually, the glitch was "Jagged line".
    
    print(svg)
    
    # Create dummy entries for other rails to prevent KeyError in Master Layout
    files[f"TOP_RAIL_PERIMETER.vTEST.svg"] = ' d="M0,0 L10,0"'
    files[f"BOTTOM_RAIL_PERIMETER.vTEST.svg"] = ' d="M0,0 L10,0"'
    files[f"LEFT_RAIL_PERIMETER.vTEST.svg"] = ' d="M0,0 L10,0"'
    
    # Also check Master Layout generation briefly
    print("\n--- Generating Master Layout ---")
    # We need dummy svg contents for other parts
    f_dummy = {"FRONT_BEZEL_PERIMETER.vTEST.svg": ' d="M0,0 L10,0 L10,10 L0,10 Z"', "FRONT_BEZEL_WINDOW.vTEST.svg": ""}
    f_dummy_holes = {
        "BACK_PANEL_HOLES.vTEST.svg": '<circle cx="5" cy="5" r="1"/>',
        "BACK_PANEL_PERIMETER.vTEST.svg": ' d="M0,0 L10,0"'
    }
    
    try:
        master = cnc_gen.generate_master_carbide_layout("TEST", f_dummy, f_dummy_holes, files, files, files, files)
        print("Master Layout Generated Successfully.")
        print("Layer Check:")
        if 'id="CUTS"' in master: print(" - CUTS layer found")
        if 'id="HOLES"' in master: print(" - HOLES layer found")
        if 'id="RABBETS"' in master: print(" - RABBETS layer found")
        if 'id="WINDOWS"' in master: print(" - WINDOWS layer found")
        if 'id="ALIGNMENT_FRAME"' in master: print(" - ALIGNMENT_FRAME found")
        
        # Check artboard size dimensions
        if 'width="48in"' in master or 'width="4608"' in master:
            print(" - Artboard seems correct (48in)")
            
    except Exception as e:
        print(f"Master Layout Generation Failed: {e}")

if __name__ == "__main__":
    test_rail_glitch()

import sys
import os
import json

# Add current dir to path
sys.path.append(os.getcwd())

# Import modules
import cnc_generator
import blender_generator
from utils import convert_to_inches

# SETUP CONFIG
# Dimensions: 63.5968 x 46.1968 x 5.0984
# Stock: 15.2mm
# Window: 53.4 x 36

# Convert inches to mm for CONFIG (app uses mm internally mostly)
w_in = 63.5968
h_in = 46.1968
d_in = 5.0984
stock_mm = 15.2
window_w_in = 53.4
window_h_in = 36.0

cnc_generator.CONFIG['TOTAL_WIDTH'] = w_in * 25.4
cnc_generator.CONFIG['TOTAL_HEIGHT'] = h_in * 25.4
cnc_generator.CONFIG['BOX_DEPTH'] = d_in * 25.4
cnc_generator.CONFIG['STOCK_THICKNESS'] = stock_mm
cnc_generator.CONFIG['TOOL_D_PRIMARY'] = 0.125 * 25.4 # 1/8" bit
cnc_generator.CONFIG['FIT_TOLERANCE'] = 0.2 # 0.2mm glue gap from screenshot
cnc_generator.CONFIG['TARGET_FINGER_WIDTH'] = 15.2 # Matching stock

# M5 FIX: match the GUI's rim/rabbet computation. Previously these keys were unset here,
# so the panel generators fell back to a 0.3" default rim — 0.3" different per side from
# what the GUI produces for the same inputs.
_stock_in = stock_mm / 25.4
_calc_rim_in = _stock_in + (cnc_generator.CONFIG['FIT_TOLERANCE'] / 25.4)  # no lid-fit adj headless
cnc_generator.CONFIG['FRONT_RIM_WIDTH_IN'] = _calc_rim_in
cnc_generator.CONFIG['BACK_RIM_WIDTH_IN'] = _calc_rim_in
cnc_generator.CONFIG['FRONT_RABBET_WIDTH'] = _stock_in - _calc_rim_in  # legacy proxy (Blender)
cnc_generator.CONFIG['BACK_RABBET_WIDTH'] = _stock_in - _calc_rim_in   # legacy proxy (Blender)
cnc_generator.CONFIG['FRONT_RABBET_DEPTH'] = _stock_in / 2.0
cnc_generator.CONFIG['BACK_RABBET_DEPTH'] = _stock_in / 2.0

# Window
cnc_generator.CONFIG['WINDOW_ENABLED'] = True
cnc_generator.CONFIG['WINDOW_WIDTH_IN'] = window_w_in
cnc_generator.CONFIG['WINDOW_HEIGHT_IN'] = window_h_in
# Rim Width (Meters)
rim_w_in = (w_in - window_w_in) / 2
cnc_generator.CONFIG['FRONT_RIM_WIDTH_M'] = rim_w_in * 0.0254

# Bottom Hatch
# User spec: 4.559 x 3.559 in
cnc_generator.CONFIG['BOTTOM_HATCH_ENABLED'] = True
cnc_generator.CONFIG['BOTTOM_HATCH_WIDTH'] = 4.559 * 25.4
cnc_generator.CONFIG['BOTTOM_HATCH_HEIGHT'] = 3.559 * 25.4
cnc_generator.CONFIG['BOTTOM_HATCH_X_PCT'] = 50.0

# Cleats (Default Enabled)
cnc_generator.CONFIG['CLEATS_ENABLED'] = True

# Hatch (Rear) - Default Disabled unless requested? 
# Screenshot didn't show it. I'll disable to be safe or enable if standard.
# "Enable Rear Access Panel" unchecked in screenshot? Screenshot was cut off at top of Output.
# I'll disable Rear Hatch to avoid conflicts, focus on Bottom Hatch.
cnc_generator.CONFIG['HATCH_ENABLED'] = False

# GENERATE GEOMETRY
version = "125_HEADLESS"

# 1. Rails
# Rail functions return (files_dict, path_d_str)
# We need path_d_str for Blender
f_top, p_top = cnc_generator.generate_rail_parts("TOP_RAIL", True, False, version)
f_bot, p_bot = cnc_generator.generate_rail_parts("BOTTOM_RAIL", True, True, version) # Has Motor/Hatch
f_left, p_left = cnc_generator.generate_rail_parts("LEFT_RAIL", False, False, version)
f_right, p_right = cnc_generator.generate_rail_parts("RIGHT_RAIL", False, False, version)

rail_paths = {
    'TOP': p_top,
    'BOTTOM': p_bot,
    'LEFT': p_left,
    'RIGHT': p_right
}

# 2. Front & Back (Need geometry data)
# generate_front_bezel_parts returns (files, geom_data)
f_front, geom_front = cnc_generator.generate_front_bezel_parts(version)
f_back, geom_back = cnc_generator.generate_back_panel_parts(version)

# 3. Generate Blender Script
script_content = blender_generator.generate_trivision_script(version, cnc_generator.CONFIG, rail_paths, geom_front, geom_back, collection_name="OUTSIDE_FRAME_NEW")

# Output to file
with open("generated_blender_script.py", "w") as f:
    f.write(script_content)

print("Script written to generated_blender_script.py")

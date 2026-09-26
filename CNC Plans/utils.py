"""
Shared utilities for CNC Generator.
"""

MARGIN_INCHES = 2.0    # 2" margin on all sides

# Longest hanging cleat: a 48" sheet less the 0.5" packing margin on each side (CNC-05).
CLEAT_MAX_LEN_IN = 47.0

# Box-cleat screw holes, as fractions of the cleat's length (Joel's v1.09 spec: 5%, 33%,
# 66%, 95%, read as thirds). CNC-14: mirror-symmetric, so the cleat's holes meet the back
# panel's whichever face each part is cut from; 0.33/0.66 missed by 1% of the cleat.
CLEAT_HOLE_FRACTIONS = (0.05, 1 / 3, 2 / 3, 0.95)

def convert_to_inches(value_mm):
    """Convert mm to inches"""
    return value_mm / 25.4

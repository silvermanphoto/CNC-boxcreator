"""
Shared utilities for CNC Generator.
"""

MARGIN_INCHES = 2.0    # 2" margin on all sides

# Longest hanging cleat: a 48" sheet less the 0.5" packing margin on each side (CNC-05).
CLEAT_MAX_LEN_IN = 47.0

def convert_to_inches(value_mm):
    """Convert mm to inches"""
    return value_mm / 25.4

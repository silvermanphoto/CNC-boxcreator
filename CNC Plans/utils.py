"""
Shared utilities for CNC Generator.
"""

MARGIN_INCHES = 2.0    # 2" margin on all sides

def convert_to_inches(value_mm):
    """Convert mm to inches"""
    return value_mm / 25.4

#!/usr/bin/env python3
"""Test script to generate and inspect master layout."""

import sys
import os
import re

# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# M7 FIX: this is a post-hoc inspector of the most recent generated output folder.
# The old broken importlib reference to "CNC GENERATOR - Claude v1.04.py" (which does not
# exist and was never executed) has been removed, and the folder pattern updated to the
# current "McTell SVGs v<N>" naming. To generate output, run cnc_generator.py (GUI) or the
# headless acceptance test in test_gen.py.

import json
from pathlib import Path

# Find the most recent output folder
out_path = Path(__file__).resolve().parent

# Look for the current output folders ("McTell SVGs v<N>")
folders = sorted([f for f in out_path.iterdir() if f.is_dir() and "McTell SVGs v" in f.name],
                 key=lambda x: int(re.search(r'v(\d+)', x.name).group(1)) if re.search(r'v(\d+)', x.name) else 0)

if folders:
    latest = folders[-1]
    print(f"Latest output folder: {latest.name}")

    # List all files
    files = list(latest.iterdir())
    print(f"\nFiles in folder ({len(files)} total):")
    for f in sorted(files):
        print(f"  - {f.name}")

    # Check master layout
    master_files = [f for f in files if "MASTER_LAYOUT" in f.name]
    if master_files:
        master = master_files[0]
        print(f"\n--- MASTER LAYOUT: {master.name} ---")

        content = master.read_text()
        print(f"File size: {len(content)} chars")

        # Parse SVG dimensions
        import re
        width_match = re.search(r'width="([^"]+)"', content)
        height_match = re.search(r'height="([^"]+)"', content)
        if width_match and height_match:
            print(f"Artboard: {width_match.group(1)} x {height_match.group(1)}")

        # Count groups/parts
        groups = re.findall(r'<g id="([^"]+)"', content)
        print(f"\nGroups found ({len(groups)}):")
        for g in groups[:30]:  # First 30
            print(f"  - {g}")
        if len(groups) > 30:
            print(f"  ... and {len(groups) - 30} more")

        # Check for specific parts
        expected_parts = ['FRONT', 'BACK', 'TOP', 'BOTTOM', 'LEFT', 'RIGHT', 'CLEAT']
        print(f"\nExpected parts check:")
        for part in expected_parts:
            found = any(part in g for g in groups)
            print(f"  {part}: {'✓' if found else '✗ MISSING'}")

        # Print first 2000 chars of SVG for inspection
        print(f"\n--- First 2000 chars of SVG ---")
        print(content[:2000])
else:
    print("No output folders found. Please run the generator first.")

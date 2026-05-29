#!/usr/bin/env python3
"""Test script to generate and inspect master layout."""

import sys
import os

# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from the main file - we need to import the module properly
# Since it has spaces in the name, use importlib
import importlib.util

spec = importlib.util.spec_from_file_location("cnc_generator", "CNC GENERATOR - Claude v1.04.py")
cnc = importlib.util.module_from_spec(spec)

# We can't easily load it due to the tkinter mainloop at the end
# Instead, let's just run the generator directly with subprocess and check output

import subprocess
import json
from pathlib import Path

# Find the most recent output folder
out_path = Path("/Users/joelsilverman/Desktop/2026 Files/26-005 Gemini-created CNC Box Creator/Gemini McTell CNC Plans")

# Look for CNC Box Generator folders
folders = sorted([f for f in out_path.iterdir() if f.is_dir() and "CNC Box Generator v" in f.name],
                 key=lambda x: int(x.name.split('v')[-1]) if x.name.split('v')[-1].isdigit() else 0)

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

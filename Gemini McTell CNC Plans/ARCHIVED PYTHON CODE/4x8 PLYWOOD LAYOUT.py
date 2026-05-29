#!/usr/bin/env python3
"""
Nesting Layout Generator
Creates a 1:1 scale SVG of the shadowbox parts nested on a 4x8 sheet.
"""

import os

def generate_nesting_svg(filename="Nesting_Layout_4x8.svg"):
    # Dimensions
    sheet_w, sheet_h = 48, 96
    margin = 0.5
    spacing = 1.0
    
    # Part Dims (Approximate bounding boxes based on 40x40x4 box)
    panel_w, panel_h = 40, 40
    rail_len, rail_depth = 40, 4
    
    # Colors
    col_sheet = "#f4e4bc" # Plywood color
    col_part = "#d1e8ff"  # Blue fill
    col_cut = "#000000"   # Cut line
    col_waste = "#ffcccc" # Waste highlight

    svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{sheet_w}in" height="{sheet_h}in" viewBox="0 0 {sheet_w} {sheet_h}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      text {{ font-family: Arial; font-size: 1px; fill: black; text-anchor: middle; }}
      .cut {{ fill: {col_part}; stroke: {col_cut}; stroke-width: 0.05; }}
      .sheet {{ fill: {col_sheet}; stroke: none; }}
      .waste {{ fill: {col_waste}; stroke: {col_cut}; stroke-width: 0.05; stroke-dasharray: 0.2, 0.2; }}
    </style>
  </defs>
  
  <rect x="0" y="0" width="{sheet_w}" height="{sheet_h}" class="sheet" />
  <text x="{sheet_w/2}" y="1.5" font-size="0.8">4' x 8' Plywood Sheet (96" x 48")</text>

  <g transform="translate({margin}, {sheet_h - margin - panel_h})">
    <rect x="0" y="0" width="{panel_w}" height="{panel_h}" class="cut" />
    <text x="{panel_w/2}" y="{panel_h/2}">FRONT BEZEL (40x40)</text>
    <rect x="{panel_w/2 - 18}" y="{panel_h/2 - 18}" width="36" height="36" class="waste" rx="0.5" />
    <text x="{panel_w/2}" y="{panel_h/2 + 2}" font-size="0.8" fill="red">(Internal Waste Area)</text>
  </g>

  <g transform="translate({margin}, {sheet_h - margin - panel_h - spacing - panel_h})">
    <rect x="0" y="0" width="{panel_w}" height="{panel_h}" class="cut" />
    <text x="{panel_w/2}" y="{panel_h/2}">BACK PANEL (40x40)</text>
  </g>

  <g transform="translate({margin + panel_w + spacing}, {sheet_h - margin - rail_len})">
    <rect x="0" y="0" width="{rail_depth}" height="{rail_len}" class="cut" />
    <text x="{rail_depth/2}" y="{rail_len/2}" transform="rotate(-90 {rail_depth/2} {rail_len/2})">RAIL 1</text>
  </g>

  <g transform="translate({margin + panel_w + spacing}, {sheet_h - margin - rail_len - spacing - rail_len})">
    <rect x="0" y="0" width="{rail_depth}" height="{rail_len}" class="cut" />
    <text x="{rail_depth/2}" y="{rail_len/2}" transform="rotate(-90 {rail_depth/2} {rail_len/2})">RAIL 2</text>
  </g>

  <g transform="translate({margin}, {sheet_h - margin - panel_h - spacing - panel_h - spacing - rail_depth})">
    <rect x="0" y="0" width="{rail_len}" height="{rail_depth}" class="cut" />
    <text x="{rail_len/2}" y="{rail_depth/2 + 0.3}">RAIL 3</text>
  </g>

  <g transform="translate({margin}, {sheet_h - margin - panel_h - spacing - panel_h - spacing - rail_depth - spacing - rail_depth})">
    <rect x="0" y="0" width="{rail_len}" height="{rail_depth}" class="cut" />
    <text x="{rail_len/2}" y="{rail_depth/2 + 0.3}">RAIL 4</text>
  </g>

  <g transform="translate({margin + 20 - 16}, {sheet_h - margin - 20 - 15})">
     <text x="16" y="-2" font-size="0.6">Glazing stops nested in waste</text>
     <rect x="0" y="0" width="32" height="1" class="cut" />
     <rect x="0" y="1.5" width="32" height="1" class="cut" />
     <rect x="0" y="3.0" width="32" height="1" class="cut" />
     <rect x="0" y="4.5" width="32" height="1" class="cut" />
  </g>

</svg>'''

    with open(filename, "w") as f:
        f.write(svg_content)
    
    print(f"Generated {filename} successfully.")

if __name__ == "__main__":
    generate_nesting_svg()

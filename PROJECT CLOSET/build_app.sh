#!/bin/bash
echo "Building macOS App Bundle for CNC Generator v1.01..."

# Ensure we are in the correct directory (where the script is)
cd "$(dirname "$0")"

# Output directory for component builds (temp)
mkdir -p build_temp

# Run PyInstaller
# --windowed: No terminal window
# --icon: Custom icon
# --noconfirm: overwrite existing
# --clean: clean cache
# --name: App Name
# --add-data: Include logic for saving settings (not stricly needing file, but making sure)
# Using the venv python to ensure deps

"/Users/joelsilverman/Desktop/2026 Files/26-005 CNC Box Creator/venv/bin/pyinstaller" \
    --name "CNC Plywood Box Maker" \
    --windowed \
    --icon "Generator.icns" \
    --noconfirm \
    --clean \
    --target-architecture universal2 \
    "CNC GENERATOR - CARBIDE-OPTIMIZED v1.01.py"

echo "Build Complete. App is in 'dist/CNC Plywood Box Maker.app'"
open dist

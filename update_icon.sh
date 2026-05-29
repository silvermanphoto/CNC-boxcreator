#!/bin/bash
set -e

SOURCE_ICON="Gemini McTell CNC Plans/App Photo Assets/Gemini_Generated_Image_8x9qnk8x9qnk8x9q.png"
ICONSET_DIR="MyIcon.iconset"
DEST_ICNS="CNC Plywood Box Maker.app/Contents/Resources/Generator.icns"

echo "Creating iconset directory..."
mkdir -p "$ICONSET_DIR"

echo "Resizing images..."
sips -z 16 16     "$SOURCE_ICON" --out "$ICONSET_DIR/icon_16x16.png"
sips -z 32 32     "$SOURCE_ICON" --out "$ICONSET_DIR/icon_16x16@2x.png"
sips -z 32 32     "$SOURCE_ICON" --out "$ICONSET_DIR/icon_32x32.png"
sips -z 64 64     "$SOURCE_ICON" --out "$ICONSET_DIR/icon_32x32@2x.png"
sips -z 128 128   "$SOURCE_ICON" --out "$ICONSET_DIR/icon_128x128.png"
sips -z 256 256   "$SOURCE_ICON" --out "$ICONSET_DIR/icon_128x128@2x.png"
sips -z 256 256   "$SOURCE_ICON" --out "$ICONSET_DIR/icon_256x256.png"
sips -z 512 512   "$SOURCE_ICON" --out "$ICONSET_DIR/icon_256x256@2x.png"
sips -z 512 512   "$SOURCE_ICON" --out "$ICONSET_DIR/icon_512x512.png"
sips -z 1024 1024 "$SOURCE_ICON" --out "$ICONSET_DIR/icon_512x512@2x.png"

echo "Converting iconset to icns..."
iconutil -c icns "$ICONSET_DIR" -o temp_icon.icns

echo "Replacing existing icon..."
mv temp_icon.icns "$DEST_ICNS"

echo "Cleaning up..."
rm -rf "$ICONSET_DIR"

echo "Touching app to refresh cache..."
touch "CNC Plywood Box Maker.app"

echo "Done!"

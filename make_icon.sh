#!/bin/bash
# Convert icon.png to proper macOS .icns for the dock
# Run after saving your logo as riot_ai/static/icon.png

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC="$SCRIPT_DIR/static/icon.png"
APP_RESOURCES="$SCRIPT_DIR/../RIOT AI.app/Contents/Resources"

if [ ! -f "$SRC" ]; then
    echo "❌ icon.png not found at $SRC"
    exit 1
fi

echo "🎨 Converting logo to macOS icon..."

# Create iconset
ICONSET="$SCRIPT_DIR/AppIcon.iconset"
mkdir -p "$ICONSET"

# Generate all required sizes
sips -z 16 16     "$SRC" --out "$ICONSET/icon_16x16.png"
sips -z 32 32     "$SRC" --out "$ICONSET/icon_16x16@2x.png"
sips -z 32 32     "$SRC" --out "$ICONSET/icon_32x32.png"
sips -z 64 64     "$SRC" --out "$ICONSET/icon_32x32@2x.png"
sips -z 128 128   "$SRC" --out "$ICONSET/icon_128x128.png"
sips -z 256 256   "$SRC" --out "$ICONSET/icon_128x128@2x.png"
sips -z 256 256   "$SRC" --out "$ICONSET/icon_256x256.png"
sips -z 512 512   "$SRC" --out "$ICONSET/icon_256x256@2x.png"
sips -z 512 512   "$SRC" --out "$ICONSET/icon_512x512.png"
sips -z 1024 1024 "$SRC" --out "$ICONSET/icon_512x512@2x.png"

# Convert to .icns
iconutil -c icns "$ICONSET" -o "$APP_RESOURCES/AppIcon.icns"

# Cleanup
rm -rf "$ICONSET"

# Also copy png for favicon
cp "$SRC" "$APP_RESOURCES/AppIcon.png"

echo "✅ AppIcon.icns created at $APP_RESOURCES/AppIcon.icns"

# Force macOS to refresh the icon cache
touch "/Applications/RIOT AI.app" 2>/dev/null
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "/Applications/RIOT AI.app" 2>/dev/null

echo "✅ Icon cache refreshed"
echo "🖤 Your logo is now the dock icon!"

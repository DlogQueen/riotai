#!/bin/bash
# RIOT AI - Install as permanent app + auto-start daemon
# Run this ONCE from Terminal

set -e
RIOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_SOURCE="$( cd "$RIOT_DIR/.." && pwd )/RIOT AI.app"

echo "🖤 Installing RIOT AI..."
echo "================================"

# 1. Create log directory
mkdir -p "$HOME/Library/Logs/RIOTAI"
echo "✅ Log directory created"

# 2. Install Python deps
echo "📦 Installing dependencies..."
/opt/local/bin/python3 -m pip install flask openai requests -q
echo "✅ Dependencies installed"

# 3. Copy .app to Applications
if [ -d "$APP_SOURCE" ]; then
    cp -r "$APP_SOURCE" "/Applications/RIOT AI.app"
    echo "✅ RIOT AI.app copied to /Applications"
else
    echo "⚠️  App bundle not found at: $APP_SOURCE"
fi

# 4. Install LaunchAgent (auto-start on login + keep alive)
PLIST_SRC="$RIOT_DIR/dev.riotai.server.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/dev.riotai.server.plist"

cp "$PLIST_SRC" "$PLIST_DEST"
echo "✅ LaunchAgent installed"

# 5. Load it now (starts immediately, no reboot needed)
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"
echo "✅ Daemon started"

# 6. Wait and open
sleep 2
open http://localhost:5001

echo ""
echo "================================"
echo "🖤 RIOT AI is installed and running!"
echo "🚀 Opens automatically on every login"
echo "🔄 Restarts automatically if it crashes"
echo "📍 Always at: http://localhost:5000"
echo "📋 Logs: ~/Library/Logs/RIOTAI/"
echo ""
echo "To add to Dock: open /Applications and drag RIOT AI.app to your Dock"
echo "================================"

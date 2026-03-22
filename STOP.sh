#!/bin/bash
# Stop RIOT AI daemon (temporarily - will restart on next login)
PLIST="$HOME/Library/LaunchAgents/dev.riotai.server.plist"
launchctl unload "$PLIST" 2>/dev/null && echo "🛑 RIOT AI daemon stopped" || echo "⚠️ Daemon not running"
lsof -ti:5000 | xargs kill -9 2>/dev/null && echo "🛑 Server killed" || true

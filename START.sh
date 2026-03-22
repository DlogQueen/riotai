#!/bin/bash
cd "$(dirname "$0")"

echo "🖤 RIOT AI - Starting up..."
echo "================================"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 not found"
    exit 1
fi

# Install core deps if needed
pip install flask openai requests -q

# Start server
echo "🚀 Launching on http://localhost:5000"
echo "🖤 Break rules. Build empires. Stay punk. ⚡"
echo "================================"

python3 server.py &
SERVER_PID=$!

# Open browser after 1.5s
sleep 1.5
open http://localhost:5001

wait $SERVER_PID

#!/bin/bash
# Coach Bear AI - local dev launcher
cd "$(dirname "$0")"

echo "🏈 Coach Bear AI - warming up..."
echo "================================"

if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 not found"
    exit 1
fi

if [ ! -f .env ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  No .env and no OPENAI_API_KEY set - copy .env.example to .env and add your key."
fi

pip install -r requirements.txt -q

echo "🚀 Launching on http://localhost:5001"
echo "================================"

python3 server.py

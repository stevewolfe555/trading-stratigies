#!/bin/bash

# Stop Laravel Trading App

echo "🛑 Stopping Trading App..."

# Kill processes on ports 8000 and 8080
lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "✅ Stopped Laravel (port 8000)" || echo "ℹ️  No Laravel process found"
lsof -ti:8080 | xargs kill -9 2>/dev/null && echo "✅ Stopped Reverb (port 8080)" || echo "ℹ️  No Reverb process found"

echo ""
echo "✅ Trading App stopped!"

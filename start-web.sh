#!/bin/bash

# Start Laravel Trading App with WebSockets
# This script starts both the web server and Reverb WebSocket server

echo "🚀 Starting Trading App..."
echo ""

# Change to web directory
cd "$(dirname "$0")/web"

# Kill any existing processes on ports 8000 and 8080
echo "🧹 Cleaning up existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:8080 | xargs kill -9 2>/dev/null || true

# Start Reverb WebSocket server in background
echo "📡 Starting Reverb WebSocket server on port 8080..."
php artisan reverb:start > ../logs/reverb.log 2>&1 &
REVERB_PID=$!

# Wait for Reverb to start
sleep 2

# Start Laravel web server in background
echo "🌐 Starting Laravel web server on port 8000..."
php artisan serve > ../logs/laravel.log 2>&1 &
LARAVEL_PID=$!

# Wait for Laravel to start
sleep 2

echo ""
echo "✅ Trading App Started!"
echo ""
echo "📊 Dashboard: http://localhost:8000"
echo "📡 WebSockets: ws://localhost:8080"
echo ""
echo "Process IDs:"
echo "  - Laravel: $LARAVEL_PID"
echo "  - Reverb: $REVERB_PID"
echo ""
echo "📝 Logs:"
echo "  - Laravel: logs/laravel.log"
echo "  - Reverb: logs/reverb.log"
echo ""
echo "To stop: ./stop-web.sh"
echo "To view logs: tail -f logs/laravel.log logs/reverb.log"

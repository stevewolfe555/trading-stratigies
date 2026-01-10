#!/bin/bash

# Phase 3 Testing Setup Script
# Prepares environment for binary options arbitrage testing

set -e  # Exit on error

echo "🚀 Phase 3: Binary Options Arbitrage Testing Setup"
echo "=================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "web/artisan" ]; then
    echo "❌ Error: Please run this script from the trading-stratigies root directory"
    exit 1
fi

# Step 1: Install Laravel dependencies
echo "📦 Step 1: Installing Laravel dependencies..."
cd web
if [ ! -d "vendor" ]; then
    composer install
    echo -e "${GREEN}✅ Laravel dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠️  Laravel dependencies already installed${NC}"
fi
cd ..

# Step 2: Install Python dependencies (engine)
echo ""
echo "🐍 Step 2: Installing Python dependencies (engine)..."
cd services/engine
pip install -r requirements.txt
echo -e "${GREEN}✅ Engine dependencies installed${NC}"
cd ../..

# Step 3: Install Python dependencies (ingestion)
echo ""
echo "🐍 Step 3: Installing Python dependencies (ingestion)..."
cd services/ingestion
pip install -r requirements.txt
echo -e "${GREEN}✅ Ingestion dependencies installed${NC}"
cd ../..

# Step 4: Check database connection
echo ""
echo "🗄️  Step 4: Checking database connection..."
if command -v psql &> /dev/null; then
    DB_HOST=${DB_HOST:-localhost}
    DB_NAME=${DB_NAME:-trading}
    DB_USER=${DB_USER:-postgres}

    if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
        echo -e "${GREEN}✅ Database connection successful${NC}"
    else
        echo -e "${YELLOW}⚠️  Database connection failed. Please check your .env file${NC}"
        echo "   Make sure TimescaleDB is running: docker-compose up -d timescale"
    fi
else
    echo -e "${YELLOW}⚠️  psql not found, skipping database check${NC}"
fi

# Step 5: Run database migrations
echo ""
echo "📊 Step 5: Running database migrations..."
cd web
php artisan migrate --force
echo -e "${GREEN}✅ Database migrations complete${NC}"
cd ..

# Step 6: Summary
echo ""
echo "=================================================="
echo -e "${GREEN}✅ Phase 3 Setup Complete!${NC}"
echo "=================================================="
echo ""
echo "Next steps:"
echo ""
echo "1️⃣  Fetch Polymarket markets:"
echo "   cd services/engine"
echo "   python -m app.utils.market_fetcher --limit 50 --categories politics sports"
echo ""
echo "2️⃣  Start monitoring (paper trading):"
echo "   python -m app.utils.arbitrage_monitor --mode paper --capital 500"
echo ""
echo "3️⃣  Review testing guide:"
echo "   cat docs/PHASE3_TESTING_GUIDE.md"
echo ""
echo "📚 Documentation:"
echo "   - Testing Guide: docs/PHASE3_TESTING_GUIDE.md"
echo "   - API Research: docs/POLYMARKET_API_RESEARCH.md"
echo "   - Design Doc: docs/BINARY_OPTIONS_DESIGN.md"
echo ""

#!/bin/bash

# Reset all trading data (keeps schema, removes data)
# This is useful for starting fresh with clean data

set -e

echo "🧹 Resetting trading data..."
echo ""
echo "This will delete:"
echo "  - All candles"
echo "  - All ticks"
echo "  - All signals"
echo "  - All volume profile data"
echo "  - All order flow data"
echo "  - All market state data"
echo ""
echo "Symbols and strategies will be preserved."
echo ""
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Truncating tables..."

docker compose exec -T db psql -U postgres -d trading <<EOF
-- Truncate data tables (CASCADE handles foreign keys)
TRUNCATE TABLE ticks CASCADE;
TRUNCATE TABLE volume_profile CASCADE;
TRUNCATE TABLE profile_metrics CASCADE;
TRUNCATE TABLE order_flow CASCADE;
TRUNCATE TABLE market_state CASCADE;
TRUNCATE TABLE signals CASCADE;
TRUNCATE TABLE candles CASCADE;

-- Verify counts
SELECT 'candles' as table_name, COUNT(*) as count FROM candles
UNION ALL
SELECT 'ticks', COUNT(*) FROM ticks
UNION ALL
SELECT 'signals', COUNT(*) FROM signals
UNION ALL
SELECT 'volume_profile', COUNT(*) FROM volume_profile
UNION ALL
SELECT 'profile_metrics', COUNT(*) FROM profile_metrics
UNION ALL
SELECT 'order_flow', COUNT(*) FROM order_flow
UNION ALL
SELECT 'market_state', COUNT(*) FROM market_state;
EOF

echo ""
echo "✅ Data reset complete!"
echo ""
echo "Next steps:"
echo "  1. Restart ingestion: docker compose restart ingestion"
echo "  2. Wait 60-120 seconds for data to populate"
echo "  3. Refresh dashboard: http://127.0.0.1:8002/dashboard"
echo ""

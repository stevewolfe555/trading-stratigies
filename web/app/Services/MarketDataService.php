<?php

namespace App\Services;

use Illuminate\Support\Facades\DB;

class MarketDataService
{
    /**
     * Load candle data for a symbol
     */
    public function loadCandles(string $symbol, string $timeframe): array
    {
        $symbolId = $this->getSymbolId($symbol);
        if (!$symbolId) {
            return ['labels' => [], 'closes' => []];
        }

        $interval = $this->getTimeframeInterval($timeframe);
        $limit = $this->getTimeframeLimit($timeframe);

        $candles = DB::select("
            SELECT 
                time_bucket(?, time) AS bucket,
                FIRST(open, time) as open,
                MAX(high) as high,
                MIN(low) as low,
                LAST(close, time) as close,
                SUM(volume) as volume
            FROM candles
            WHERE symbol_id = ?
                AND time >= NOW() - INTERVAL '7 days'
            GROUP BY bucket
            ORDER BY bucket DESC
            LIMIT ?
        ", [$interval, $symbolId, $limit]);

        $labels = [];
        $closes = [];

        foreach (array_reverse($candles) as $candle) {
            $time = new \DateTime($candle->bucket);
            $time->setTimezone(new \DateTimeZone('America/New_York'));
            $labels[] = $time->format('m/d H:i');
            $closes[] = (float) $candle->close;
        }

        return compact('labels', 'closes');
    }

    /**
     * Load trading signals for a symbol
     */
    public function loadSignals(string $symbol): array
    {
        $symbolId = $this->getSymbolId($symbol);
        if (!$symbolId) {
            return [];
        }

        // Get signals with nearest candle price using subquery
        $signals = DB::select("
            SELECT s.time, s.type, 
                   (SELECT c.close 
                    FROM candles c 
                    WHERE c.symbol_id = s.symbol_id 
                      AND c.time <= s.time 
                    ORDER BY c.time DESC 
                    LIMIT 1) as price
            FROM signals s 
            WHERE s.symbol_id = ? 
            ORDER BY s.time ASC 
            LIMIT 100
        ", [$symbolId]);

        // Filter out signals without valid prices
        return array_filter(array_map(fn($s) => [
            'time' => $s->time,
            'type' => $s->type,
            'price' => (float) ($s->price ?? 0),
        ], $signals), fn($s) => $s['price'] > 0);
    }

    /**
     * Load volume profile data
     */
    public function loadVolumeProfile(string $symbol): array
    {
        $symbolId = $this->getSymbolId($symbol);
        if (!$symbolId) {
            return [];
        }

        $profile = DB::selectOne("
            SELECT poc, vah, val
            FROM profile_metrics
            WHERE symbol_id = ?
            ORDER BY bucket DESC
            LIMIT 1
        ", [$symbolId]);

        if (!$profile) {
            return [];
        }

        return [
            'poc' => (float) $profile->poc,
            'vah' => (float) $profile->vah,
            'val' => (float) $profile->val,
        ];
    }

    /**
     * Load order flow data
     */
    public function loadOrderFlow(string $symbol): array
    {
        $symbolId = $this->getSymbolId($symbol);
        if (!$symbolId) {
            return [];
        }

        $flow = DB::selectOne("
            SELECT 
                cumulative_delta,
                buy_pressure,
                sell_pressure
            FROM order_flow
            WHERE symbol_id = ?
            ORDER BY bucket DESC
            LIMIT 1
        ", [$symbolId]);

        if (!$flow) {
            return [];
        }

        return [
            'cvd' => (int) $flow->cumulative_delta,
            'buy_pressure' => (float) $flow->buy_pressure,
            'sell_pressure' => (float) $flow->sell_pressure,
        ];
    }

    /**
     * Get symbol ID from symbol name
     */
    private function getSymbolId(string $symbol): ?int
    {
        $result = DB::selectOne("SELECT id FROM symbols WHERE symbol = ?", [$symbol]);
        return $result->id ?? null;
    }

    /**
     * Get time bucket interval for timeframe
     */
    private function getTimeframeInterval(string $timeframe): string
    {
        return match($timeframe) {
            '1m' => '1 minute',
            '5m' => '5 minutes',
            '15m' => '15 minutes',
            '30m' => '30 minutes',
            '1h' => '1 hour',
            '1d' => '1 day',
            default => '1 minute',
        };
    }

    /**
     * Get data limit for timeframe
     */
    private function getTimeframeLimit(string $timeframe): int
    {
        return match($timeframe) {
            '1m' => 390,   // 1 trading day
            '5m' => 390,   // ~3 days
            '15m' => 390,  // ~10 days
            '30m' => 390,  // ~20 days
            '1h' => 390,   // ~40 days
            '1d' => 252,   // 1 year
            default => 390,
        };
    }
}

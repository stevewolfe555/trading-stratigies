<?php

namespace App\Services;

use Illuminate\Support\Facades\DB;

class TradingMetricsService
{
    /**
     * Load market state for a symbol
     */
    public function loadMarketState(string $symbol): array
    {
        $symbolId = $this->getSymbolId($symbol);
        if (!$symbolId) {
            return [];
        }

        $state = DB::selectOne("
            SELECT state, confidence
            FROM market_state
            WHERE symbol_id = ?
            ORDER BY time DESC
            LIMIT 1
        ", [$symbolId]);

        if (!$state) {
            return [];
        }

        return [
            'state' => $state->state,
            'confidence' => (int) $state->confidence,
        ];
    }

    /**
     * Load LVN alert for a symbol
     */
    public function loadLVNAlert(string $symbol): array
    {
        $symbolId = $this->getSymbolId($symbol);
        if (!$symbolId) {
            return [];
        }

        // Get current price
        $currentPrice = DB::selectOne("
            SELECT close
            FROM candles
            WHERE symbol_id = ?
            ORDER BY time DESC
            LIMIT 1
        ", [$symbolId]);

        if (!$currentPrice) {
            return [];
        }

        $price = (float) $currentPrice->close;

        // Get LVNs from volume profile
        $lvns = DB::select("
            SELECT price_level, total_volume
            FROM volume_profile
            WHERE symbol_id = ?
                AND total_volume < (
                    SELECT AVG(total_volume) * 0.7
                    FROM volume_profile
                    WHERE symbol_id = ?
                )
            ORDER BY ABS(price_level - ?) ASC
            LIMIT 3
        ", [$symbolId, $symbolId, $price]);

        if (empty($lvns)) {
            return [];
        }

        $nearestLVN = $lvns[0];
        $lvnPrice = (float) $nearestLVN->price_level;
        $distance = abs($price - $lvnPrice);
        $distancePct = ($distance / $price) * 100;

        $direction = $price < $lvnPrice ? 'UP' : 'DOWN';
        $isNear = $distancePct <= 0.5; // Alert threshold

        return [
            'alert' => $isNear,
            'lvn_price' => round($lvnPrice, 2),
            'current_price' => round($price, 2),
            'distance_pct' => round($distancePct, 2),
            'distance_dollars' => round($distance, 2),
            'direction' => $direction,
        ];
    }

    /**
     * Load aggressive flow metrics
     */
    public function loadAggressiveFlow(string $symbol): array
    {
        $symbolId = $this->getSymbolId($symbol);
        if (!$symbolId) {
            return $this->getEmptyAggressiveFlow();
        }

        // Get most recent order flow data (last 5 buckets)
        $flow = DB::select("
            SELECT delta, cumulative_delta, buy_pressure, sell_pressure
            FROM order_flow
            WHERE symbol_id = ?
            ORDER BY bucket DESC
            LIMIT 5
        ", [$symbolId]);

        if (empty($flow)) {
            return $this->getEmptyAggressiveFlow();
        }

        // Get recent volume (last candle vs average)
        $volumeData = DB::selectOne("
            SELECT 
                (SELECT AVG(volume) FROM candles WHERE symbol_id = ? LIMIT 100) as avg_volume,
                (SELECT volume FROM candles WHERE symbol_id = ? ORDER BY time DESC LIMIT 1) as recent_volume
        ", [$symbolId, $symbolId]);

        $avgVolume = $volumeData->avg_volume ?? 1;
        $recentVolume = $volumeData->recent_volume ?? 0;
        $volumeRatio = $avgVolume > 0 ? $recentVolume / $avgVolume : 1.0;

        // Calculate metrics
        $currentFlow = $flow[0];
        $buyPressure = (float) ($currentFlow->buy_pressure ?? 50);
        $sellPressure = (float) ($currentFlow->sell_pressure ?? 50);
        
        // CVD momentum
        $cvdMomentum = 0;
        if (count($flow) >= 2) {
            $cvdStart = (int) ($flow[count($flow)-1]->cumulative_delta ?? 0);
            $cvdEnd = (int) ($flow[0]->cumulative_delta ?? 0);
            $cvdMomentum = $cvdEnd - $cvdStart;
        }

        // Calculate score
        $score = 0;
        if ($volumeRatio >= 2.0) $score += 20;
        if (abs($cvdMomentum) >= 1000) $score += 30;
        if ($buyPressure >= 70 || $sellPressure >= 70) $score += 20;

        // Determine direction
        if ($buyPressure >= 70) {
            $direction = 'BUY';
        } elseif ($sellPressure >= 70) {
            $direction = 'SELL';
        } elseif ($cvdMomentum > 500) {
            $direction = 'BUY';
        } elseif ($cvdMomentum < -500) {
            $direction = 'SELL';
        } else {
            $direction = 'NEUTRAL';
        }

        return [
            'score' => min(100, (int) $score),
            'direction' => $direction,
            'volume_ratio' => round($volumeRatio, 2),
            'cvd_momentum' => $cvdMomentum,
            'buy_pressure' => round($buyPressure, 1),
            'sell_pressure' => round($sellPressure, 1),
            'is_aggressive' => $score >= 50
        ];
    }

    /**
     * Get empty aggressive flow data
     */
    private function getEmptyAggressiveFlow(): array
    {
        return [
            'score' => 0,
            'direction' => 'NEUTRAL',
            'volume_ratio' => 1.0,
            'cvd_momentum' => 0,
            'buy_pressure' => 50.0,
            'sell_pressure' => 50.0,
            'is_aggressive' => false
        ];
    }

    /**
     * Get session information
     */
    public function getSessionInfo(): array
    {
        $now = new \DateTime('now', new \DateTimeZone('America/New_York'));
        $hour = (int) $now->format('H');
        $minute = (int) $now->format('i');
        $timeInMinutes = ($hour * 60) + $minute;

        // Market hours: 09:30 - 16:00 ET
        $marketOpen = (9 * 60) + 30;  // 570
        $marketClose = 16 * 60;        // 960

        $currentSession = 'CLOSED';
        $sessionIcon = '🌙';
        $recommendedSetup = 'Market Closed';

        $sessionName = 'Market Closed';
        
        if ($timeInMinutes >= $marketOpen && $timeInMinutes < $marketClose) {
            $currentSession = 'NEW_YORK';
            $sessionIcon = '🗽';
            $sessionName = 'New York Session';
            $recommendedSetup = 'Trend Model + Mean Reversion';
        }

        return [
            'session' => $currentSession,
            'name' => $sessionName,
            'icon' => $sessionIcon,
            'time_et' => $now->format('H:i T'),
            'recommended_setup' => $recommendedSetup,
            'is_market_hours' => $currentSession === 'NEW_YORK',
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
}

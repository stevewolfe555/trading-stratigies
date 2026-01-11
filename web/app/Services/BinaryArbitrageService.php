<?php

namespace App\Services;

use Illuminate\Support\Facades\DB;
use App\Models\BinaryMarket;
use App\Models\BinaryPosition;
use App\Models\BinaryPrice;

class BinaryArbitrageService
{
    // Configuration constants
    private const MAX_BINARY_CAPITAL = 400; // £400 max allocation
    private const MAX_POSITION_SIZE = 100;  // £100 per position

    /**
     * Get capital allocation overview
     */
    public function getCapitalAllocation(): array
    {
        $totalExposure = $this->getTotalExposure();
        $available = self::MAX_BINARY_CAPITAL - $totalExposure;

        // Get win rate for display
        $winRate = $this->getWinRate();

        return [
            'total' => self::MAX_BINARY_CAPITAL,
            'used' => $totalExposure,
            'available' => max(0, $available),
            'win_rate' => $winRate,
        ];
    }

    /**
     * Get available capital for new positions
     */
    public function getAvailableCapital(): float
    {
        $totalExposure = $this->getTotalExposure();
        return max(0, self::MAX_BINARY_CAPITAL - $totalExposure);
    }

    /**
     * Get total exposure from open positions
     */
    public function getTotalExposure(): float
    {
        $result = DB::selectOne("
            SELECT COALESCE(SUM((yes_qty * yes_entry_price) + (no_qty * no_entry_price)), 0) as total
            FROM binary_positions
            WHERE status = 'open'
        ");

        return (float) ($result->total ?? 0);
    }

    /**
     * Get active arbitrage opportunities
     */
    public function getActiveOpportunities(int $limit = 10): array
    {
        $opportunities = DB::select("
            SELECT
                bp.symbol_id,
                s.symbol,
                bm.id as market_id,
                bm.market_id as polymarket_market_id,
                bm.question,
                bm.end_date,
                bp.yes_ask,
                bp.no_ask,
                bp.spread,
                bp.estimated_profit_pct,
                bp.timestamp
            FROM binary_prices bp
            JOIN symbols s ON bp.symbol_id = s.id
            JOIN binary_markets bm ON bm.symbol_id = s.id
            WHERE bp.arbitrage_opportunity = true
                AND bm.status = 'active'
                AND bp.timestamp > NOW() - INTERVAL '10 seconds'
            ORDER BY bp.estimated_profit_pct DESC, bp.timestamp DESC
            LIMIT ?
        ", [$limit]);

        return array_map(function($opp) {
            return [
                'symbol_id' => $opp->symbol_id,
                'symbol' => $opp->symbol,
                'market_id' => $opp->market_id,
                'polymarket_market_id' => $opp->polymarket_market_id,
                'question' => $opp->question,
                'end_date' => $opp->end_date,
                'yes_ask' => (float) $opp->yes_ask,
                'no_ask' => (float) $opp->no_ask,
                'spread' => (float) $opp->spread,
                'estimated_profit_pct' => (float) $opp->estimated_profit_pct,
                'timestamp' => $opp->timestamp,
            ];
        }, $opportunities);
    }

    /**
     * Get opportunity details for a specific market
     */
    public function getOpportunityDetails(int $marketId): ?array
    {
        $opp = DB::selectOne("
            SELECT
                bp.symbol_id,
                s.symbol,
                bm.id as market_id,
                bm.market_id as polymarket_market_id,
                bm.question,
                bm.description,
                bm.end_date,
                bp.yes_ask,
                bp.no_ask,
                bp.yes_bid,
                bp.no_bid,
                bp.spread,
                bp.estimated_profit_pct,
                bp.timestamp
            FROM binary_prices bp
            JOIN symbols s ON bp.symbol_id = s.id
            JOIN binary_markets bm ON bm.symbol_id = s.id
            WHERE bm.id = ?
                AND bp.arbitrage_opportunity = true
                AND bp.timestamp > NOW() - INTERVAL '10 seconds'
            ORDER BY bp.timestamp DESC
            LIMIT 1
        ", [$marketId]);

        if (!$opp) {
            return null;
        }

        return [
            'symbol_id' => $opp->symbol_id,
            'symbol' => $opp->symbol,
            'market_id' => $opp->market_id,
            'polymarket_market_id' => $opp->polymarket_market_id,
            'question' => $opp->question,
            'description' => $opp->description,
            'end_date' => $opp->end_date,
            'yes_ask' => (float) $opp->yes_ask,
            'no_ask' => (float) $opp->no_ask,
            'yes_bid' => (float) $opp->yes_bid,
            'no_bid' => (float) $opp->no_bid,
            'spread' => (float) $opp->spread,
            'estimated_profit_pct' => (float) $opp->estimated_profit_pct,
            'timestamp' => $opp->timestamp,
        ];
    }

    /**
     * Get open positions
     */
    public function getOpenPositions(): array
    {
        $positions = DB::select("
            SELECT
                bp.id,
                bp.symbol_id,
                s.symbol,
                bm.question,
                bm.end_date,
                bp.yes_qty,
                bp.no_qty,
                bp.yes_entry_price,
                bp.no_entry_price,
                bp.entry_spread,
                bp.opened_at,
                (1.00 - bp.entry_spread) * (bp.yes_qty + bp.no_qty) as locked_profit,
                ((1.00 - bp.entry_spread) / bp.entry_spread) * 100 as locked_profit_pct,
                EXTRACT(DAY FROM (NOW() - bp.opened_at)) as days_held
            FROM binary_positions bp
            JOIN symbols s ON bp.symbol_id = s.id
            JOIN binary_markets bm ON bm.symbol_id = s.id
            WHERE bp.status = 'open'
            ORDER BY bp.opened_at DESC
        ");

        return array_map(function($pos) {
            return [
                'id' => $pos->id,
                'symbol_id' => $pos->symbol_id,
                'symbol' => $pos->symbol,
                'question' => $pos->question,
                'end_date' => $pos->end_date,
                'yes_qty' => (float) $pos->yes_qty,
                'no_qty' => (float) $pos->no_qty,
                'yes_entry_price' => (float) $pos->yes_entry_price,
                'no_entry_price' => (float) $pos->no_entry_price,
                'entry_spread' => (float) $pos->entry_spread,
                'opened_at' => $pos->opened_at,
                'locked_profit' => (float) $pos->locked_profit,
                'locked_profit_pct' => (float) $pos->locked_profit_pct,
                'days_held' => (int) $pos->days_held,
            ];
        }, $positions);
    }

    /**
     * Get closed positions (recent history)
     */
    public function getClosedPositions(int $limit = 20): array
    {
        $positions = DB::select("
            SELECT
                bp.id,
                bp.symbol_id,
                s.symbol,
                bm.question,
                bp.entry_spread,
                bp.profit_loss,
                bp.profit_loss_pct,
                bp.resolution,
                bp.closed_at,
                bp.opened_at,
                EXTRACT(DAY FROM (bp.closed_at - bp.opened_at)) as days_held
            FROM binary_positions bp
            JOIN symbols s ON bp.symbol_id = s.id
            JOIN binary_markets bm ON bm.symbol_id = s.id
            WHERE bp.status IN ('closed', 'resolved')
            ORDER BY bp.closed_at DESC
            LIMIT ?
        ", [$limit]);

        return array_map(function($pos) {
            return [
                'id' => $pos->id,
                'symbol_id' => $pos->symbol_id,
                'symbol' => $pos->symbol,
                'question' => $pos->question,
                'entry_spread' => (float) $pos->entry_spread,
                'profit_loss' => (float) ($pos->profit_loss ?? 0),
                'profit_loss_pct' => (float) ($pos->profit_loss_pct ?? 0),
                'resolution' => $pos->resolution,
                'closed_at' => $pos->closed_at,
                'opened_at' => $pos->opened_at,
                'days_held' => (int) $pos->days_held,
            ];
        }, $positions);
    }

    /**
     * Get performance metrics
     */
    public function getPerformanceMetrics(): array
    {
        $metrics = DB::selectOne("
            SELECT
                COUNT(*) as total_positions,
                COALESCE(SUM(profit_loss), 0) as total_profit,
                COALESCE(AVG(profit_loss), 0) as avg_profit,
                COALESCE(AVG(profit_loss_pct), 0) as avg_profit_pct,
                COALESCE(AVG(EXTRACT(DAY FROM (closed_at - opened_at))), 0) as avg_hold_time
            FROM binary_positions
            WHERE status IN ('closed', 'resolved')
        ");

        // Calculate total profit percentage relative to capital used
        $totalCostBasis = DB::selectOne("
            SELECT COALESCE(SUM((yes_qty * yes_entry_price) + (no_qty * no_entry_price)), 0) as total
            FROM binary_positions
            WHERE status IN ('closed', 'resolved')
        ");

        $totalProfitPct = 0;
        if ($totalCostBasis && $totalCostBasis->total > 0) {
            $totalProfitPct = (($metrics->total_profit ?? 0) / $totalCostBasis->total) * 100;
        }

        return [
            'total_positions' => (int) ($metrics->total_positions ?? 0),
            'total_profit' => (float) ($metrics->total_profit ?? 0),
            'total_profit_pct' => $totalProfitPct,
            'avg_profit' => (float) ($metrics->avg_profit ?? 0),
            'avg_profit_pct' => (float) ($metrics->avg_profit_pct ?? 0),
            'avg_hold_time' => (float) ($metrics->avg_hold_time ?? 0),
            'win_rate' => $this->getWinRate(),
        ];
    }

    /**
     * Get win rate percentage
     */
    public function getWinRate(): float
    {
        $result = DB::selectOne("
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins
            FROM binary_positions
            WHERE status IN ('closed', 'resolved')
                AND profit_loss IS NOT NULL
        ");

        if (!$result || $result->total == 0) {
            return 100.0; // Default to 100% when no positions (arbitrage should guarantee profit)
        }

        return (($result->wins / $result->total) * 100);
    }

    /**
     * Get average profit per trade
     */
    public function getAverageProfit(): float
    {
        $result = DB::selectOne("
            SELECT COALESCE(AVG(profit_loss), 0) as avg_profit
            FROM binary_positions
            WHERE status IN ('closed', 'resolved')
        ");

        return (float) ($result->avg_profit ?? 0);
    }

    /**
     * Get average hold time in days
     */
    public function getAverageHoldTime(): float
    {
        $result = DB::selectOne("
            SELECT COALESCE(AVG(EXTRACT(DAY FROM (closed_at - opened_at))), 0) as avg_days
            FROM binary_positions
            WHERE status IN ('closed', 'resolved')
                AND closed_at IS NOT NULL
        ");

        return (float) ($result->avg_days ?? 0);
    }

    /**
     * Execute arbitrage for a market
     *
     * Note: This is a placeholder - actual execution will be handled by the engine service
     */
    public function executeArbitrage(int $marketId): array
    {
        // Get opportunity details
        $opportunity = $this->getOpportunityDetails($marketId);

        if (!$opportunity) {
            return [
                'success' => false,
                'message' => 'Opportunity no longer available or invalid market ID',
            ];
        }

        // Check available capital
        $availableCapital = $this->getAvailableCapital();
        if ($availableCapital < self::MAX_POSITION_SIZE) {
            return [
                'success' => false,
                'message' => sprintf('Insufficient capital. Available: £%.2f', $availableCapital),
            ];
        }

        // Check if we already have a position for this market
        $existing = DB::selectOne("
            SELECT id
            FROM binary_positions
            WHERE symbol_id = ? AND status = 'open'
        ", [$opportunity['symbol_id']]);

        if ($existing) {
            return [
                'success' => false,
                'message' => 'Already have an open position for this market',
            ];
        }

        // In production, this would trigger the engine service to execute the trade
        // For now, we'll just return success to allow UI testing
        return [
            'success' => true,
            'message' => sprintf(
                'Arbitrage execution queued for: %s (Estimated profit: %.2f%%)',
                $opportunity['question'],
                $opportunity['estimated_profit_pct']
            ),
            'opportunity' => $opportunity,
        ];
    }

    /**
     * Close a position early
     *
     * Note: This is a placeholder - actual closing will be handled by the engine service
     */
    public function closePosition(int $positionId): bool
    {
        $position = BinaryPosition::find($positionId);

        if (!$position) {
            return false;
        }

        if ($position->status !== 'open') {
            return false;
        }

        // In production, this would trigger the engine service to close the position
        // For now, we'll just return success
        return true;
    }
}

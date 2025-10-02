<?php

namespace App\Services;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;

class AccountService
{
    /**
     */
    public function loadAccountInfo(): array
    {
        $apiKey = env('ALPACA_API_KEY');
        $secretKey = env('ALPACA_SECRET_KEY');
        $autoTradingEnabled = env('AUTO_TRADING_ENABLED', 'false') === 'true';

        $accountData = [
            'portfolio_value' => 100000.00,
            'buying_power' => 100000.00,
            'cash' => 100000.00,
            'daily_pnl' => 0.00,
            'daily_pnl_pct' => 0.00,
        ];

        $isConnected = false;

        // Try to get real account data from Alpaca if auto-trading is enabled
        if ($autoTradingEnabled && $apiKey && $secretKey) {
            try {
                $response = Http::withHeaders([
                    'APCA-API-KEY-ID' => $apiKey,
                    'APCA-API-SECRET-KEY' => $secretKey,
                ])->get('https://paper-api.alpaca.markets/v2/account');

                if ($response->successful()) {
                    $account = $response->json();
                    $isConnected = true;
                    
                    $dailyPnl = (float) ($account['equity'] - $account['last_equity']);
                    $lastEquity = (float) $account['last_equity'];
                    $dailyPnlPct = $lastEquity > 0 ? ($dailyPnl / $lastEquity) * 100 : 0;
                    
                    $accountData = [
                        'portfolio_value' => (float) $account['portfolio_value'],
                        'buying_power' => (float) $account['buying_power'],
                        'cash' => (float) $account['cash'],
                        'daily_pnl' => $dailyPnl,
                        'daily_pnl_pct' => $dailyPnlPct,
                    ];
                }
            } catch (\Exception $e) {
                // Silent fail and use mock data
            }
        }

        // Count today's trades
        $tradesCount = DB::selectOne(
            "SELECT COUNT(*) as count 
             FROM signals 
             WHERE type IN ('BUY', 'SELL', 'ENTRY', 'EXIT') 
                AND time::date = CURRENT_DATE"
        );
        $tradesToday = $tradesCount->count ?? 0;

        // Calculate win rate (placeholder for now)
        $winRate = $tradesToday > 0 ? 50.0 : 0.0;

        return array_merge($accountData, [
            'risk_per_trade_pct' => (float) env('RISK_PER_TRADE_PCT', 1.0),
            'max_positions' => (int) env('MAX_POSITIONS', 3),
            'max_daily_loss_pct' => (float) env('MAX_DAILY_LOSS_PCT', 3.0),
            'trades_today' => $tradesToday,
            'win_rate' => $winRate,
            'is_connected' => $isConnected,
        ]);
    }

    /**
     * Load open positions from Alpaca
     */
    public function loadPositions(): array
    {
        $apiKey = env('ALPACA_API_KEY');
        $secretKey = env('ALPACA_SECRET_KEY');

        if (!$apiKey || !$secretKey) {
            return [];
        }

        try {
            $response = Http::withHeaders([
                'APCA-API-KEY-ID' => $apiKey,
                'APCA-API-SECRET-KEY' => $secretKey,
            ])->get('https://paper-api.alpaca.markets/v2/positions');

            if ($response->successful()) {
                return $response->json();
            }
        } catch (\Exception $e) {
            // Silent fail
        }

        return [];
    }

    /**
     * Load trade history from database
     */
    public function loadTradeHistory(int $limit = 20): array
    {
        $trades = DB::select("
            SELECT s.time AT TIME ZONE 'America/New_York' as time_et, 
                   s.type, 
                   s.details,
                   sym.symbol
            FROM signals s
            JOIN symbols sym ON s.symbol_id = sym.id
            WHERE s.type IN ('BUY', 'SELL')
            ORDER BY s.time DESC
            LIMIT ?
        ", [$limit]);

        return array_map(function($trade) {
            $details = json_decode($trade->details, true);
            return [
                'time' => $trade->time_et,
                'symbol' => $trade->symbol,
                'type' => $trade->type,
                'qty' => $details['qty'] ?? 0,
                'price' => $details['price'] ?? 0,
                'reason' => $details['reason'] ?? '',
            ];
        }, $trades);
    }
}

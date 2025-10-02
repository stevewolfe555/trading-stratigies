<?php

namespace App\Livewire;

use Illuminate\Support\Facades\DB;
use Livewire\Component;

class Watchlist extends Component
{
    public array $stocks = [];
    public array $openPositions = [];
    public int $tradesCount = 0;
    public array $accountInfo = [];
    public array $engineLogs = [];
    public string $lastUpdate = '';

    public function mount(): void
    {
        $this->loadStocks();
        $this->loadOpenPositions();
        $this->loadAccountInfo();
        $this->loadEngineLogs();
    }

    public function loadEngineLogs(): void
    {
        // Get last 50 lines from engine logs via docker
        try {
            $logs = shell_exec('cd /Users/steve/Projects/trading-strategies && docker compose logs engine --tail 50 2>&1');
            
            if ($logs) {
                // Parse logs into array
                $lines = explode("\n", trim($logs));
                $parsedLogs = [];
                
                foreach (array_reverse(array_slice($lines, -30)) as $line) {
                    if (empty(trim($line))) continue;
                    
                    // Extract timestamp and message
                    if (preg_match('/(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+\|\s+(\w+)\s+\|\s+(.+)/', $line, $matches)) {
                        $parsedLogs[] = [
                            'time' => $matches[1],
                            'level' => $matches[2],
                            'message' => $matches[3],
                        ];
                    } else {
                        // Fallback for lines without standard format
                        $parsedLogs[] = [
                            'time' => date('Y-m-d H:i:s'),
                            'level' => 'INFO',
                            'message' => $line,
                        ];
                    }
                }
                
                $this->engineLogs = $parsedLogs;
            }
        } catch (\Exception $e) {
            $this->engineLogs = [];
        }
    }

    public function loadStocks(): void
    {
        // Reload everything for fresh data
        $this->loadOpenPositions();
        $this->loadAccountInfo();
        $this->loadEngineLogs();
        
        // Get all symbols
        $symbols = DB::table('symbols')->orderBy('symbol')->pluck('symbol', 'id');

        $stocks = [];

        foreach ($symbols as $symbolId => $symbol) {
            // Get latest price
            $priceRow = DB::select(
                'SELECT close, time FROM candles 
                 WHERE symbol_id = ? 
                 ORDER BY time DESC 
                 LIMIT 1',
                [$symbolId]
            );

            $currentPrice = $priceRow[0]->close ?? 0;
            $lastUpdate = $priceRow[0]->time ?? null;

            // Get market state
            $stateRow = DB::select(
                'SELECT state, confidence, poc 
                 FROM market_state 
                 WHERE symbol_id = ? 
                 ORDER BY time DESC 
                 LIMIT 1',
                [$symbolId]
            );

            $marketState = $stateRow[0]->state ?? 'UNKNOWN';
            $confidence = $stateRow[0]->confidence ?? 0;
            $poc = $stateRow[0]->poc ?? 0;

            // Get aggressive flow
            $flowRow = DB::select(
                'SELECT buy_pressure, sell_pressure, cumulative_delta
                 FROM order_flow 
                 WHERE symbol_id = ? 
                 ORDER BY bucket DESC 
                 LIMIT 1',
                [$symbolId]
            );

            $buyPressure = $flowRow[0]->buy_pressure ?? 50;
            $sellPressure = $flowRow[0]->sell_pressure ?? 50;
            $cvd = $flowRow[0]->cumulative_delta ?? 0;

            // Calculate aggression score (simplified)
            $aggressionScore = 0;
            if ($buyPressure >= 70 || $sellPressure >= 70) {
                $aggressionScore += 40;
            }
            if (abs($cvd) >= 1000) {
                $aggressionScore += 30;
            }

            $stocks[] = [
                'symbol' => $symbol,
                'price' => round($currentPrice, 2),
                'market_state' => $marketState,
                'confidence' => (int)$confidence,
                'poc' => round($poc, 2),
                'buy_pressure' => round($buyPressure, 1),
                'sell_pressure' => round($sellPressure, 1),
                'cvd' => (int)$cvd,
                'aggression_score' => $aggressionScore,
                'last_update' => $lastUpdate,
            ];
        }

        $this->stocks = $stocks;
        
        // Update timestamp to force Livewire to detect changes
        $this->lastUpdate = now()->format('H:i:s');
    }

    public function loadOpenPositions(): void
    {
        $apiKey = env('ALPACA_API_KEY');
        $secretKey = env('ALPACA_SECRET_KEY');
        
        $positions = [];
        $pendingOrders = [];
        
        if ($apiKey && $secretKey) {
            try {
                // Get open positions from Alpaca
                $positionsResponse = \Illuminate\Support\Facades\Http::withHeaders([
                    'APCA-API-KEY-ID' => $apiKey,
                    'APCA-API-SECRET-KEY' => $secretKey,
                ])->get('https://paper-api.alpaca.markets/v2/positions');
                
                if ($positionsResponse->successful()) {
                    $positions = collect($positionsResponse->json())->map(function($pos) use ($apiKey, $secretKey) {
                        $entryPrice = (float)$pos['avg_entry_price'];
                        $currentPrice = (float)$pos['current_price'];
                        $qty = (int)$pos['qty'];
                        $unrealizedPl = (float)$pos['unrealized_pl'];
                        $unrealizedPlPct = (float)$pos['unrealized_plpc'] * 100;
                        
                        // Get open orders for this symbol to find TP/SL
                        $takeProfit = null;
                        $stopLoss = null;
                        
                        try {
                            $ordersResponse = \Illuminate\Support\Facades\Http::withHeaders([
                                'APCA-API-KEY-ID' => $apiKey,
                                'APCA-API-SECRET-KEY' => $secretKey,
                            ])->get('https://paper-api.alpaca.markets/v2/orders', [
                                'status' => 'open',
                                'symbols' => $pos['symbol']
                            ]);
                            
                            if ($ordersResponse->successful()) {
                                $orders = $ordersResponse->json();
                                foreach ($orders as $order) {
                                    if ($order['type'] === 'limit' && isset($order['limit_price'])) {
                                        $takeProfit = (float)$order['limit_price'];
                                    } elseif ($order['type'] === 'stop' && isset($order['stop_price'])) {
                                        $stopLoss = (float)$order['stop_price'];
                                    }
                                }
                            }
                        } catch (\Exception $e) {
                            // Silently fail
                        }
                        
                        return [
                            'symbol' => $pos['symbol'],
                            'side' => $pos['side'],
                            'qty' => $qty,
                            'entry_price' => $entryPrice,
                            'current_price' => $currentPrice,
                            'unrealized_pl' => $unrealizedPl,
                            'unrealized_pl_pct' => $unrealizedPlPct,
                            'market_value' => (float)$pos['market_value'],
                            'take_profit' => $takeProfit,
                            'stop_loss' => $stopLoss,
                            'status' => 'FILLED',
                        ];
                    })->toArray();
                }
                
                // Get pending orders from Alpaca
                $ordersResponse = \Illuminate\Support\Facades\Http::withHeaders([
                    'APCA-API-KEY-ID' => $apiKey,
                    'APCA-API-SECRET-KEY' => $secretKey,
                ])->get('https://paper-api.alpaca.markets/v2/orders', [
                    'status' => 'open'
                ]);
                
                if ($ordersResponse->successful()) {
                    $pendingOrders = collect($ordersResponse->json())->map(function($order) {
                        return [
                            'symbol' => $order['symbol'],
                            'side' => $order['side'],
                            'qty' => (int)$order['qty'],
                            'order_type' => $order['type'],
                            'limit_price' => isset($order['limit_price']) ? (float)$order['limit_price'] : null,
                            'submitted_at' => $order['submitted_at'],
                            'status' => 'PENDING',
                        ];
                    })->toArray();
                }
                
            } catch (\Exception $e) {
                logger()->error("Error loading positions/orders: " . $e->getMessage());
            }
        }
        
        // Merge positions and pending orders
        $this->openPositions = array_merge($positions, $pendingOrders);
        
        // Count today's trades (actual fills)
        $this->tradesCount = count($positions);
    }

    public function loadAccountInfo(): void
    {
        // Check if auto-trading is enabled and try to get real account data
        // Temporarily hardcoded to true to bypass env cache issues
        $autoTradingEnabled = true;
        
        logger()->info('Checking auto-trading status', [
            'enabled' => $autoTradingEnabled,
        ]);
        
        $isConnected = false;
        $accountData = [
            'portfolio_value' => 100000.00,
            'buying_power' => 100000.00,
            'cash' => 100000.00,
            'equity' => 100000.00,
            'daily_pnl' => 0.00,
            'daily_pnl_pct' => 0.00,
        ];

        // Try to get real account data from Alpaca if auto-trading is enabled
        if ($autoTradingEnabled) {
            try {
                $apiKey = env('ALPACA_API_KEY');
                $secretKey = env('ALPACA_SECRET_KEY');
                
                logger()->info('Attempting to fetch Alpaca account data', [
                    'has_api_key' => !empty($apiKey),
                    'has_secret_key' => !empty($secretKey),
                ]);
                
                if ($apiKey && $secretKey) {
                    // Call Alpaca API to get account info
                    $response = \Illuminate\Support\Facades\Http::withHeaders([
                        'APCA-API-KEY-ID' => $apiKey,
                        'APCA-API-SECRET-KEY' => $secretKey,
                    ])->get('https://paper-api.alpaca.markets/v2/account');
                    
                    if ($response->successful()) {
                        $account = $response->json();
                        $isConnected = true;
                        
                        $accountData = [
                            'portfolio_value' => (float)$account['portfolio_value'],
                            'buying_power' => (float)$account['buying_power'],
                            'cash' => (float)$account['cash'],
                            'equity' => (float)$account['equity'],
                            'daily_pnl' => (float)($account['equity'] - $account['last_equity']),
                            'daily_pnl_pct' => $account['last_equity'] > 0 
                                ? (($account['equity'] - $account['last_equity']) / $account['last_equity'] * 100)
                                : 0,
                        ];
                        
                        logger()->info('Successfully fetched Alpaca account data', [
                            'portfolio_value' => $accountData['portfolio_value'],
                            'daily_pnl' => $accountData['daily_pnl'],
                        ]);
                    } else {
                        logger()->error('Alpaca API returned error', [
                            'status' => $response->status(),
                            'body' => $response->body(),
                        ]);
                    }
                }
            } catch (\Exception $e) {
                // Log error but continue with mock data
                logger()->error('Failed to fetch Alpaca account data: ' . $e->getMessage());
            }
        }

        $this->accountInfo = array_merge($accountData, [
            'risk_per_trade_pct' => (float)env('RISK_PER_TRADE_PCT', 1.0),
            'max_positions' => (int)env('MAX_POSITIONS', 3),
            'max_daily_loss_pct' => (float)env('MAX_DAILY_LOSS_PCT', 3.0),
            'trades_today' => $this->tradesCount,
            'is_connected' => $isConnected,
        ]);
        
        logger()->info('Account info set', ['is_connected' => $isConnected, 'portfolio_value' => $this->accountInfo['portfolio_value']]);
    }

    public function closePosition($symbol)
    {
        try {
            $apiKey = env('ALPACA_API_KEY');
            $secretKey = env('ALPACA_SECRET_KEY');
            
            if (!$apiKey || !$secretKey) {
                session()->flash('error', 'Alpaca API keys not configured');
                return;
            }
            
            $headers = [
                'APCA-API-KEY-ID' => $apiKey,
                'APCA-API-SECRET-KEY' => $secretKey,
            ];
            
            // Step 1: Cancel all open orders for this symbol
            $ordersResponse = \Illuminate\Support\Facades\Http::withHeaders($headers)
                ->get('https://paper-api.alpaca.markets/v2/orders', [
                    'status' => 'open',
                    'symbols' => $symbol,
                ]);
            
            if ($ordersResponse->successful()) {
                $orders = $ordersResponse->json();
                foreach ($orders as $order) {
                    \Illuminate\Support\Facades\Http::withHeaders($headers)
                        ->delete("https://paper-api.alpaca.markets/v2/orders/{$order['id']}");
                }
            }
            
            // Step 2: Close the position
            $response = \Illuminate\Support\Facades\Http::withHeaders($headers)
                ->delete("https://paper-api.alpaca.markets/v2/positions/{$symbol}");
            
            if ($response->successful()) {
                session()->flash('success', "Position {$symbol} closed successfully! Orders cancelled and position exited at market.");
                $this->loadAccountInfo();
            } else {
                session()->flash('error', "Failed to close {$symbol}: " . $response->body());
            }
            
        } catch (\Exception $e) {
            session()->flash('error', 'Error closing position: ' . $e->getMessage());
        }
    }

    public function render()
    {
        return view('livewire.watchlist');
    }
}

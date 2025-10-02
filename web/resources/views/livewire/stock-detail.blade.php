<div class="space-y-4" wire:poll.3s>
    <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
            <a href="{{ route('watchlist') }}" class="px-3 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 text-sm">
                ← Watchlist
            </a>
            <label for="symbol" class="text-sm font-medium text-gray-700">Symbol</label>
            <select id="symbol" wire:model.live="symbol" class="border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500">
                @foreach($symbols as $sym)
                    <option value="{{ $sym }}">{{ $sym }}</option>
                @endforeach
            </select>
        </div>
        <div class="flex items-center gap-2">
            <label class="text-sm font-medium text-gray-700">Timeframe</label>
            <select wire:model.live="timeframe" class="border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 text-sm">
                <option value="tick">Tick</option>
                <option value="1m">1 Min</option>
                <option value="5m">5 Min</option>
                <option value="15m">15 Min</option>
                <option value="30m">30 Min</option>
                <option value="1h">1 Hour</option>
                <option value="1d">1 Day</option>
            </select>
        </div>
    </div>

    <!-- Account Overview -->
    <div class="bg-white p-4 rounded-lg shadow">
        <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-semibold text-gray-700">💰 Account Overview</h3>
            @if($accountInfo['is_connected'])
            <span class="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-semibold">
                🟢 Connected
            </span>
            @else
            <span class="px-2 py-1 bg-gray-100 text-gray-600 rounded-full text-xs font-semibold">
                ⚪ Demo Mode
            </span>
            @endif
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <!-- Portfolio Value -->
            <div class="text-center p-3 bg-blue-50 rounded-lg">
                <div class="text-xs text-gray-600 mb-1">Portfolio Value</div>
                <div class="text-2xl font-bold text-blue-600">
                    ${{ number_format($accountInfo['portfolio_value'], 2) }}
                </div>
                @if($accountInfo['daily_pnl'] != 0)
                <div class="text-xs {{ $accountInfo['daily_pnl'] >= 0 ? 'text-green-600' : 'text-red-600' }} mt-1">
                    {{ $accountInfo['daily_pnl'] >= 0 ? '+' : '' }}${{ number_format($accountInfo['daily_pnl'], 2) }}
                    ({{ $accountInfo['daily_pnl_pct'] >= 0 ? '+' : '' }}{{ number_format($accountInfo['daily_pnl_pct'], 2) }}%)
                </div>
                @endif
            </div>

            <!-- Buying Power -->
            <div class="text-center p-3 bg-green-50 rounded-lg">
                <div class="text-xs text-gray-600 mb-1">Buying Power</div>
                <div class="text-2xl font-bold text-green-600">
                    ${{ number_format($accountInfo['buying_power'], 2) }}
                </div>
                <div class="text-xs text-gray-500 mt-1">Available</div>
            </div>

            <!-- Cash -->
            <div class="text-center p-3 bg-purple-50 rounded-lg">
                <div class="text-xs text-gray-600 mb-1">Cash</div>
                <div class="text-2xl font-bold text-purple-600">
                    ${{ number_format($accountInfo['cash'], 2) }}
                </div>
                <div class="text-xs text-gray-500 mt-1">Liquid</div>
            </div>

            <!-- Trades Today -->
            <div class="text-center p-3 bg-orange-50 rounded-lg">
                <div class="text-xs text-gray-600 mb-1">Trades Today</div>
                <div class="text-2xl font-bold text-orange-600">
                    {{ $accountInfo['trades_today'] }}
                </div>
                @if($accountInfo['win_rate'] > 0)
                <div class="text-xs text-gray-500 mt-1">{{ number_format($accountInfo['win_rate'], 0) }}% Win Rate</div>
                @else
                <div class="text-xs text-gray-500 mt-1">-</div>
                @endif
            </div>
        </div>

        <!-- Risk Metrics -->
        <div class="mt-4 p-3 bg-gray-50 rounded-lg">
            <div class="text-xs font-semibold text-gray-700 mb-2">⚠️ Risk Management</div>
            <div class="grid grid-cols-3 gap-4 text-center">
                <div>
                    <div class="text-xs text-gray-600">Risk Per Trade</div>
                    <div class="text-lg font-bold text-gray-900">{{ $accountInfo['risk_per_trade_pct'] }}%</div>
                    <div class="text-xs text-gray-500">${{ number_format($accountInfo['portfolio_value'] * $accountInfo['risk_per_trade_pct'] / 100, 2) }}</div>
                </div>
                <div>
                    <div class="text-xs text-gray-600">Max Positions</div>
                    <div class="text-lg font-bold text-gray-900">{{ $accountInfo['max_positions'] }}</div>
                    <div class="text-xs text-gray-500">Concurrent</div>
                </div>
                <div>
                    <div class="text-xs text-gray-600">Daily Loss Limit</div>
                    <div class="text-lg font-bold text-gray-900">{{ $accountInfo['max_daily_loss_pct'] }}%</div>
                    <div class="text-xs text-gray-500">${{ number_format($accountInfo['portfolio_value'] * $accountInfo['max_daily_loss_pct'] / 100, 2) }}</div>
                </div>
            </div>
        </div>

        @if(!$accountInfo['is_connected'])
        <div class="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
            💡 <strong>Demo Mode:</strong> Connect Alpaca trading API keys to see real account data and enable live trading.
        </div>
        @endif
    </div>

    <!-- Session Indicator -->
    <div class="bg-white p-4 rounded-lg shadow">
        <div class="flex items-center justify-between">
            <div>
                <h3 class="text-sm font-semibold text-gray-700 mb-1">Trading Session</h3>
                <div class="flex items-center gap-3">
                    <span class="text-4xl">{{ $sessionInfo['icon'] }}</span>
                    <div>
                        <div class="text-2xl font-bold text-gray-900">{{ $sessionInfo['name'] }}</div>
                        <div class="text-sm text-gray-600">{{ $sessionInfo['time_et'] }}</div>
                    </div>
                </div>
            </div>
            <div class="text-right">
                <div class="text-xs text-gray-600 mb-1">Recommended Setup</div>
                <div class="text-lg font-semibold {{ $sessionInfo['is_market_hours'] ? 'text-green-600' : 'text-gray-600' }}">
                    {{ $sessionInfo['recommended_setup'] }}
                </div>
                @if($sessionInfo['is_market_hours'])
                <div class="mt-2 px-3 py-1 bg-green-100 text-green-800 rounded-full text-xs font-semibold inline-block">
                    🟢 MARKET OPEN
                </div>
                @else
                <div class="mt-2 px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-xs font-semibold inline-block">
                    ⚪ MARKET CLOSED
                </div>
                @endif
            </div>
        </div>
        
        <div class="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <p class="text-sm text-blue-900">
                <strong>💡 Session Guide:</strong>
                @if($sessionInfo['session'] === 'NEW_YORK')
                    New York session (09:30-16:00 ET) is best for <strong>Trend Model</strong> trades. High liquidity and momentum.
                @elseif($sessionInfo['session'] === 'LONDON')
                    London session (03:00-11:00 ET) is best for <strong>Mean Reversion</strong> trades. Watch for failed breakouts.
                @elseif($sessionInfo['session'] === 'ASIAN')
                    Asian session (18:00-03:00 ET) has lower volatility. Reduced trading opportunities for US stocks.
                @else
                    Pre-market hours. Wait for regular session to open for best opportunities.
                @endif
            </p>
        </div>
    </div>

    <!-- Market State Indicator -->
    <div class="bg-white p-4 rounded-lg shadow">
        <div class="flex items-center justify-between">
            <div>
                <h3 class="text-sm font-semibold text-gray-700 mb-1">Market State</h3>
                <div class="flex items-center gap-3">
                    @php
                        $state = $marketState['state'] ?? 'UNKNOWN';
                        $confidence = $marketState['confidence'] ?? 0;
                        $stateColors = [
                            'BALANCE' => 'bg-yellow-100 text-yellow-800 border-yellow-300',
                            'IMBALANCE_UP' => 'bg-green-100 text-green-800 border-green-300',
                            'IMBALANCE_DOWN' => 'bg-red-100 text-red-800 border-red-300',
                            'UNKNOWN' => 'bg-gray-100 text-gray-800 border-gray-300',
                        ];
                        $stateColor = $stateColors[$state] ?? $stateColors['UNKNOWN'];
                        $stateLabels = [
                            'BALANCE' => '⚖️ BALANCE',
                            'IMBALANCE_UP' => '📈 IMBALANCE UP',
                            'IMBALANCE_DOWN' => '📉 IMBALANCE DOWN',
                            'UNKNOWN' => '❓ UNKNOWN',
                        ];
                        $stateLabel = $stateLabels[$state] ?? 'UNKNOWN';
                    @endphp
                    <span class="px-4 py-2 rounded-lg border-2 font-bold text-lg {{ $stateColor }}">
                        {{ $stateLabel }}
                    </span>
                    <span class="text-sm text-gray-600">
                        Confidence: <span class="font-semibold">{{ $confidence }}%</span>
                    </span>
                </div>
            </div>
            @if($state !== 'UNKNOWN')
            <div class="text-right">
                <div class="text-xs text-gray-600 mb-1">POC (Point of Control)</div>
                <div class="text-2xl font-bold text-blue-600">${{ number_format($marketState['poc'] ?? 0, 2) }}</div>
                @if(isset($marketState['balance_high']) && $marketState['balance_high'] > 0)
                <div class="text-xs text-gray-500 mt-1">
                    Range: ${{ number_format($marketState['balance_low'], 2) }} - ${{ number_format($marketState['balance_high'], 2) }}
                </div>
                @endif
            </div>
            @endif
        </div>
        
        @if($state === 'BALANCE')
        <div class="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p class="text-sm text-yellow-800">
                <strong>💡 Strategy Tip:</strong> Market is in balance. Consider <strong>Mean Reversion</strong> trades. Wait for failed breakouts and reclaims into balance.
            </p>
        </div>
        @elseif($state === 'IMBALANCE_UP' || $state === 'IMBALANCE_DOWN')
        <div class="mt-3 p-3 {{ $state === 'IMBALANCE_UP' ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200' }} border rounded-lg">
            <p class="text-sm {{ $state === 'IMBALANCE_UP' ? 'text-green-800' : 'text-red-800' }}">
                <strong>💡 Strategy Tip:</strong> Market is out of balance. Consider <strong>Trend Model</strong> trades. Look for pullbacks to LVNs on the impulse leg.
            </p>
        </div>
        @endif
    </div>

    <!-- LVN Alert Widget -->
    @if(!empty($lvnAlert))
    <div class="bg-white p-4 rounded-lg shadow {{ $lvnAlert['alert'] ? 'ring-2 ring-orange-400 animate-pulse' : '' }}">
        <div class="flex items-center justify-between">
            <div>
                <h3 class="text-sm font-semibold text-gray-700 mb-1">
                    @if($lvnAlert['alert'])
                        🔔 LVN ALERT - Price Approaching Entry Zone
                    @else
                        📍 Nearest LVN (Low Volume Node)
                    @endif
                </h3>
                <div class="flex items-center gap-4 mt-2">
                    <div>
                        <div class="text-xs text-gray-600">Current Price</div>
                        <div class="text-xl font-bold text-gray-900">${{ number_format($lvnAlert['current_price'], 2) }}</div>
                    </div>
                    <div class="text-2xl {{ $lvnAlert['direction'] === 'UP' ? 'text-green-600' : 'text-red-600' }}">
                        {{ $lvnAlert['direction'] === 'UP' ? '↑' : '↓' }}
                    </div>
                    <div>
                        <div class="text-xs text-gray-600">Target LVN</div>
                        <div class="text-xl font-bold text-blue-600">${{ number_format($lvnAlert['lvn_price'], 2) }}</div>
                    </div>
                </div>
            </div>
            <div class="text-right">
                <div class="text-xs text-gray-600 mb-1">Distance</div>
                <div class="text-3xl font-bold {{ $lvnAlert['alert'] ? 'text-orange-600' : 'text-gray-600' }}">
                    {{ $lvnAlert['distance_pct'] }}%
                </div>
                <div class="text-sm text-gray-500">${{ number_format($lvnAlert['distance_dollars'], 2) }}</div>
            </div>
        </div>
        
        @if($lvnAlert['alert'])
        <div class="mt-3 p-3 bg-orange-50 border border-orange-300 rounded-lg">
            <p class="text-sm text-orange-900 font-semibold">
                ⚠️ Price is within 0.5% of LVN! Watch for aggressive order flow at this level for potential entry.
            </p>
        </div>
        @else
        <div class="mt-3">
            <div class="w-full bg-gray-200 rounded-full h-2">
                <div class="bg-blue-500 h-2 rounded-full transition-all" style="width: {{ min(100, 100 - ($lvnAlert['distance_pct'] * 10)) }}%"></div>
            </div>
            <p class="text-xs text-gray-600 mt-1">
                Price moving {{ $lvnAlert['direction'] }} toward LVN. Alert triggers at 0.5% distance.
            </p>
        </div>
        @endif
    </div>
    @endif

    <!-- Aggressive Flow Indicator -->
    @if(!empty($aggressiveFlow))
    <div class="bg-white p-4 rounded-lg shadow {{ $aggressiveFlow['is_aggressive'] ? 'ring-2 ring-purple-400' : '' }}">
        <div class="flex items-center justify-between">
            <div class="flex-1">
                <h3 class="text-sm font-semibold text-gray-700 mb-2">
                    🔥 Aggressive Flow Detector
                </h3>
                <div class="flex items-center gap-6">
                    <!-- Score Gauge -->
                    <div class="text-center">
                        <div class="text-xs text-gray-600 mb-1">Aggression Score</div>
                        <div class="relative w-24 h-24">
                            <svg class="transform -rotate-90 w-24 h-24">
                                <circle cx="48" cy="48" r="40" stroke="#e5e7eb" stroke-width="8" fill="none" />
                                <circle cx="48" cy="48" r="40" 
                                    stroke="{{ $aggressiveFlow['score'] >= 70 ? '#ef4444' : ($aggressiveFlow['score'] >= 50 ? '#f59e0b' : '#10b981') }}" 
                                    stroke-width="8" 
                                    fill="none"
                                    stroke-dasharray="{{ 2 * 3.14159 * 40 }}"
                                    stroke-dashoffset="{{ 2 * 3.14159 * 40 * (1 - $aggressiveFlow['score'] / 100) }}"
                                    class="transition-all duration-500" />
                            </svg>
                            <div class="absolute inset-0 flex items-center justify-center">
                                <span class="text-2xl font-bold {{ $aggressiveFlow['score'] >= 70 ? 'text-red-600' : ($aggressiveFlow['score'] >= 50 ? 'text-orange-600' : 'text-green-600') }}">
                                    {{ $aggressiveFlow['score'] }}
                                </span>
                            </div>
                        </div>
                    </div>

                    <!-- Direction -->
                    <div class="text-center px-4 border-l border-gray-200">
                        <div class="text-xs text-gray-600 mb-1">Direction</div>
                        @php
                            $directionColors = [
                                'BUY' => 'bg-green-100 text-green-800 border-green-300',
                                'SELL' => 'bg-red-100 text-red-800 border-red-300',
                                'NEUTRAL' => 'bg-gray-100 text-gray-800 border-gray-300',
                            ];
                            $directionColor = $directionColors[$aggressiveFlow['direction']] ?? $directionColors['NEUTRAL'];
                        @endphp
                        <div class="px-4 py-2 rounded-lg border-2 font-bold text-lg {{ $directionColor }}">
                            {{ $aggressiveFlow['direction'] }}
                        </div>
                    </div>

                    <!-- Metrics -->
                    <div class="flex-1 grid grid-cols-3 gap-4">
                        <div>
                            <div class="text-xs text-gray-600">Volume</div>
                            <div class="text-lg font-semibold {{ $aggressiveFlow['volume_ratio'] >= 2.0 ? 'text-orange-600' : 'text-gray-900' }}">
                                {{ $aggressiveFlow['volume_ratio'] }}x
                            </div>
                        </div>
                        <div>
                            <div class="text-xs text-gray-600">CVD Momentum</div>
                            <div class="text-lg font-semibold {{ $aggressiveFlow['cvd_momentum'] > 0 ? 'text-green-600' : 'text-red-600' }}">
                                {{ $aggressiveFlow['cvd_momentum'] > 0 ? '+' : '' }}{{ number_format($aggressiveFlow['cvd_momentum']) }}
                            </div>
                        </div>
                        <div>
                            <div class="text-xs text-gray-600">Pressure</div>
                            <div class="text-lg font-semibold">
                                <span class="text-green-600">{{ $aggressiveFlow['buy_pressure'] }}%</span>
                                /
                                <span class="text-red-600">{{ $aggressiveFlow['sell_pressure'] }}%</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        @if($aggressiveFlow['is_aggressive'])
        <div class="mt-3 p-3 bg-purple-50 border border-purple-300 rounded-lg">
            <p class="text-sm text-purple-900 font-semibold">
                ⚡ Strong aggressive flow detected! This confirms institutional activity at current price level.
            </p>
        </div>
        @endif
    </div>
    @endif

    <!-- Positions & Trade History -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Active Positions -->
        <div class="bg-white p-4 rounded-lg shadow">
            <h3 class="text-sm font-semibold text-gray-700 mb-3">📊 Active Positions</h3>
            @if(empty($positions))
            <div class="text-center py-8 text-gray-500">
                <div class="text-4xl mb-2">💤</div>
                <p class="text-sm">No active positions</p>
                <p class="text-xs mt-1">Positions will appear here when auto-trading is active</p>
            </div>
            @else
            <div class="space-y-2">
                @foreach($positions as $pos)
                <div class="border border-gray-200 rounded-lg p-3">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="font-bold text-lg">{{ $pos['symbol'] }}</div>
                            <div class="text-sm text-gray-600">{{ $pos['qty'] }} shares @ ${{ number_format($pos['avg_entry_price'], 2) }}</div>
                        </div>
                        <div class="text-right">
                            <div class="text-lg font-bold {{ $pos['unrealized_plpc'] >= 0 ? 'text-green-600' : 'text-red-600' }}">
                                {{ $pos['unrealized_plpc'] >= 0 ? '+' : '' }}{{ number_format($pos['unrealized_plpc'], 2) }}%
                            </div>
                            <div class="text-sm {{ $pos['unrealized_pl'] >= 0 ? 'text-green-600' : 'text-red-600' }}">
                                ${{ number_format($pos['unrealized_pl'], 2) }}
                            </div>
                        </div>
                    </div>
                    <div class="mt-2 text-xs text-gray-500">
                        Current: ${{ number_format($pos['current_price'], 2) }}
                    </div>
                </div>
                @endforeach
            </div>
            @endif
        </div>

        <!-- Trade History -->
        <div class="bg-white p-4 rounded-lg shadow">
            <h3 class="text-sm font-semibold text-gray-700 mb-3">📜 Recent Trades</h3>
            @if(empty($tradeHistory))
            <div class="text-center py-8 text-gray-500">
                <div class="text-4xl mb-2">📝</div>
                <p class="text-sm">No trade history yet</p>
                <p class="text-xs mt-1">Trades will be logged here when executed</p>
            </div>
            @else
            <div class="space-y-2 max-h-64 overflow-y-auto">
                @foreach($tradeHistory as $trade)
                <div class="border-l-4 {{ $trade['type'] === 'BUY' ? 'border-green-500' : 'border-red-500' }} bg-gray-50 p-2 rounded">
                    <div class="flex items-center justify-between">
                        <div>
                            <span class="font-semibold {{ $trade['type'] === 'BUY' ? 'text-green-600' : 'text-red-600' }}">
                                {{ $trade['type'] }}
                            </span>
                            <span class="font-bold ml-2">{{ $trade['symbol'] }}</span>
                        </div>
                        <div class="text-right">
                            <div class="text-sm font-semibold">${{ number_format($trade['price'], 2) }}</div>
                            <div class="text-xs text-gray-600">{{ $trade['qty'] }} shares</div>
                        </div>
                    </div>
                    <div class="text-xs text-gray-600 mt-1">
                        {{ \Carbon\Carbon::parse($trade['time'])->format('M d, H:i') }}
                    </div>
                    @if($trade['reason'])
                    <div class="text-xs text-gray-500 mt-1 truncate">
                        {{ $trade['reason'] }}
                    </div>
                    @endif
                </div>
                @endforeach
            </div>
            @endif
        </div>
    </div>

    <div class="bg-white p-4 rounded-lg shadow" wire:ignore>
        <div id="priceChart" style="height: 500px; width: 100%;"></div>
        <!-- Buy/Sell Pressure Indicator -->
        <div class="mt-4 flex items-center gap-4">
            <div class="flex-1">
                <div class="flex items-center justify-between text-xs mb-1">
                    <span class="text-green-600 font-semibold">Buy Pressure</span>
                    <span id="buyPressureValue" class="text-green-600 font-bold">50%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                    <div id="buyPressureBar" class="bg-gradient-to-r from-green-400 to-green-600 h-3 transition-all duration-300" style="width: 50%"></div>
                </div>
            </div>
            <div class="flex-1">
                <div class="flex items-center justify-between text-xs mb-1">
                    <span class="text-red-600 font-semibold">Sell Pressure</span>
                    <span id="sellPressureValue" class="text-red-600 font-bold">50%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                    <div id="sellPressureBar" class="bg-gradient-to-r from-red-400 to-red-600 h-3 transition-all duration-300" style="width: 50%"></div>
                </div>
            </div>
            <div class="text-center px-4 border-l border-gray-300">
                <div class="text-xs text-gray-600">CVD</div>
                <div id="cvdValue" class="text-lg font-bold text-gray-900">0</div>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <script>
        let chart = null;
        let candlestickSeries = null;
        let currentSymbol = @json($this->symbol ?? 'AAPL');
        let currentChannel = null;
        let currentTimeframe = '1m';

        function parseTime(timeStr) {
            // Convert "2025-10-01 05:45:00" to Unix timestamp
            const date = new Date(timeStr.replace(' ', 'T') + 'Z');
            return Math.floor(date.getTime() / 1000);
        }

        function renderChart(labels, closes, signals = [], volumeProfile = {}, orderFlow = {}) {
            const container = document.getElementById('priceChart');
            if (!container) return;
            
            console.log('Rendering TradingView chart:', { closes: closes.length, signals: signals.length });
            
            // Destroy existing chart
            if (chart) {
                chart.remove();
                chart = null;
            }
            
            // Create new chart
            chart = LightweightCharts.createChart(container, {
                width: container.clientWidth,
                height: 500,
                layout: {
                    background: { color: '#ffffff' },
                    textColor: '#333',
                },
                grid: {
                    vertLines: { color: '#f0f0f0' },
                    horzLines: { color: '#f0f0f0' },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                },
                rightPriceScale: {
                    borderColor: '#d1d4dc',
                },
                timeScale: {
                    borderColor: '#d1d4dc',
                    timeVisible: true,
                    secondsVisible: false,
                },
            });
            
            // Add candlestick series
            candlestickSeries = chart.addCandlestickSeries({
                upColor: '#22c55e',
                downColor: '#ef4444',
                borderVisible: false,
                wickUpColor: '#22c55e',
                wickDownColor: '#ef4444',
            });
            
            // Convert OHLC data to TradingView format
            const candleData = closes.map(c => ({
                time: parseTime(c.x),
                open: c.o,
                high: c.h,
                low: c.l,
                close: c.c
            })).sort((a, b) => a.time - b.time);
            
            console.log('Candle data sample:', candleData.slice(0, 3));
            
            candlestickSeries.setData(candleData);
            
            // Add signal markers
            const markers = signals.map(sig => {
                const matchingCandle = closes.find(c => c.x === sig.time);
                const price = matchingCandle ? matchingCandle.c : sig.price;
                
                return {
                    time: parseTime(sig.time),
                    position: sig.type === 'BUY' ? 'belowBar' : 'aboveBar',
                    color: sig.type === 'BUY' ? '#22c55e' : '#ef4444',
                    shape: sig.type === 'BUY' ? 'arrowUp' : 'arrowDown',
                    text: sig.type
                };
            });
            
            if (markers.length > 0) {
                candlestickSeries.setMarkers(markers);
            }
            
            // Add volume profile overlays as price lines
            if (volumeProfile && volumeProfile.poc) {
                // POC line
                candlestickSeries.createPriceLine({
                    price: volumeProfile.poc,
                    color: '#3b82f6',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: 'POC',
                });
                
                // VAH line
                if (volumeProfile.vah) {
                    candlestickSeries.createPriceLine({
                        price: volumeProfile.vah,
                        color: '#3b82f680',
                        lineWidth: 1,
                        lineStyle: LightweightCharts.LineStyle.Dotted,
                        axisLabelVisible: true,
                        title: 'VAH',
                    });
                }
                
                // VAL line
                if (volumeProfile.val) {
                    candlestickSeries.createPriceLine({
                        price: volumeProfile.val,
                        color: '#3b82f680',
                        lineWidth: 1,
                        lineStyle: LightweightCharts.LineStyle.Dotted,
                        axisLabelVisible: true,
                        title: 'VAL',
                    });
                }
                
                // LVN lines
                if (volumeProfile.lvns && volumeProfile.lvns.length > 0) {
                    volumeProfile.lvns.slice(0, 5).forEach((lvn, idx) => {
                        candlestickSeries.createPriceLine({
                            price: lvn,
                            color: '#ef444480',
                            lineWidth: 1,
                            lineStyle: LightweightCharts.LineStyle.Dotted,
                            axisLabelVisible: false,
                            title: 'LVN',
                        });
                    });
                }
            }
            
            // Fit content
            chart.timeScale().fitContent();
            
            // Handle resize
            window.addEventListener('resize', () => {
                if (chart) {
                    chart.applyOptions({ width: container.clientWidth });
                }
            });
        }

        function updatePressureIndicators(orderFlow) {
            if (!orderFlow) return;
            
            const buyPressure = orderFlow.buy_pressure || 50;
            const sellPressure = orderFlow.sell_pressure || 50;
            const cvd = orderFlow.cvd || 0;
            
            document.getElementById('buyPressureValue').textContent = buyPressure.toFixed(1) + '%';
            document.getElementById('buyPressureBar').style.width = buyPressure + '%';
            
            document.getElementById('sellPressureValue').textContent = sellPressure.toFixed(1) + '%';
            document.getElementById('sellPressureBar').style.width = sellPressure + '%';
            
            const cvdEl = document.getElementById('cvdValue');
            cvdEl.textContent = cvd.toLocaleString();
            cvdEl.className = 'text-lg font-bold ' + (cvd > 0 ? 'text-green-600' : cvd < 0 ? 'text-red-600' : 'text-gray-900');
        }

        document.addEventListener('chart-data', (event) => {
            const { labels, closes, signals, volumeProfile, orderFlow } = event.detail;
            currentTimeframe = @json($this->timeframe ?? '1m');
            renderChart(labels, closes, signals, volumeProfile, orderFlow);
            updatePressureIndicators(orderFlow);
        });

        function subscribeToSymbol(sym) {
            if (!window.Echo) return;
            if (currentChannel) {
                window.Echo.leave(`candles.${currentSymbol}`);
                currentChannel = null;
            }
            currentSymbol = sym;
            currentChannel = window.Echo.channel(`candles.${sym}`)
                .listen('.candle.ticked', (e) => {
                    if (!candlestickSeries) return;
                    const newCandle = {
                        time: parseTime(e.time),
                        close: Number(e.close)
                    };
                    candlestickSeries.update(newCandle);
                });
        }

        document.addEventListener('DOMContentLoaded', () => {
            subscribeToSymbol(currentSymbol);
        });

        document.addEventListener('symbol-changed', (ev) => {
            const sym = ev.detail.symbol;
            subscribeToSymbol(sym);
        });
    </script>

    <!-- Auto-refresh indicator -->
    <div class="text-center text-sm text-gray-500 py-2">
        ⚡ Ultra-fast mode: Auto-refreshing every 3 seconds
    </div>
</div>

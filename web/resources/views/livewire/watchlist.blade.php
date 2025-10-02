<div class="space-y-4">
    <div class="flex items-center justify-between">
        <h1 class="text-2xl font-bold text-gray-900">📊 Watchlist - 30 Stocks</h1>
        <div class="flex gap-2">
            <a href="{{ route('strategies') }}" class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
                ⚙️ Strategies
            </a>
            <a href="{{ route('account') }}" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                💼 Account
            </a>
        </div>
    </div>

    <!-- Account Overview -->
    <div class="bg-white p-4 rounded-lg shadow">
        <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-semibold text-gray-700">💰 Account Overview</h3>
            @if(!empty($accountInfo) && isset($accountInfo['is_connected']) && $accountInfo['is_connected'])
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
                    ${{ number_format($accountInfo['portfolio_value'] ?? 100000, 2) }}
                </div>
                @if(isset($accountInfo['daily_pnl']) && $accountInfo['daily_pnl'] != 0)
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
                <div class="text-xs text-gray-500 mt-1">Positions: {{ $accountInfo['max_positions'] }}</div>
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
    </div>

    <!-- Flash Messages -->
    @if (session()->has('success'))
    <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
        <span class="block sm:inline">{{ session('success') }}</span>
    </div>
    @endif
    @if (session()->has('error'))
    <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
        <span class="block sm:inline">{{ session('error') }}</span>
    </div>
    @endif

    <!-- Open Positions & Pending Orders -->
    @if(count($openPositions) > 0)
    <div class="bg-white p-4 rounded-lg shadow">
        <div class="flex items-center justify-between mb-3">
            <h2 class="text-lg font-semibold text-gray-900">📊 Positions & Orders ({{ $tradesCount }} open)</h2>
            <span class="text-xs text-gray-500">Auto-refreshing</span>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            @foreach($openPositions as $position)
            <div class="border-l-4 p-3 rounded hover:shadow-md transition-all
                      @if($position['status'] === 'PENDING')
                          border-yellow-500 bg-yellow-50
                      @elseif(isset($position['unrealized_pl']) && $position['unrealized_pl'] >= 0)
                          border-green-500 bg-green-50
                      @else
                          border-red-500 bg-red-50
                      @endif">
                
                <!-- Header: Symbol & Status -->
                <div class="flex items-center justify-between mb-2">
                    <a href="{{ route('stock.detail', ['symbol' => $position['symbol']]) }}" class="flex items-center gap-2 hover:underline">
                        <span class="font-bold text-lg text-gray-900">
                            {{ \App\Models\Symbol::formatSymbol($position['symbol']) }}
                        </span>
                        <span class="px-2 py-0.5 rounded text-xs font-semibold
                                     {{ $position['side'] === 'long' || $position['side'] === 'buy' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700' }}">
                            {{ strtoupper($position['side']) }}
                        </span>
                    </a>
                    
                    @if($position['status'] === 'FILLED')
                    <button 
                        wire:click="closePosition('{{ $position['symbol'] }}')"
                        wire:confirm="Close {{ $position['symbol'] }} position?"
                        class="px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700 text-xs font-semibold"
                        onclick="event.stopPropagation()">
                        Close
                    </button>
                    @elseif($position['status'] === 'PENDING')
                    <span class="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs font-semibold">
                        PENDING
                    </span>
                    @endif
                </div>
                
                <!-- Position Details -->
                @if($position['status'] === 'FILLED')
                    <!-- Open Position with P&L -->
                    <div class="space-y-1">
                        <div class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                            <div class="flex justify-between">
                                <span class="text-gray-600">Entry:</span>
                                <span class="font-semibold">${{ number_format($position['entry_price'], 2) }}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Current:</span>
                                <span class="font-semibold">${{ number_format($position['current_price'], 2) }}</span>
                            </div>
                            
                            @if(isset($position['take_profit']) && $position['take_profit'])
                            <div class="flex justify-between">
                                <span class="text-gray-600">🎯 Target:</span>
                                <span class="font-semibold text-green-600">${{ number_format($position['take_profit'], 2) }}</span>
                            </div>
                            @endif
                            
                            @if(isset($position['stop_loss']) && $position['stop_loss'])
                            <div class="flex justify-between">
                                <span class="text-gray-600">🛑 Stop:</span>
                                <span class="font-semibold text-red-600">${{ number_format($position['stop_loss'], 2) }}</span>
                            </div>
                            @endif
                        </div>
                        
                        <div class="flex justify-between text-sm pt-1">
                            <span class="text-gray-600">Qty:</span>
                            <span class="font-semibold">{{ $position['qty'] }} shares</span>
                        </div>
                        
                        <!-- P&L Display -->
                        <div class="pt-2 border-t mt-2">
                            <div class="flex justify-between items-center">
                                <span class="text-xs text-gray-600">Unrealized P&L:</span>
                                <div class="text-right">
                                    <div class="text-lg font-bold {{ $position['unrealized_pl'] >= 0 ? 'text-green-600' : 'text-red-600' }}">
                                        {{ $position['unrealized_pl'] >= 0 ? '+' : '' }}${{ number_format($position['unrealized_pl'], 2) }}
                                    </div>
                                    <div class="text-xs {{ $position['unrealized_pl'] >= 0 ? 'text-green-600' : 'text-red-600' }}">
                                        {{ $position['unrealized_pl'] >= 0 ? '+' : '' }}{{ number_format($position['unrealized_pl_pct'], 2) }}%
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                @else
                    <!-- Pending Order -->
                    <div class="space-y-1">
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-600">Type:</span>
                            <span class="font-semibold uppercase">{{ $position['order_type'] }}</span>
                        </div>
                        @if($position['limit_price'])
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-600">Limit Price:</span>
                            <span class="font-semibold">${{ number_format($position['limit_price'], 2) }}</span>
                        </div>
                        @endif
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-600">Qty:</span>
                            <span class="font-semibold">{{ $position['qty'] }} shares</span>
                        </div>
                        <div class="text-xs text-gray-500 mt-2">
                            Submitted: {{ \Carbon\Carbon::parse($position['submitted_at'])->diffForHumans() }}
                        </div>
                    </div>
                @endif
            </div>
            @endforeach
        </div>
    </div>
    @endif

    <!-- Quick Stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        @php
            $imbalanceCount = 0;
            $aggressiveCount = 0;
            $totalConfidence = 0;
            $confidenceCount = 0;
            
            foreach ($stocks as $stock) {
                if ($stock['market_state'] !== 'BALANCE' && $stock['market_state'] !== 'UNKNOWN') {
                    $imbalanceCount++;
                }
                if ($stock['aggression_score'] >= 50) {
                    $aggressiveCount++;
                }
                if ($stock['confidence'] > 0) {
                    $totalConfidence += $stock['confidence'];
                    $confidenceCount++;
                }
            }
            
            $avgConfidence = $confidenceCount > 0 ? round($totalConfidence / $confidenceCount) : 0;
        @endphp
        
        <div class="bg-white p-4 rounded-lg shadow text-center">
            <div class="text-sm text-gray-600">Stocks Tracked</div>
            <div class="text-3xl font-bold text-blue-600">{{ count($stocks) }}</div>
        </div>
        
        <div class="bg-white p-4 rounded-lg shadow text-center">
            <div class="text-sm text-gray-600">In Imbalance</div>
            <div class="text-3xl font-bold text-orange-600">{{ $imbalanceCount }}</div>
        </div>
        
        <div class="bg-white p-4 rounded-lg shadow text-center">
            <div class="text-sm text-gray-600">Aggressive Flow</div>
            <div class="text-3xl font-bold text-purple-600">{{ $aggressiveCount }}</div>
        </div>
        
        <div class="bg-white p-4 rounded-lg shadow text-center">
            <div class="text-sm text-gray-600">Avg Confidence</div>
            <div class="text-3xl font-bold text-green-600">{{ round($avgConfidence) }}%</div>
        </div>
    </div>

    <!-- Stock Cards Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        @foreach($stocks as $stock)
        <a href="{{ route('stock.detail', ['symbol' => $stock['symbol']]) }}" 
           class="block bg-white rounded-lg shadow hover:shadow-lg transition-shadow p-4">
            
            <!-- Header -->
            <div class="flex items-center justify-between mb-3">
                <div>
                    <h3 class="text-2xl font-bold text-gray-900">{{ $stock['symbol'] }}</h3>
                    <div class="text-sm text-gray-500">
                        {{ $stock['last_update'] ? \Carbon\Carbon::parse($stock['last_update'])->diffForHumans() : 'No data' }}
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-2xl font-bold text-gray-900">${{ number_format($stock['price'], 2) }}</div>
                </div>
            </div>

            <!-- Market State -->
            <div class="mb-3">
                @php
                    $stateColors = [
                        'BALANCE' => 'bg-yellow-100 text-yellow-800 border-yellow-300',
                        'IMBALANCE_UP' => 'bg-green-100 text-green-800 border-green-300',
                        'IMBALANCE_DOWN' => 'bg-red-100 text-red-800 border-red-300',
                        'UNKNOWN' => 'bg-gray-100 text-gray-600 border-gray-300',
                    ];
                    $stateColor = $stateColors[$stock['market_state']] ?? $stateColors['UNKNOWN'];
                    $stateLabels = [
                        'BALANCE' => '⚖️ Balance',
                        'IMBALANCE_UP' => '📈 Imbalance ↑',
                        'IMBALANCE_DOWN' => '📉 Imbalance ↓',
                        'UNKNOWN' => '❓ Unknown',
                    ];
                    $stateLabel = $stateLabels[$stock['market_state']] ?? 'Unknown';
                @endphp
                <div class="px-3 py-2 rounded-lg border {{ $stateColor }} text-center font-semibold">
                    {{ $stateLabel }}
                </div>
                <div class="text-xs text-center text-gray-600 mt-1">
                    {{ $stock['confidence'] }}% confidence
                </div>
            </div>

            <!-- Metrics Grid -->
            <div class="grid grid-cols-2 gap-2 text-sm">
                <div class="bg-gray-50 p-2 rounded">
                    <div class="text-xs text-gray-600">POC</div>
                    <div class="font-semibold">${{ number_format($stock['poc'], 2) }}</div>
                </div>
                
                <div class="bg-gray-50 p-2 rounded">
                    <div class="text-xs text-gray-600">CVD</div>
                    <div class="font-semibold {{ $stock['cvd'] >= 0 ? 'text-green-600' : 'text-red-600' }}">
                        {{ $stock['cvd'] >= 0 ? '+' : '' }}{{ number_format($stock['cvd']) }}
                    </div>
                </div>
                
                <div class="bg-gray-50 p-2 rounded">
                    <div class="text-xs text-gray-600">Buy Pressure</div>
                    <div class="font-semibold text-green-600">{{ $stock['buy_pressure'] }}%</div>
                </div>
                
                <div class="bg-gray-50 p-2 rounded">
                    <div class="text-xs text-gray-600">Sell Pressure</div>
                    <div class="font-semibold text-red-600">{{ $stock['sell_pressure'] }}%</div>
                </div>
            </div>

            <!-- Aggression Score -->
            <div class="mt-3 pt-3 border-t border-gray-200">
                <div class="flex items-center justify-between">
                    <span class="text-xs text-gray-600">Aggression Score</span>
                    <span class="text-lg font-bold {{ $stock['aggression_score'] >= 70 ? 'text-red-600' : ($stock['aggression_score'] >= 50 ? 'text-orange-600' : 'text-gray-600') }}">
                        {{ $stock['aggression_score'] }}
                    </span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2 mt-1">
                    <div class="bg-purple-600 h-2 rounded-full transition-all" style="width: {{ $stock['aggression_score'] }}%"></div>
                </div>
            </div>

            <!-- Trade Signal Indicator -->
            @if($stock['market_state'] !== 'BALANCE' && $stock['market_state'] !== 'UNKNOWN' && $stock['aggression_score'] >= 70)
            <div class="mt-3 p-2 bg-green-50 border border-green-300 rounded text-center">
                <div class="text-xs font-semibold text-green-800">
                    🎯 POTENTIAL ENTRY SIGNAL
                </div>
            </div>
            @endif
        </a>
        @endforeach
    </div>

    <!-- Engine Debug Logs -->
    <div class="bg-gray-900 text-gray-100 p-4 rounded-lg shadow">
        <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-semibold">🔧 Engine Activity Monitor</h3>
            <div class="text-xs text-gray-400">
                Checks: Market State (5s) • Aggressive Flow (1s) • Auto-Trading (1s) • Real-time tick data
            </div>
        </div>
        <div class="bg-black rounded p-3 font-mono text-xs max-h-96 overflow-y-auto space-y-1">
            @forelse($engineLogs as $log)
            <div class="flex gap-2">
                <span class="text-gray-500">{{ substr($log['time'], 11, 8) }}</span>
                <span class="
                    @if($log['level'] === 'ERROR') text-red-400
                    @elseif($log['level'] === 'WARNING') text-yellow-400
                    @elseif($log['level'] === 'INFO') text-blue-400
                    @else text-gray-400
                    @endif
                ">{{ $log['level'] }}</span>
                <span class="text-gray-300 flex-1">{{ $log['message'] }}</span>
            </div>
            @empty
            <div class="text-gray-500 text-center py-4">No recent logs</div>
            @endforelse
        </div>
        <div class="mt-2 text-xs text-gray-500 text-center">
            Auto-updates every 3 seconds • Last 30 log entries • Ultra-fast mode
        </div>
    </div>

    <!-- Auto-refresh -->
    <div wire:poll.3s="loadStocks" class="text-center text-sm text-gray-500">
        Auto-refreshing every 3 seconds... <span class="font-mono">Last update: {{ $lastUpdate }}</span>
    </div>
</div>

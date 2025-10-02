<div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
        <h2 class="text-2xl font-bold text-gray-900">📊 Backtesting</h2>
        <button 
            wire:click="toggleRunForm" 
            class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-semibold"
        >
            {{ $showRunForm ? 'Cancel' : '+ New Backtest' }}
        </button>
    </div>

    <!-- Flash Messages -->
    @if (session()->has('message'))
        <div class="p-3 bg-green-50 border border-green-200 rounded-lg text-green-800 text-sm">
            ✅ {{ session('message') }}
        </div>
    @endif

    @if (session()->has('error'))
        <div class="p-3 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
            ❌ {{ session('error') }}
        </div>
    @endif

    <!-- New Backtest Form -->
    @if ($showRunForm)
    <div class="bg-white p-6 rounded-lg shadow">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Run New Backtest</h3>
        
        <form wire:submit="runBacktest" class="space-y-4">
            <!-- Symbols Selection -->
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Symbols</label>
                <div class="grid grid-cols-6 gap-2">
                    @foreach($availableSymbols as $symbol)
                    <label class="flex items-center space-x-2 cursor-pointer">
                        <input 
                            type="checkbox" 
                            wire:model="selectedSymbols" 
                            value="{{ $symbol }}"
                            class="rounded border-gray-300"
                        >
                        <span class="text-sm">{{ $symbol }}</span>
                    </label>
                    @endforeach
                </div>
                @error('selectedSymbols') <span class="text-red-600 text-xs">{{ $message }}</span> @enderror
            </div>

            <!-- Parameters -->
            <div class="grid grid-cols-4 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Years of History</label>
                    <input 
                        type="number" 
                        wire:model="years" 
                        step="0.1" 
                        min="0.01" 
                        max="10"
                        class="w-full border-gray-300 rounded-md text-sm"
                    >
                    @error('years') <span class="text-red-600 text-xs">{{ $message }}</span> @enderror
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Initial Capital ($)</label>
                    <input 
                        type="number" 
                        wire:model="initialCapital" 
                        step="1000"
                        class="w-full border-gray-300 rounded-md text-sm"
                    >
                    @error('initialCapital') <span class="text-red-600 text-xs">{{ $message }}</span> @enderror
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Risk Per Trade (%)</label>
                    <input 
                        type="number" 
                        wire:model="riskPerTrade" 
                        step="0.1"
                        class="w-full border-gray-300 rounded-md text-sm"
                    >
                    @error('riskPerTrade') <span class="text-red-600 text-xs">{{ $message }}</span> @enderror
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Max Positions</label>
                    <input 
                        type="number" 
                        wire:model="maxPositions" 
                        min="1" 
                        max="10"
                        class="w-full border-gray-300 rounded-md text-sm"
                    >
                    @error('maxPositions') <span class="text-red-600 text-xs">{{ $message }}</span> @enderror
                </div>
            </div>

            <!-- Submit -->
            <div class="flex justify-end">
                <button 
                    type="submit"
                    class="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 font-semibold"
                >
                    🚀 Run Backtest
                </button>
            </div>
        </form>
    </div>
    @endif

    <!-- Results Section -->
    <div class="grid grid-cols-3 gap-4">
        <!-- Backtest Runs List -->
        <div class="bg-white p-4 rounded-lg shadow">
            <h3 class="text-sm font-semibold text-gray-700 mb-3">Backtest Runs</h3>
            
            <div class="space-y-2">
                @forelse($runs as $run)
                <div 
                    wire:click="selectRun({{ $run->id }})"
                    class="p-3 border rounded-lg cursor-pointer hover:bg-gray-50 {{ $selectedRunId === $run->id ? 'border-blue-500 bg-blue-50' : 'border-gray-200' }}"
                >
                    <div class="flex items-center justify-between mb-1">
                        <span class="text-sm font-semibold">{{ $run->name }}</span>
                        <span class="px-2 py-1 bg-{{ $run->status_color }}-100 text-{{ $run->status_color }}-800 rounded text-xs">
                            {{ $run->status }}
                        </span>
                    </div>
                    
                    <div class="text-xs text-gray-600">
                        {{ implode(', ', array_slice($run->symbols ?? [], 0, 3)) }}{{ count($run->symbols ?? []) > 3 ? '...' : '' }}
                    </div>
                    
                    @if($run->isCompleted())
                    <div class="mt-2 flex items-center justify-between text-xs">
                        <span class="text-gray-600">{{ $run->total_trades }} trades</span>
                        <span class="font-semibold text-{{ $run->profit_color }}-600">
                            {{ $run->total_pnl >= 0 ? '+' : '' }}{{ number_format($run->total_pnl_pct, 2) }}%
                        </span>
                    </div>
                    @endif
                    
                    <div class="text-xs text-gray-500 mt-1">
                        {{ $run->created_at->diffForHumans() }}
                    </div>
                </div>
                @empty
                <div class="text-center py-8 text-gray-500 text-sm">
                    No backtests yet. Click "New Backtest" to get started!
                </div>
                @endforelse
            </div>

            <div class="mt-4">
                {{ $runs->links() }}
            </div>
        </div>

        <!-- Selected Run Details -->
        <div class="col-span-2 space-y-4">
            @if($selectedRun)
                <!-- Performance Metrics -->
                <div class="bg-white p-4 rounded-lg shadow">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-lg font-semibold text-gray-900">{{ $selectedRun->name }}</h3>
                        <button 
                            wire:click="deleteRun({{ $selectedRun->id }})"
                            wire:confirm="Are you sure you want to delete this backtest?"
                            class="px-3 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700"
                        >
                            Delete
                        </button>
                    </div>

                    <div class="grid grid-cols-4 gap-4">
                        <div class="text-center p-3 bg-blue-50 rounded-lg">
                            <div class="text-xs text-gray-600 mb-1">Total P&L</div>
                            <div class="text-2xl font-bold text-{{ $selectedRun->profit_color }}-600">
                                {{ $selectedRun->total_pnl >= 0 ? '+' : '' }}{{ number_format($selectedRun->total_pnl_pct, 2) }}%
                            </div>
                            <div class="text-xs text-gray-500 mt-1">
                                ${{ number_format($selectedRun->total_pnl, 2) }}
                            </div>
                        </div>

                        <div class="text-center p-3 bg-green-50 rounded-lg">
                            <div class="text-xs text-gray-600 mb-1">Win Rate</div>
                            <div class="text-2xl font-bold text-gray-900">
                                {{ number_format($selectedRun->win_rate, 1) }}%
                            </div>
                            <div class="text-xs text-gray-500 mt-1">
                                {{ $selectedRun->winning_trades }}W / {{ $selectedRun->losing_trades }}L
                            </div>
                        </div>

                        <div class="text-center p-3 bg-purple-50 rounded-lg">
                            <div class="text-xs text-gray-600 mb-1">Total Trades</div>
                            <div class="text-2xl font-bold text-gray-900">
                                {{ $selectedRun->total_trades }}
                            </div>
                            <div class="text-xs text-gray-500 mt-1">
                                Avg: {{ $selectedRun->avg_trade_duration_minutes ?? 0 }}m
                            </div>
                        </div>

                        <div class="text-center p-3 bg-orange-50 rounded-lg">
                            <div class="text-xs text-gray-600 mb-1">Sharpe Ratio</div>
                            <div class="text-2xl font-bold text-gray-900">
                                {{ number_format($selectedRun->sharpe_ratio ?? 0, 2) }}
                            </div>
                            <div class="text-xs text-gray-500 mt-1">
                                Risk-adjusted
                            </div>
                        </div>
                    </div>

                    <!-- Additional Metrics -->
                    <div class="mt-4 grid grid-cols-2 gap-4 text-sm">
                        <div class="flex justify-between p-2 bg-gray-50 rounded">
                            <span class="text-gray-600">Avg Win:</span>
                            <span class="font-semibold text-green-600">${{ number_format($selectedRun->avg_win, 2) }}</span>
                        </div>
                        <div class="flex justify-between p-2 bg-gray-50 rounded">
                            <span class="text-gray-600">Avg Loss:</span>
                            <span class="font-semibold text-red-600">${{ number_format($selectedRun->avg_loss, 2) }}</span>
                        </div>
                        <div class="flex justify-between p-2 bg-gray-50 rounded">
                            <span class="text-gray-600">Largest Win:</span>
                            <span class="font-semibold text-green-600">${{ number_format($selectedRun->largest_win, 2) }}</span>
                        </div>
                        <div class="flex justify-between p-2 bg-gray-50 rounded">
                            <span class="text-gray-600">Largest Loss:</span>
                            <span class="font-semibold text-red-600">${{ number_format($selectedRun->largest_loss, 2) }}</span>
                        </div>
                    </div>
                </div>

                <!-- Equity Curve Chart -->
                <div class="bg-white p-4 rounded-lg shadow">
                    <h3 class="text-sm font-semibold text-gray-700 mb-3">Equity Curve</h3>
                    <div id="equity-chart" style="height: 300px;"></div>
                </div>

                <!-- Trade List -->
                <div class="bg-white p-4 rounded-lg shadow">
                    <h3 class="text-sm font-semibold text-gray-700 mb-3">Recent Trades (Top 20)</h3>
                    
                    <div class="overflow-x-auto">
                        <table class="min-w-full text-xs">
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="px-3 py-2 text-left">Symbol</th>
                                    <th class="px-3 py-2 text-left">Entry</th>
                                    <th class="px-3 py-2 text-left">Exit</th>
                                    <th class="px-3 py-2 text-right">Qty</th>
                                    <th class="px-3 py-2 text-right">P&L</th>
                                    <th class="px-3 py-2 text-right">P&L %</th>
                                    <th class="px-3 py-2 text-left">Exit Reason</th>
                                    <th class="px-3 py-2 text-right">Duration</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-200">
                                @foreach($trades as $trade)
                                <tr class="hover:bg-gray-50">
                                    <td class="px-3 py-2 font-semibold">{{ $trade->symbol->symbol }}</td>
                                    <td class="px-3 py-2">${{ number_format($trade->entry_price, 2) }}</td>
                                    <td class="px-3 py-2">${{ number_format($trade->exit_price, 2) }}</td>
                                    <td class="px-3 py-2 text-right">{{ $trade->quantity }}</td>
                                    <td class="px-3 py-2 text-right font-semibold text-{{ $trade->pnl_color }}-600">
                                        ${{ number_format($trade->pnl, 2) }}
                                    </td>
                                    <td class="px-3 py-2 text-right font-semibold text-{{ $trade->pnl_color }}-600">
                                        {{ $trade->pnl >= 0 ? '+' : '' }}{{ number_format($trade->pnl_pct, 2) }}%
                                    </td>
                                    <td class="px-3 py-2">{{ $trade->exit_reason }}</td>
                                    <td class="px-3 py-2 text-right">{{ $trade->duration_minutes }}m</td>
                                </tr>
                                @endforeach
                            </tbody>
                        </table>
                    </div>
                </div>
            @else
                <div class="bg-white p-8 rounded-lg shadow text-center text-gray-500">
                    Select a backtest run to view results
                </div>
            @endif
        </div>
    </div>
</div>

@script
<script>
let equityChart = null;

$wire.on('equity-curve-data', (event) => {
    const { labels, equity } = event;
    
    if (equityChart) {
        equityChart.remove();
    }
    
    const container = document.getElementById('equity-chart');
    equityChart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 300,
        layout: {
            background: { color: '#ffffff' },
            textColor: '#333',
        },
        grid: {
            vertLines: { color: '#f0f0f0' },
            horzLines: { color: '#f0f0f0' },
        },
    });
    
    const lineSeries = equityChart.addLineSeries({
        color: '#2563eb',
        lineWidth: 2,
    });
    
    const data = labels.map((label, i) => ({
        time: label,
        value: equity[i]
    }));
    
    lineSeries.setData(data);
    equityChart.timeScale().fitContent();
});
</script>
@endscript

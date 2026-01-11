<div class="space-y-4" wire:poll.2s="loadAllData">
    {{-- Flash Messages --}}
    @if (session('success'))
        <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative" role="alert">
            <span class="block sm:inline">{{ session('success') }}</span>
        </div>
    @endif

    @if (session('error'))
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
            <span class="block sm:inline">{{ session('error') }}</span>
        </div>
    @endif

    {{-- Capital Allocation Cards --}}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {{-- Total Allocated --}}
        <div class="bg-cyan-50 p-4 rounded-lg border-l-4 border-cyan-500 shadow">
            <div class="text-sm text-gray-600 mb-1">Total Allocated</div>
            <div class="text-2xl font-bold text-cyan-700">
                £{{ number_format($capitalAllocation['total'] ?? 0, 2) }}
            </div>
            <div class="text-xs text-gray-500 mt-1">Binary Options Capital</div>
        </div>

        {{-- Currently Used --}}
        <div class="bg-purple-50 p-4 rounded-lg border-l-4 border-purple-500 shadow">
            <div class="text-sm text-gray-600 mb-1">Currently Used</div>
            <div class="text-2xl font-bold text-purple-700">
                £{{ number_format($capitalAllocation['used'] ?? 0, 2) }}
            </div>
            <div class="text-xs text-gray-500 mt-1">In Open Positions</div>
        </div>

        {{-- Available --}}
        <div class="bg-green-50 p-4 rounded-lg border-l-4 border-green-500 shadow">
            <div class="text-sm text-gray-600 mb-1">Available</div>
            <div class="text-2xl font-bold text-green-700">
                £{{ number_format($capitalAllocation['available'] ?? 0, 2) }}
            </div>
            <div class="text-xs text-gray-500 mt-1">For New Positions</div>
        </div>

        {{-- Win Rate --}}
        <div class="bg-blue-50 p-4 rounded-lg border-l-4 border-blue-500 shadow">
            <div class="text-sm text-gray-600 mb-1">Win Rate</div>
            <div class="text-2xl font-bold text-blue-700">
                {{ number_format($capitalAllocation['win_rate'] ?? 100, 1) }}%
            </div>
            <div class="text-xs text-gray-500 mt-1">Arbitrage Guarantee</div>
        </div>
    </div>

    {{-- Active Opportunities --}}
    <div class="bg-white p-4 rounded-lg shadow">
        <h2 class="text-lg font-semibold mb-4">🔍 Active Opportunities</h2>

        @if(count($activeOpportunities) > 0)
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                @foreach($activeOpportunities as $opp)
                    <div class="border border-gray-200 rounded-lg p-4 hover:border-cyan-500 transition-colors">
                        <h3 class="font-semibold text-gray-900 mb-2 line-clamp-2">{{ $opp['question'] }}</h3>

                        <div class="grid grid-cols-2 gap-2 text-sm mb-3">
                            <div>
                                <span class="text-gray-600">YES:</span>
                                <span class="font-semibold text-green-600">${{ number_format($opp['yes_ask'], 2) }}</span>
                            </div>
                            <div>
                                <span class="text-gray-600">NO:</span>
                                <span class="font-semibold text-red-600">${{ number_format($opp['no_ask'], 2) }}</span>
                            </div>
                        </div>

                        <div class="flex justify-between items-center mb-3">
                            <span class="text-xs text-gray-500">Spread: ${{ number_format($opp['spread'], 2) }}</span>
                            <span class="text-xs font-semibold {{ $opp['estimated_profit_pct'] > 2 ? 'text-green-600' : 'text-cyan-600' }}">
                                +{{ number_format($opp['estimated_profit_pct'], 2) }}%
                            </span>
                        </div>

                        <div class="text-xs text-gray-400 mb-3">
                            Resolves: {{ \Carbon\Carbon::parse($opp['end_date'])->format('M d, Y') }}
                        </div>

                        <button
                            wire:click="executeArbitrage({{ $opp['market_id'] }})"
                            class="w-full bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2 rounded text-sm font-semibold transition-colors"
                        >
                            Execute Arbitrage
                        </button>
                    </div>
                @endforeach
            </div>
        @else
            <div class="text-center py-12">
                <div class="text-gray-400 text-5xl mb-3">🔍</div>
                <p class="text-gray-500">No arbitrage opportunities available at the moment.</p>
                <p class="text-gray-400 text-sm mt-1">Check back in a few minutes or ensure data ingestion is running.</p>
            </div>
        @endif
    </div>

    {{-- Open Positions --}}
    <div class="bg-white p-4 rounded-lg shadow">
        <h2 class="text-lg font-semibold mb-4">📍 Open Positions</h2>

        @if(count($openPositions) > 0)
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                @foreach($openPositions as $pos)
                    <div class="border border-gray-200 rounded-lg p-4 bg-gradient-to-br from-green-50 to-white">
                        <h3 class="font-semibold text-gray-900 mb-2 line-clamp-2">{{ $pos['question'] }}</h3>

                        <div class="space-y-1 text-sm mb-3">
                            <div class="flex justify-between">
                                <span class="text-gray-600">Entry Spread:</span>
                                <span class="font-semibold">${{ number_format($pos['entry_spread'], 2) }}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Locked Profit:</span>
                                <span class="font-semibold text-green-600">
                                    £{{ number_format($pos['locked_profit'], 2) }}
                                    ({{ number_format($pos['locked_profit_pct'], 2) }}%)
                                </span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Days Held:</span>
                                <span class="font-semibold">{{ $pos['days_held'] }} day{{ $pos['days_held'] != 1 ? 's' : '' }}</span>
                            </div>
                        </div>

                        <div class="text-xs text-gray-500 mb-3">
                            Resolves {{ \Carbon\Carbon::parse($pos['end_date'])->diffForHumans() }}
                        </div>

                        <div class="flex gap-2">
                            <button
                                wire:click="closePosition({{ $pos['id'] }})"
                                class="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-2 rounded text-xs font-semibold transition-colors"
                            >
                                Close Early
                            </button>
                            <button
                                class="flex-1 bg-cyan-600 hover:bg-cyan-700 text-white px-3 py-2 rounded text-xs font-semibold transition-colors"
                                onclick="alert('Position details view not yet implemented')"
                            >
                                View Details
                            </button>
                        </div>
                    </div>
                @endforeach
            </div>
        @else
            <div class="text-center py-12">
                <div class="text-gray-400 text-5xl mb-3">📍</div>
                <p class="text-gray-500">No open positions.</p>
                <p class="text-gray-400 text-sm mt-1">Execute an arbitrage opportunity to create a position.</p>
            </div>
        @endif
    </div>

    {{-- Performance Metrics --}}
    <div class="bg-white p-4 rounded-lg shadow">
        <h2 class="text-lg font-semibold mb-4">📈 Performance Metrics</h2>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="text-center p-4 bg-purple-50 rounded-lg">
                <div class="text-3xl font-bold text-purple-600">{{ $performanceMetrics['total_positions'] ?? 0 }}</div>
                <div class="text-sm text-gray-600 mt-1">Total Positions</div>
            </div>
            <div class="text-center p-4 bg-green-50 rounded-lg">
                <div class="text-3xl font-bold text-green-600">£{{ number_format($performanceMetrics['total_profit'] ?? 0, 2) }}</div>
                <div class="text-sm text-gray-600 mt-1">
                    Total Profit
                    @if(isset($performanceMetrics['total_profit_pct']))
                        ({{ number_format($performanceMetrics['total_profit_pct'], 2) }}%)
                    @endif
                </div>
            </div>
            <div class="text-center p-4 bg-blue-50 rounded-lg">
                <div class="text-3xl font-bold text-blue-600">{{ number_format($performanceMetrics['avg_hold_time'] ?? 0, 1) }}</div>
                <div class="text-sm text-gray-600 mt-1">Avg Hold Time (days)</div>
            </div>
        </div>

        @if(($performanceMetrics['total_positions'] ?? 0) > 0)
            <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <div class="flex justify-between p-3 bg-gray-50 rounded">
                    <span class="text-gray-600">Average Profit:</span>
                    <span class="font-semibold">£{{ number_format($performanceMetrics['avg_profit'] ?? 0, 2) }}</span>
                </div>
                <div class="flex justify-between p-3 bg-gray-50 rounded">
                    <span class="text-gray-600">Win Rate:</span>
                    <span class="font-semibold text-green-600">{{ number_format($performanceMetrics['win_rate'] ?? 100, 1) }}%</span>
                </div>
            </div>
        @endif
    </div>

    {{-- Recent History --}}
    <div class="bg-white p-4 rounded-lg shadow">
        <h2 class="text-lg font-semibold mb-4">🕐 Recent History</h2>

        @if(count($recentHistory) > 0)
            <div class="overflow-x-auto">
                <table class="min-w-full text-sm">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-4 py-2 text-left font-semibold text-gray-700">Market</th>
                            <th class="px-4 py-2 text-left font-semibold text-gray-700">Entry Spread</th>
                            <th class="px-4 py-2 text-left font-semibold text-gray-700">Profit</th>
                            <th class="px-4 py-2 text-left font-semibold text-gray-700">Resolution</th>
                            <th class="px-4 py-2 text-left font-semibold text-gray-700">Closed</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach($recentHistory as $hist)
                            <tr class="border-b hover:bg-gray-50">
                                <td class="px-4 py-2">
                                    <div class="max-w-xs truncate" title="{{ $hist['question'] }}">
                                        {{ $hist['question'] }}
                                    </div>
                                </td>
                                <td class="px-4 py-2">${{ number_format($hist['entry_spread'], 2) }}</td>
                                <td class="px-4 py-2">
                                    <span class="font-semibold {{ $hist['profit_loss'] > 0 ? 'text-green-600' : 'text-red-600' }}">
                                        £{{ number_format($hist['profit_loss'], 2) }}
                                        ({{ number_format($hist['profit_loss_pct'], 2) }}%)
                                    </span>
                                </td>
                                <td class="px-4 py-2">
                                    @if($hist['resolution'])
                                        <span class="px-2 py-1 rounded text-xs {{ $hist['resolution'] == 'yes' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700' }}">
                                            {{ strtoupper($hist['resolution']) }}
                                        </span>
                                    @else
                                        <span class="text-gray-400">-</span>
                                    @endif
                                </td>
                                <td class="px-4 py-2 text-gray-600">
                                    {{ \Carbon\Carbon::parse($hist['closed_at'])->format('M d, Y') }}
                                </td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @else
            <div class="text-center py-12">
                <div class="text-gray-400 text-5xl mb-3">🕐</div>
                <p class="text-gray-500">No closed positions yet.</p>
                <p class="text-gray-400 text-sm mt-1">Your arbitrage history will appear here once positions are resolved.</p>
            </div>
        @endif
    </div>
</div>

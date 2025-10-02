<div class="p-6">
    <div class="mb-6">
        <div class="flex items-center justify-between">
            <div>
                <h2 class="text-2xl font-bold text-gray-900">Strategy Management</h2>
                <p class="text-gray-600 mt-1">Enable/disable strategies and adjust parameters per symbol</p>
            </div>
            <div class="flex gap-2">
                <button wire:click="enableAll" class="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
                    Enable All
                </button>
                <button wire:click="disableAll" class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700">
                    Disable All
                </button>
            </div>
        </div>
    </div>

    <!-- Flash Messages -->
    @if (session()->has('success'))
    <div class="mb-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative">
        <span class="block sm:inline">{{ session('success') }}</span>
    </div>
    @endif

    <!-- Strategies Table -->
    <div class="bg-white rounded-lg shadow overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Symbol
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Market
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Strategy
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Parameters
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Risk
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                    </th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                @foreach($strategies as $strategy)
                <tr class="{{ $strategy['enabled'] ? 'bg-white' : 'bg-gray-50' }}">
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="flex items-center">
                            <div>
                                <div class="text-sm font-bold text-gray-900">{{ $strategy['symbol'] }}</div>
                                <div class="text-xs text-gray-500">{{ $strategy['symbol_name'] }}</div>
                            </div>
                        </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                            {{ $strategy['market'] === 'NASDAQ' || $strategy['market'] === 'NYSE' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800' }}">
                            {{ $strategy['market'] ?? 'N/A' }}
                        </span>
                        <span class="ml-1 text-xs text-gray-500">{{ $strategy['provider'] ?? '' }}</span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="text-sm text-gray-900">{{ ucwords(str_replace('_', ' ', $strategy['strategy_name'])) }}</div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        @php
                            $params = json_decode($strategy['parameters'], true);
                        @endphp
                        <div class="text-xs">
                            <div>Aggression: {{ $params['min_aggression_score'] ?? 70 }}</div>
                            <div>Stop: {{ $params['atr_stop_multiplier'] ?? 1.5 }}x ATR</div>
                            <div>Target: {{ $params['atr_target_multiplier'] ?? 3.0 }}x ATR</div>
                        </div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {{ $strategy['risk_per_trade_pct'] }}%
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <button 
                            wire:click="toggleStrategy({{ $strategy['id'] }})"
                            class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                                {{ $strategy['enabled'] ? 'bg-green-600' : 'bg-gray-200' }}">
                            <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform
                                {{ $strategy['enabled'] ? 'translate-x-6' : 'translate-x-1' }}">
                            </span>
                        </button>
                        <span class="ml-2 text-xs {{ $strategy['enabled'] ? 'text-green-600 font-semibold' : 'text-gray-400' }}">
                            {{ $strategy['enabled'] ? 'ON' : 'OFF' }}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <button 
                            wire:click="openConfig('{{ $strategy['symbol'] }}', '{{ $strategy['strategy_name'] }}')"
                            class="text-blue-600 hover:text-blue-900">
                            Configure
                        </button>
                    </td>
                </tr>
                @endforeach
            </tbody>
        </table>
    </div>

    <!-- Configuration Modal -->
    @if($showConfigModal)
    <div class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
        <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4">
            <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="text-lg font-semibold text-gray-900">
                    Configure Strategy: {{ $selectedSymbol }}
                </h3>
                <p class="text-sm text-gray-500 mt-1">{{ ucwords(str_replace('_', ' ', $selectedStrategy)) }}</p>
            </div>
            
            <div class="px-6 py-4 space-y-6">
                <!-- Min Aggression Score -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">
                        Minimum Aggression Score (0-100)
                    </label>
                    <div class="flex items-center gap-4">
                        <input 
                            type="range" 
                            wire:model.live="minAggressionScore"
                            min="0" 
                            max="100" 
                            step="5"
                            class="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">
                        <span class="text-lg font-bold text-gray-900 w-12 text-right">{{ $minAggressionScore }}</span>
                    </div>
                    <p class="text-xs text-gray-500 mt-1">Higher = fewer but stronger signals</p>
                </div>

                <!-- ATR Stop Multiplier -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">
                        Stop Loss (ATR Multiplier)
                    </label>
                    <div class="flex items-center gap-4">
                        <input 
                            type="range" 
                            wire:model.live="atrStopMultiplier"
                            min="0.5" 
                            max="5" 
                            step="0.1"
                            class="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">
                        <span class="text-lg font-bold text-gray-900 w-12 text-right">{{ number_format($atrStopMultiplier, 1) }}x</span>
                    </div>
                    <p class="text-xs text-gray-500 mt-1">Tighter = less risk, more stops</p>
                </div>

                <!-- ATR Target Multiplier -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">
                        Take Profit (ATR Multiplier)
                    </label>
                    <div class="flex items-center gap-4">
                        <input 
                            type="range" 
                            wire:model.live="atrTargetMultiplier"
                            min="1" 
                            max="10" 
                            step="0.5"
                            class="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">
                        <span class="text-lg font-bold text-gray-900 w-12 text-right">{{ number_format($atrTargetMultiplier, 1) }}x</span>
                    </div>
                    <p class="text-xs text-gray-500 mt-1">Higher = bigger wins, longer holds</p>
                </div>

                <!-- Risk Per Trade -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">
                        Risk Per Trade (% of account)
                    </label>
                    <div class="flex items-center gap-4">
                        <input 
                            type="range" 
                            wire:model.live="riskPerTradePct"
                            min="0.1" 
                            max="5" 
                            step="0.1"
                            class="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">
                        <span class="text-lg font-bold text-gray-900 w-12 text-right">{{ number_format($riskPerTradePct, 1) }}%</span>
                    </div>
                    <p class="text-xs text-gray-500 mt-1">Conservative: 0.5-1%, Aggressive: 2-5%</p>
                </div>

                <!-- Risk:Reward Ratio Display -->
                <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <div class="flex items-center justify-between">
                        <span class="text-sm font-medium text-gray-700">Risk:Reward Ratio</span>
                        <span class="text-2xl font-bold text-blue-600">
                            1:{{ number_format($atrTargetMultiplier / $atrStopMultiplier, 1) }}
                        </span>
                    </div>
                    <p class="text-xs text-gray-600 mt-1">
                        For every $1 risked, potential profit is ${{ number_format($atrTargetMultiplier / $atrStopMultiplier, 2) }}
                    </p>
                </div>
            </div>

            <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
                <button 
                    wire:click="closeModal"
                    class="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50">
                    Cancel
                </button>
                <button 
                    wire:click="saveConfig"
                    class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                    Save Configuration
                </button>
            </div>
        </div>
    </div>
    @endif
</div>

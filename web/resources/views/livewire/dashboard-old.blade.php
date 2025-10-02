<div class="space-y-4">
    <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
            <label for="symbol" class="text-sm font-medium text-gray-700">Symbol</label>
            <select id="symbol" wire:model.live="symbol" class="border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500">
                @foreach($this->symbols as $sym)
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

    <div class="bg-white p-4 rounded-lg shadow">
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
        window.dashboardChart = window.dashboardChart || null;
        let currentSymbol = @json($this->symbol ?? 'AAPL');
        let currentChannel = null;
        let currentTimeframe = '1m';
        let signalMarkers = [];

        function renderChart(labels, closes, signals = [], volumeProfile = {}, orderFlow = {}) {
            const container = document.getElementById('priceChart');
            if (!container) return;
            
            console.log('Rendering TradingView chart:', { closes: closes.length, signals: signals.length });
            
            // Build annotations (signals + volume profile)
            const annotations = {};
            
            // Add signal markers
            signals.forEach((sig, idx) => {
                // Find the matching candle to get exact price
                const matchingCandle = closes.find(c => c.x === sig.time);
                const signalPrice = matchingCandle ? matchingCandle.c : sig.price;
                
                annotations[`signal${idx}`] = {
                    type: 'point',
                    xValue: sig.time,
                    yValue: signalPrice,
                    backgroundColor: sig.type === 'BUY' ? 'rgba(34, 197, 94, 0.9)' : 'rgba(239, 68, 68, 0.9)',
                    borderColor: 'white',
                    borderWidth: 2,
                    radius: 8,
                    label: {
                        display: true,
                        content: sig.type === 'BUY' ? '▲ BUY' : '▼ SELL',
                        position: sig.type === 'BUY' ? 'bottom' : 'top',
                        backgroundColor: sig.type === 'BUY' ? 'rgba(34, 197, 94, 0.95)' : 'rgba(239, 68, 68, 0.95)',
                        color: 'white',
                        font: { size: 11, weight: 'bold' },
                        padding: 6,
                        borderRadius: 4
                    }
                };
            });
            
            // Add volume profile overlays
            if (volumeProfile && volumeProfile.poc) {
                // POC (Point of Control) - horizontal line
                annotations.poc = {
                    type: 'line',
                    yMin: volumeProfile.poc,
                    yMax: volumeProfile.poc,
                    borderColor: 'rgb(59, 130, 246)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    label: {
                        display: true,
                        content: 'POC: $' + volumeProfile.poc.toFixed(2),
                        position: 'end',
                        backgroundColor: 'rgba(59, 130, 246, 0.9)',
                        color: 'white',
                        font: { size: 10, weight: 'bold' }
                    }
                };
                
                // VAH/VAL (Value Area) - shaded box
                if (volumeProfile.vah && volumeProfile.val) {
                    annotations.valueArea = {
                        type: 'box',
                        yMin: volumeProfile.val,
                        yMax: volumeProfile.vah,
                        backgroundColor: 'rgba(59, 130, 246, 0.05)',
                        borderColor: 'rgba(59, 130, 246, 0.3)',
                        borderWidth: 1,
                        label: {
                            display: true,
                            content: 'Value Area',
                            position: { x: 'start', y: 'start' },
                            color: 'rgb(59, 130, 246)',
                            font: { size: 9 }
                        }
                    };
                }
                
                // LVNs (Low Volume Nodes) - red markers
                if (volumeProfile.lvns && volumeProfile.lvns.length > 0) {
                    volumeProfile.lvns.slice(0, 5).forEach((lvn, idx) => {
                        annotations[`lvn${idx}`] = {
                            type: 'line',
                            yMin: lvn,
                            yMax: lvn,
                            borderColor: 'rgba(239, 68, 68, 0.6)',
                            borderWidth: 1,
                            borderDash: [2, 2],
                            label: {
                                display: true,
                                content: 'LVN',
                                position: 'start',
                                backgroundColor: 'rgba(239, 68, 68, 0.8)',
                                color: 'white',
                                font: { size: 8 }
                            }
                        };
                    });
                }
            }

            // Destroy existing chart to prevent sizing issues on Livewire updates
            if (window.dashboardChart) {
                window.dashboardChart.destroy();
                window.dashboardChart = null;
            }
            
            // Use line chart for now (candlestick has compatibility issues)
            // Extract close prices for line chart
            const priceData = closes.map(c => ({
                x: c.x,
                y: c.c
            }));
            
            console.log('Price data sample:', priceData.slice(0, 3));
            
            window.dashboardChart = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: [{
                        label: currentSymbol + ' Price',
                        data: priceData,
                        borderColor: 'rgb(79, 70, 229)',
                        backgroundColor: 'rgba(79, 70, 229, 0.1)',
                        fill: true,
                        pointRadius: 0,
                        borderWidth: 2,
                        tension: 0.1,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            enabled: true,
                            mode: 'index',
                            intersect: false,
                            callbacks: {
                                title: (items) => items[0]?.label || '',
                                label: (context) => `Price: $${context.parsed.y.toFixed(2)}`
                            }
                        },
                        zoom: {
                            pan: {
                                enabled: true,
                                mode: 'x',
                            },
                            zoom: {
                                wheel: { enabled: true },
                                pinch: { enabled: true },
                                mode: 'x',
                            },
                            limits: {
                                x: { min: 'original', max: 'original' },
                            }
                        },
                        annotation: {
                            annotations: annotations
                        }
                    },
                    scales: {
                        x: {
                            type: 'category',
                            display: true,
                            title: { display: true, text: 'Time (ET)' },
                            ticks: {
                                maxRotation: 45,
                                minRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 12,
                                callback: function(value, index, ticks) {
                                    // Access data from the context
                                    const dataPoint = priceData[index];
                                    if (!dataPoint || !dataPoint.x) return '';
                                    
                                    const timeStr = dataPoint.x;
                                    // Format: "2025-10-01 05:45:00" -> "05:45"
                                    try {
                                        const parts = timeStr.split(' ');
                                        if (parts.length >= 2) {
                                            const timePart = parts[1].substring(0, 5); // HH:MM
                                            if (currentTimeframe === '1d') {
                                                return parts[0].substring(5); // MM-DD
                                            }
                                            return timePart;
                                        }
                                        return timeStr.substring(11, 16); // fallback HH:MM
                                    } catch {
                                        return '';
                                    }
                                }
                            }
                        },
                        y: {
                            display: true,
                            title: { display: true, text: 'Price ($)' },
                            beginAtZero: false,
                            ticks: {
                                callback: function(value) {
                                    return '$' + value.toFixed(2);
                                }
                            }
                        }
                    }
                }
            });
        }

        document.addEventListener('chart-data', (event) => {
            const { labels, closes, signals, volumeProfile, orderFlow } = event.detail;
            signalMarkers = signals || [];
            // Update timeframe from Livewire component
            currentTimeframe = @json($this->timeframe ?? '1m');
            renderChart(labels, closes, signalMarkers, volumeProfile, orderFlow);
            updatePressureIndicators(orderFlow);
        });

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

        // Reset zoom button (optional, can add to UI)
        function resetZoom() {
            if (window.dashboardChart) {
                window.dashboardChart.resetZoom();
            }
        }

        function subscribeToSymbol(sym) {
            if (!window.Echo) return; // Echo not initialized yet
            // leave previous channel
            if (currentChannel) {
                window.Echo.leave(`candles.${currentSymbol}`);
                currentChannel = null;
            }
            currentSymbol = sym;
            currentChannel = window.Echo.channel(`candles.${sym}`)
                .listen('.candle.ticked', (e) => {
                    // Append new point
                    if (!window.dashboardChart) return;
                    const labels = window.dashboardChart.data.labels;
                    const data = window.dashboardChart.data.datasets[0].data;
                    labels.push(e.time);
                    data.push(Number(e.close));
                    // Keep last 300 points
                    if (labels.length > 300) {
                        labels.shift();
                        data.shift();
                    }
                    window.dashboardChart.update('none');
                });
        }

        // initial subscribe once Echo is ready
        document.addEventListener('DOMContentLoaded', () => {
            subscribeToSymbol(currentSymbol);
        });

        // resubscribe on symbol change from Livewire
        document.addEventListener('symbol-changed', (ev) => {
            const sym = ev.detail.symbol;
            subscribeToSymbol(sym);
        });
    </script>
</div>

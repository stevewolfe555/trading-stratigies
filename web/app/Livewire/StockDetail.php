<?php

namespace App\Livewire;

use App\Services\MarketDataService;
use App\Services\TradingMetricsService;
use App\Services\AccountService;
use Illuminate\Support\Facades\DB;
use Livewire\Component;

class StockDetail extends Component
{
    // Services
    private MarketDataService $marketData;
    private TradingMetricsService $metrics;
    private AccountService $account;

    // Component properties
    public string $symbol = 'AAPL';
    public string $timeframe = '1m';
    public array $labels = [];
    public array $closes = [];
    public array $symbols = [];
    public array $marketState = [];
    public array $lvnAlert = [];
    public array $aggressiveFlow = [];
    public array $sessionInfo = [];
    public array $positions = [];
    public array $tradeHistory = [];
    public array $accountInfo = [];

    public function boot(
        MarketDataService $marketData,
        TradingMetricsService $metrics,
        AccountService $account
    ): void {
        $this->marketData = $marketData;
        $this->metrics = $metrics;
        $this->account = $account;
    }

    public function mount($symbol = null): void
    {
        // Load available symbols
        $this->symbols = DB::table('symbols')
            ->orderBy('symbol')
            ->pluck('symbol')
            ->toArray();

        if (empty($this->symbols)) {
            $this->symbols = ['AAPL'];
        }

        // Set initial symbol
        if ($symbol && in_array($symbol, $this->symbols)) {
            $this->symbol = $symbol;
        } else {
            $this->symbol = $this->symbols[0] ?? 'AAPL';
        }

        $this->loadAllData();
    }

    public function updatedSymbol(): void
    {
        $this->loadAllData();
    }

    public function updatedTimeframe(): void
    {
        $this->loadAllData();
    }

    private function loadAllData(): void
    {
        // Load market data
        $candleData = $this->marketData->loadCandles($this->symbol, $this->timeframe);
        $this->labels = $candleData['labels'];
        $this->closes = $candleData['closes'];

        // Load trading metrics
        $this->marketState = $this->metrics->loadMarketState($this->symbol);
        $this->lvnAlert = $this->metrics->loadLVNAlert($this->symbol);
        $this->aggressiveFlow = $this->metrics->loadAggressiveFlow($this->symbol);
        $this->sessionInfo = $this->metrics->getSessionInfo();

        // Load account data
        $this->accountInfo = $this->account->loadAccountInfo();
        $this->positions = $this->account->loadPositions();
        $this->tradeHistory = $this->account->loadTradeHistory();
    }

    public function render()
    {
        // Load fresh data for chart
        $signals = $this->marketData->loadSignals($this->symbol);
        $volumeProfile = $this->marketData->loadVolumeProfile($this->symbol);
        $orderFlow = $this->marketData->loadOrderFlow($this->symbol);

        // Dispatch chart data to JavaScript
        $this->dispatch('chart-data',
            labels: $this->labels,
            closes: $this->closes,
            signals: $signals,
            volumeProfile: $volumeProfile,
            orderFlow: $orderFlow
        );

        return view('livewire.stock-detail');
    }
}

<?php

namespace App\Livewire;

use App\Services\BinaryArbitrageService;
use Livewire\Component;

class ArbitrageMonitor extends Component
{
    // State
    public array $capitalAllocation = [];
    public array $activeOpportunities = [];
    public array $openPositions = [];
    public array $performanceMetrics = [];
    public array $recentHistory = [];

    // Service
    private BinaryArbitrageService $service;

    /**
     * Boot the component with dependencies
     */
    public function boot(BinaryArbitrageService $service): void
    {
        $this->service = $service;
    }

    /**
     * Mount the component
     */
    public function mount(): void
    {
        $this->loadAllData();
    }

    /**
     * Load all dashboard data
     */
    public function loadAllData(): void
    {
        $this->loadCapitalAllocation();
        $this->loadActiveOpportunities();
        $this->loadOpenPositions();
        $this->loadPerformanceMetrics();
        $this->loadRecentHistory();
    }

    /**
     * Load capital allocation data
     */
    public function loadCapitalAllocation(): void
    {
        $this->capitalAllocation = $this->service->getCapitalAllocation();
    }

    /**
     * Load active arbitrage opportunities
     */
    public function loadActiveOpportunities(): void
    {
        $this->activeOpportunities = $this->service->getActiveOpportunities(10);
    }

    /**
     * Load open positions
     */
    public function loadOpenPositions(): void
    {
        $this->openPositions = $this->service->getOpenPositions();
    }

    /**
     * Load performance metrics
     */
    public function loadPerformanceMetrics(): void
    {
        $this->performanceMetrics = $this->service->getPerformanceMetrics();
    }

    /**
     * Load recent history
     */
    public function loadRecentHistory(): void
    {
        $this->recentHistory = $this->service->getClosedPositions(20);
    }

    /**
     * Execute arbitrage for a market
     */
    public function executeArbitrage(int $marketId): void
    {
        try {
            $result = $this->service->executeArbitrage($marketId);

            if ($result['success']) {
                session()->flash('success', $result['message']);
            } else {
                session()->flash('error', $result['message']);
            }

            // Refresh data
            $this->loadAllData();
        } catch (\Exception $e) {
            session()->flash('error', 'Failed to execute arbitrage: ' . $e->getMessage());
        }
    }

    /**
     * Close a position early
     */
    public function closePosition(int $positionId): void
    {
        try {
            $success = $this->service->closePosition($positionId);

            if ($success) {
                session()->flash('success', 'Position close requested. This will be processed by the engine.');
            } else {
                session()->flash('error', 'Failed to close position. Position may not exist or is already closed.');
            }

            // Refresh data
            $this->loadAllData();
        } catch (\Exception $e) {
            session()->flash('error', 'Failed to close position: ' . $e->getMessage());
        }
    }

    /**
     * Render the component
     */
    public function render()
    {
        return view('livewire.arbitrage-monitor');
    }
}

<?php

namespace App\Livewire;

use App\Models\BacktestRun;
use App\Models\Symbol;
use App\Services\BacktestService;
use Livewire\Component;
use Livewire\WithPagination;

class Backtesting extends Component
{
    use WithPagination;
    
    private BacktestService $backtestService;
    
    // Form inputs
    public array $selectedSymbols = [];
    public $years = 1.0;
    public $initialCapital = 100000;
    public $riskPerTrade = 1.0;
    public $maxPositions = 3;

    // New advanced parameters
    public $testMode = 'portfolio'; // 'portfolio', 'individual', 'unlimited'
    public $individualSymbol = '';
    public $unlimitedMode = false;
    public $minAggressionScore = 70;
    public $atrStopMultiplier = 1.5;
    public $atrTargetMultiplier = 3.0;
    
    // State
    public bool $showRunForm = false;
    public ?int $selectedRunId = null;
    public array $availableSymbols = [];
    
    protected function casts(): array
    {
        return [
            'years' => 'float',
            'initialCapital' => 'float',
            'riskPerTrade' => 'float',
            'maxPositions' => 'integer',
            'minAggressionScore' => 'integer',
            'atrStopMultiplier' => 'float',
            'atrTargetMultiplier' => 'float',
            'unlimitedMode' => 'boolean',
        ];
    }
    
    public function boot(BacktestService $backtestService): void
    {
        $this->backtestService = $backtestService;
    }
    
    public function mount(): void
    {
        // Load available symbols
        $this->availableSymbols = Symbol::orderBy('symbol')
            ->pluck('symbol')
            ->toArray() ?? [];
        
        // Default to first 5 symbols
        if (!empty($this->availableSymbols)) {
            $this->selectedSymbols = array_slice($this->availableSymbols, 0, 5);
        }
    }
    
    public function toggleRunForm(): void
    {
        $this->showRunForm = !$this->showRunForm;
    }
    
    public function runBacktest(): void
    {
        // Dynamic validation based on test mode
        $rules = [
            'years' => 'required|numeric|min:0.01|max:10',
            'initialCapital' => 'required|numeric|min:1000',
            'riskPerTrade' => 'required|numeric|min:0.1|max:10',
            'maxPositions' => 'required|integer|min:1|max:10',
        ];

        // Add mode-specific validation
        if ($this->testMode === 'individual') {
            $rules['individualSymbol'] = 'required|string';
        } else {
            $rules['selectedSymbols'] = 'required|array|min:1';
        }

        // Add advanced parameter validation
        if (!$this->unlimitedMode) {
            $rules['minAggressionScore'] = 'required|integer|min:1|max:100';
            $rules['atrStopMultiplier'] = 'required|numeric|min:0.5|max:5';
            $rules['atrTargetMultiplier'] = 'required|numeric|min:1|max:10';
        }

        $this->validate($rules);

        // Convert to proper types
        $this->years = (float) $this->years;
        $this->initialCapital = (float) $this->initialCapital;
        $this->riskPerTrade = (float) $this->riskPerTrade;
        $this->maxPositions = (int) $this->maxPositions;
        $this->minAggressionScore = (int) $this->minAggressionScore;
        $this->atrStopMultiplier = (float) $this->atrStopMultiplier;
        $this->atrTargetMultiplier = (float) $this->atrTargetMultiplier;

        // Build parameters array
        $params = [
            'symbols' => $this->testMode === 'individual' ? [$this->individualSymbol] : $this->selectedSymbols,
            'years' => $this->years,
            'initial_capital' => $this->initialCapital,
            'risk_per_trade_pct' => $this->riskPerTrade,
            'max_positions' => $this->maxPositions,
            'test_mode' => $this->testMode,
            'unlimited_mode' => $this->unlimitedMode,
        ];

        // Add advanced parameters if not unlimited
        if (!$this->unlimitedMode) {
            $params = array_merge($params, [
                'min_aggression_score' => $this->minAggressionScore,
                'atr_stop_multiplier' => $this->atrStopMultiplier,
                'atr_target_multiplier' => $this->atrTargetMultiplier,
            ]);
        }

        // Set individual symbol for individual mode
        if ($this->testMode === 'individual') {
            $params['individual_symbol'] = $this->individualSymbol;
        }

        $run = $this->backtestService->runBacktest($params);

        if ($run) {
            $this->selectedRunId = $run->id;
            $this->showRunForm = false;
            session()->flash('message', 'Backtest completed successfully!');
        } else {
            session()->flash('error', 'Backtest failed. Check logs for details.');
        }
    }
    
    public function selectRun(int $runId): void
    {
        $this->selectedRunId = $runId;
    }
    
    public function deleteRun(int $runId): void
    {
        BacktestRun::find($runId)?->delete();
        
        if ($this->selectedRunId === $runId) {
            $this->selectedRunId = null;
        }
        
        session()->flash('message', 'Backtest deleted successfully!');
    }
    
    public function render()
    {
        $runs = BacktestRun::orderBy('created_at', 'desc')
            ->paginate(10);
        
        $selectedRun = null;
        $trades = [];
        $equityCurve = null;
        
        if ($this->selectedRunId) {
            $selectedRun = BacktestRun::with(['trades.symbol', 'equityCurve'])
                ->find($this->selectedRunId);
            
            if ($selectedRun) {
                $trades = $this->backtestService->getTrades($selectedRun, 20);
                $equityCurve = $this->backtestService->getEquityCurve($selectedRun);
            }
        }
        
        return view('livewire.backtesting', [
            'runs' => $runs,
            'selectedRun' => $selectedRun,
            'trades' => $trades,
            'equityCurve' => $equityCurve,
        ]);
    }
}

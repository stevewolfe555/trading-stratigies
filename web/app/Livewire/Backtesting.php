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
            ->toArray();
        
        // Default to first 5 symbols
        $this->selectedSymbols = array_slice($this->availableSymbols, 0, 5);
    }
    
    public function toggleRunForm(): void
    {
        $this->showRunForm = !$this->showRunForm;
    }
    
    public function runBacktest(): void
    {
        $this->validate([
            'selectedSymbols' => 'required|array|min:1',
            'years' => ['required', 'numeric', 'min:0.01', 'max:10'],
            'initialCapital' => ['required', 'numeric', 'min:1000'],
            'riskPerTrade' => ['required', 'numeric', 'min:0.1', 'max:10'],
            'maxPositions' => ['required', 'integer', 'min:1', 'max:10'],
        ]);
        
        $params = [
            'symbols' => $this->selectedSymbols,
            'years' => $this->years,
            'initial_capital' => $this->initialCapital,
            'risk_per_trade_pct' => $this->riskPerTrade,
            'max_positions' => $this->maxPositions,
        ];
        
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
                
                // Dispatch equity curve data to JavaScript
                $this->dispatch('equity-curve-data', 
                    labels: $equityCurve['labels'],
                    equity: $equityCurve['equity']
                );
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

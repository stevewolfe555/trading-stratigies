<?php

namespace App\Livewire;

use Livewire\Component;
use Illuminate\Support\Facades\DB;

class StrategyManager extends Component
{
    public $strategies = [];
    public $selectedSymbol = null;
    public $selectedStrategy = null;
    public $showConfigModal = false;
    
    // Config parameters
    public $minAggressionScore = 70;
    public $atrStopMultiplier = 1.5;
    public $atrTargetMultiplier = 3.0;
    public $riskPerTradePct = 1.0;
    
    public function mount()
    {
        $this->loadStrategies();
    }
    
    public function loadStrategies()
    {
        $this->strategies = DB::select("
            SELECT 
                sc.id,
                s.symbol,
                s.name as symbol_name,
                sc.strategy_name,
                sc.enabled,
                sc.parameters,
                sc.risk_per_trade_pct,
                sc.max_positions,
                sp.market,
                sp.provider
            FROM strategy_configs sc
            JOIN symbols s ON sc.symbol_id = s.id
            LEFT JOIN symbol_providers sp ON s.symbol = sp.symbol
            ORDER BY s.symbol
        ");
        
        // Convert to array for easier manipulation
        $this->strategies = array_map(function($strategy) {
            return (array) $strategy;
        }, $this->strategies);
    }
    
    public function toggleStrategy($configId)
    {
        $strategy = collect($this->strategies)->firstWhere('id', $configId);
        
        if ($strategy) {
            $newState = !$strategy['enabled'];
            
            DB::table('strategy_configs')
                ->where('id', $configId)
                ->update([
                    'enabled' => $newState,
                    'updated_at' => now()
                ]);
            
            $this->loadStrategies();
            
            $status = $newState ? 'enabled' : 'disabled';
            session()->flash('success', "Strategy {$status} for {$strategy['symbol']}");
        }
    }
    
    public function openConfig($symbol, $strategyName)
    {
        $this->selectedSymbol = $symbol;
        $this->selectedStrategy = $strategyName;
        
        // Load current parameters
        $config = DB::selectOne("
            SELECT sc.parameters, sc.risk_per_trade_pct
            FROM strategy_configs sc
            JOIN symbols s ON sc.symbol_id = s.id
            WHERE s.symbol = ? AND sc.strategy_name = ?
        ", [$symbol, $strategyName]);
        
        if ($config) {
            $params = json_decode($config->parameters, true);
            $this->minAggressionScore = $params['min_aggression_score'] ?? 70;
            $this->atrStopMultiplier = $params['atr_stop_multiplier'] ?? 1.5;
            $this->atrTargetMultiplier = $params['atr_target_multiplier'] ?? 3.0;
            $this->riskPerTradePct = $config->risk_per_trade_pct ?? 1.0;
        }
        
        $this->showConfigModal = true;
    }
    
    public function saveConfig()
    {
        $this->validate([
            'minAggressionScore' => 'required|numeric|min:0|max:100',
            'atrStopMultiplier' => 'required|numeric|min:0.1|max:5',
            'atrTargetMultiplier' => 'required|numeric|min:0.1|max:10',
            'riskPerTradePct' => 'required|numeric|min:0.1|max:5',
        ]);
        
        $parameters = [
            'min_aggression_score' => (int) $this->minAggressionScore,
            'atr_stop_multiplier' => (float) $this->atrStopMultiplier,
            'atr_target_multiplier' => (float) $this->atrTargetMultiplier,
        ];
        
        DB::statement("
            UPDATE strategy_configs sc
            SET 
                parameters = ?::jsonb,
                risk_per_trade_pct = ?,
                updated_at = NOW()
            FROM symbols s
            WHERE sc.symbol_id = s.id
                AND s.symbol = ?
                AND sc.strategy_name = ?
        ", [
            json_encode($parameters),
            $this->riskPerTradePct,
            $this->selectedSymbol,
            $this->selectedStrategy
        ]);
        
        $this->showConfigModal = false;
        $this->loadStrategies();
        
        session()->flash('success', "Configuration updated for {$this->selectedSymbol}");
    }
    
    public function closeModal()
    {
        $this->showConfigModal = false;
        $this->selectedSymbol = null;
        $this->selectedStrategy = null;
    }
    
    public function enableAll()
    {
        DB::table('strategy_configs')
            ->update(['enabled' => true, 'updated_at' => now()]);
        
        $this->loadStrategies();
        session()->flash('success', 'All strategies enabled');
    }
    
    public function disableAll()
    {
        DB::table('strategy_configs')
            ->update(['enabled' => false, 'updated_at' => now()]);
        
        $this->loadStrategies();
        session()->flash('success', 'All strategies disabled');
    }
    
    public function render()
    {
        return view('livewire.strategy-manager');
    }
}

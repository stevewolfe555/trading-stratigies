<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class BacktestTrade extends Model
{
    protected $table = 'backtest_trades';
    
    public $timestamps = false;
    
    protected $fillable = [
        'backtest_run_id',
        'symbol_id',
        'entry_time',
        'entry_price',
        'entry_reason',
        'exit_time',
        'exit_price',
        'exit_reason',
        'direction',
        'quantity',
        'pnl',
        'pnl_pct',
        'stop_loss',
        'take_profit',
        'atr_at_entry',
        'market_state',
        'aggressive_flow_score',
        'volume_ratio',
        'cvd_momentum',
        'bars_in_trade',
        'duration_minutes',
        'mae',
        'mfe',
    ];
    
    protected $casts = [
        'entry_time' => 'datetime',
        'exit_time' => 'datetime',
        'entry_price' => 'decimal:4',
        'exit_price' => 'decimal:4',
        'pnl' => 'decimal:2',
        'pnl_pct' => 'decimal:4',
        'stop_loss' => 'decimal:4',
        'take_profit' => 'decimal:4',
        'atr_at_entry' => 'decimal:4',
        'volume_ratio' => 'decimal:4',
        'mae' => 'decimal:4',
        'mfe' => 'decimal:4',
    ];
    
    public function backtestRun(): BelongsTo
    {
        return $this->belongsTo(BacktestRun::class, 'backtest_run_id');
    }
    
    public function symbol(): BelongsTo
    {
        return $this->belongsTo(Symbol::class);
    }
    
    public function isWinner(): bool
    {
        return $this->pnl > 0;
    }
    
    public function getPnlColorAttribute(): string
    {
        if (!$this->pnl) return 'gray';
        return $this->pnl >= 0 ? 'green' : 'red';
    }
}

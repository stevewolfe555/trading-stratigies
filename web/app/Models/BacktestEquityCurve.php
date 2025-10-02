<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class BacktestEquityCurve extends Model
{
    protected $table = 'backtest_equity_curve';
    
    public $timestamps = false;
    
    protected $fillable = [
        'backtest_run_id',
        'time',
        'equity',
        'cash',
        'positions_value',
        'drawdown',
        'drawdown_pct',
        'open_positions',
    ];
    
    protected $casts = [
        'time' => 'datetime',
        'equity' => 'decimal:2',
        'cash' => 'decimal:2',
        'positions_value' => 'decimal:2',
        'drawdown' => 'decimal:2',
        'drawdown_pct' => 'decimal:4',
    ];
    
    public function backtestRun(): BelongsTo
    {
        return $this->belongsTo(BacktestRun::class, 'backtest_run_id');
    }
}

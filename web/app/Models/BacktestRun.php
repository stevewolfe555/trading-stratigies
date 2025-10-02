<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class BacktestRun extends Model
{
    protected $table = 'backtest_runs';
    
    protected $fillable = [
        'name',
        'description',
        'strategy_name',
        'start_date',
        'end_date',
        'symbols',
        'parameters',
        'total_trades',
        'winning_trades',
        'losing_trades',
        'win_rate',
        'total_pnl',
        'total_pnl_pct',
        'avg_win',
        'avg_loss',
        'largest_win',
        'largest_loss',
        'max_drawdown',
        'max_drawdown_pct',
        'sharpe_ratio',
        'profit_factor',
        'status',
        'error_message',
        'started_at',
        'completed_at',
        'duration_seconds',
    ];
    
    protected $casts = [
        'start_date' => 'datetime',
        'end_date' => 'datetime',
        'symbols' => 'array',
        'parameters' => 'array',
        'win_rate' => 'decimal:2',
        'total_pnl' => 'decimal:2',
        'total_pnl_pct' => 'decimal:4',
        'avg_win' => 'decimal:2',
        'avg_loss' => 'decimal:2',
        'largest_win' => 'decimal:2',
        'largest_loss' => 'decimal:2',
        'max_drawdown' => 'decimal:4',
        'max_drawdown_pct' => 'decimal:4',
        'sharpe_ratio' => 'decimal:4',
        'profit_factor' => 'decimal:4',
        'started_at' => 'datetime',
        'completed_at' => 'datetime',
    ];
    
    public function trades(): HasMany
    {
        return $this->hasMany(BacktestTrade::class, 'backtest_run_id');
    }
    
    public function equityCurve(): HasMany
    {
        return $this->hasMany(BacktestEquityCurve::class, 'backtest_run_id');
    }
    
    public function dailyStats(): HasMany
    {
        return $this->hasMany(BacktestDailyStats::class, 'backtest_run_id');
    }
    
    public function isRunning(): bool
    {
        return $this->status === 'running';
    }
    
    public function isCompleted(): bool
    {
        return $this->status === 'completed';
    }
    
    public function isFailed(): bool
    {
        return $this->status === 'failed';
    }
    
    public function getStatusColorAttribute(): string
    {
        return match($this->status) {
            'pending' => 'gray',
            'running' => 'blue',
            'completed' => 'green',
            'failed' => 'red',
            default => 'gray',
        };
    }
    
    public function getProfitColorAttribute(): string
    {
        if (!$this->total_pnl) return 'gray';
        return $this->total_pnl >= 0 ? 'green' : 'red';
    }
}

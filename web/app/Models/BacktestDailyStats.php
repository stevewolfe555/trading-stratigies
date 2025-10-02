<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class BacktestDailyStats extends Model
{
    protected $table = 'backtest_daily_stats';
    
    public $timestamps = false;
    
    protected $fillable = [
        'backtest_run_id',
        'date',
        'trades_count',
        'winning_trades',
        'losing_trades',
        'daily_pnl',
        'daily_pnl_pct',
        'cumulative_pnl',
        'starting_equity',
        'ending_equity',
    ];
    
    protected $casts = [
        'date' => 'date',
        'daily_pnl' => 'decimal:2',
        'daily_pnl_pct' => 'decimal:4',
        'cumulative_pnl' => 'decimal:2',
        'starting_equity' => 'decimal:2',
        'ending_equity' => 'decimal:2',
    ];
    
    public function backtestRun(): BelongsTo
    {
        return $this->belongsTo(BacktestRun::class, 'backtest_run_id');
    }
}

<?php

namespace App\Services;

use App\Models\BacktestRun;
use Illuminate\Support\Facades\Process;
use Illuminate\Support\Facades\Log;

class BacktestService
{
    /**
     * Run a backtest using the Python engine
     */
    public function runBacktest(array $params): ?BacktestRun
    {
        $symbols = implode(',', $params['symbols']);
        $years = $params['years'] ?? 1;
        
        // Build command
        $command = sprintf(
            'docker compose exec -T engine python3 backtest.py --symbols %s --years %s',
            escapeshellarg($symbols),
            escapeshellarg($years)
        );
        
        Log::info("Running backtest: {$command}");
        
        try {
            // Run backtest in background
            $result = Process::path(base_path('..'))->run($command);
            
            if ($result->successful()) {
                // Get the latest backtest run
                $run = BacktestRun::latest('id')->first();
                
                Log::info("Backtest completed successfully", ['run_id' => $run?->id]);
                
                return $run;
            } else {
                Log::error("Backtest failed", [
                    'output' => $result->output(),
                    'error' => $result->errorOutput()
                ]);
                
                return null;
            }
        } catch (\Exception $e) {
            Log::error("Backtest exception", ['error' => $e->getMessage()]);
            return null;
        }
    }
    
    /**
     * Get backtest results summary
     */
    public function getResultsSummary(BacktestRun $run): array
    {
        return [
            'run' => $run,
            'trades_count' => $run->total_trades,
            'win_rate' => $run->win_rate,
            'total_pnl' => $run->total_pnl,
            'total_pnl_pct' => $run->total_pnl_pct,
            'avg_win' => $run->avg_win,
            'avg_loss' => $run->avg_loss,
            'largest_win' => $run->largest_win,
            'largest_loss' => $run->largest_loss,
            'sharpe_ratio' => $run->sharpe_ratio,
            'profit_factor' => $run->profit_factor,
            'max_drawdown' => $run->max_drawdown_pct,
        ];
    }
    
    /**
     * Get trade list for a backtest run
     */
    public function getTrades(BacktestRun $run, int $limit = 50)
    {
        return $run->trades()
            ->with('symbol')
            ->orderBy('entry_time', 'desc')
            ->limit($limit)
            ->get();
    }
    
    /**
     * Get equity curve data for charting
     */
    public function getEquityCurve(BacktestRun $run): array
    {
        $points = $run->equityCurve()
            ->orderBy('time')
            ->get();
        
        return [
            'labels' => $points->pluck('time')->map(fn($t) => $t->format('Y-m-d H:i'))->toArray(),
            'equity' => $points->pluck('equity')->toArray(),
            'drawdown' => $points->pluck('drawdown_pct')->toArray(),
        ];
    }
    
    /**
     * Get daily stats for a backtest run
     */
    public function getDailyStats(BacktestRun $run)
    {
        return $run->dailyStats()
            ->orderBy('date')
            ->get();
    }
    
    /**
     * Compare multiple backtest runs
     */
    public function compareRuns(array $runIds): array
    {
        $runs = BacktestRun::whereIn('id', $runIds)
            ->orderBy('total_pnl_pct', 'desc')
            ->get();
        
        return $runs->map(function($run) {
            return [
                'id' => $run->id,
                'name' => $run->name,
                'symbols' => $run->symbols,
                'win_rate' => $run->win_rate,
                'total_pnl_pct' => $run->total_pnl_pct,
                'sharpe_ratio' => $run->sharpe_ratio,
                'max_drawdown' => $run->max_drawdown_pct,
                'total_trades' => $run->total_trades,
            ];
        })->toArray();
    }
}

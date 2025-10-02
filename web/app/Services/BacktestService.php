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
        // Extract parameters
        $symbols = implode(',', $params['symbols'] ?? []);
        $years = $params['years'] ?? 1;
        $initialCapital = $params['initial_capital'] ?? 100000;
        $riskPerTrade = $params['risk_per_trade_pct'] ?? 1.0;
        $maxPositions = $params['max_positions'] ?? 3;

        // Test modes
        $testMode = $params['test_mode'] ?? 'portfolio'; // 'portfolio', 'individual', 'unlimited'
        $individualSymbol = $params['individual_symbol'] ?? null;
        $unlimitedMode = $params['unlimited_mode'] ?? false;

        // Build command based on test mode
        if ($testMode === 'individual' && $individualSymbol) {
            $command = sprintf(
                'docker compose exec -T engine python3 backtest.py --individual %s --years %s --initial-capital %s --risk-per-trade %s --max-positions %s',
                escapeshellarg($individualSymbol),
                escapeshellarg($years),
                escapeshellarg($initialCapital),
                escapeshellarg($riskPerTrade),
                escapeshellarg($maxPositions)
            );
        } elseif ($unlimitedMode || $testMode === 'unlimited') {
            $command = sprintf(
                'docker compose exec -T engine python3 backtest.py --symbols %s --years %s --initial-capital %s --risk-per-trade %s --max-positions %s --unlimited',
                escapeshellarg($symbols),
                escapeshellarg($years),
                escapeshellarg($initialCapital),
                escapeshellarg($riskPerTrade),
                escapeshellarg($maxPositions)
            );
        } else {
            // Portfolio mode (default)
            $command = sprintf(
                'docker compose exec -T engine python3 backtest.py --symbols %s --years %s --initial-capital %s --risk-per-trade %s --max-positions %s',
                escapeshellarg($symbols),
                escapeshellarg($years),
                escapeshellarg($initialCapital),
                escapeshellarg($riskPerTrade),
                escapeshellarg($maxPositions)
            );
        }

        Log::info("Running backtest: {$command}");

        try {
            // Create a pending run record first
            $run = BacktestRun::create([
                'name' => 'Backtest ' . now()->format('Y-m-d H:i:s'),
                'strategy_name' => 'auction_market',
                'start_date' => now()->subDays($years * 365),
                'end_date' => now(),
                'symbols' => $symbols ? explode(',', $symbols) : [],
                'parameters' => $params,
                'status' => 'running',
                'started_at' => now(),
            ]);

            // Run backtest in background with timeout
            $result = Process::path(base_path('..'))->timeout(300)->run($command);

            if ($result->successful()) {
                // Refresh the run to get updated data
                $run->refresh();

                Log::info("Backtest completed successfully", ['run_id' => $run->id]);

                return $run;
            } else {
                // Update run status to failed
                $run->update([
                    'status' => 'failed',
                    'error_message' => $result->errorOutput(),
                    'completed_at' => now(),
                ]);

                Log::error("Backtest failed", [
                    'output' => $result->output(),
                    'error' => $result->errorOutput()
                ]);

                return null;
            }
        } catch (\Exception $e) {
            Log::error("Backtest exception", ['error' => $e->getMessage()]);
            
            if (isset($run)) {
                $run->update([
                    'status' => 'failed',
                    'error_message' => $e->getMessage(),
                    'completed_at' => now(),
                ]);
            }
            
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
     * Get constraint analysis for a backtest run
     */
    public function getConstraintAnalysis(BacktestRun $run): array
    {
        // This would need to be stored in the database during backtest execution
        // For now, return a placeholder structure
        return [
            'signals_generated' => 0, // Would come from backtest engine logs
            'signals_blocked' => 0,  // Would come from backtest engine logs
            'blocked_percentage' => 0,
            'position_limit_hit' => 0,
            'capital_limit_hit' => 0,
            'recommendations' => [
                'max_positions_needed' => null,
                'capital_needed' => null,
            ]
        ];
    }

    /**
     * Get detailed backtest information including constraints
     */
    public function getDetailedResults(BacktestRun $run): array
    {
        $summary = $this->getResultsSummary($run);
        $constraints = $this->getConstraintAnalysis($run);

        return array_merge($summary, [
            'constraint_analysis' => $constraints,
            'parameters' => json_decode($run->parameters, true) ?? [],
            'version_info' => [
                'engine_version' => '1.0.0',
                'strategy_version' => '1.0.0',
                'config_version' => '1.0.0'
            ]
        ]);
    }
}

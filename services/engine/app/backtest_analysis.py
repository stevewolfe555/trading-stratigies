"""
Backtest Analysis Module

Handles results analysis, reporting, and constraint analysis.
Provides insights into strategy performance and recommendations.
"""

import psycopg2
from typing import Dict, List
from loguru import logger
from .versions import get_version_info


class BacktestAnalyzer:
    """Analyzes backtest results and provides insights."""

    def __init__(self, db_connection, portfolio, parameters: Dict):
        """Initialize analyzer."""
        self.conn = db_connection
        self.portfolio = portfolio
        self.parameters = parameters
        self.version = get_version_info()

    def save_results(self, run_id: int):
        """Save backtest results to database."""
        logger.info("Saving results...")

        try:
            # Save trades
            if self.portfolio.trades:
                with self.conn.cursor() as cur:
                    # Prepare trade data for batch insert
                    trade_data = []
                    for trade in self.portfolio.trades:
                        trade_data.append((
                            run_id,
                            trade['symbol_id'],
                            trade['entry_time'],
                            trade['entry_price'],
                            trade['entry_reason'],
                            trade['exit_time'],
                            trade['exit_price'],
                            trade['exit_reason'],
                            trade['direction'],
                            trade['quantity'],
                            trade['pnl'],
                            trade['pnl_pct'],
                            trade['stop_loss'],
                            trade['take_profit'],
                            0,  # atr_at_entry (simplified)
                            trade['market_state'],
                            trade['aggressive_flow_score'],
                            0,  # volume_ratio (simplified)
                            0,  # cvd_momentum (simplified)
                            trade['bars_in_trade'],
                            trade['duration_minutes'],
                            trade['mae'],
                            trade['mfe']
                        ))

                    # Batch insert trades
                    cur.executemany("""
                        INSERT INTO backtest_trades (
                            backtest_run_id, symbol_id, entry_time, entry_price, entry_reason,
                            exit_time, exit_price, exit_reason, direction, quantity,
                            pnl, pnl_pct, stop_loss, take_profit, atr_at_entry,
                            market_state, aggressive_flow_score, volume_ratio, cvd_momentum,
                            bars_in_trade, duration_minutes, mae, mfe
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s
                        )
                    """, trade_data)

                    logger.info(f"Saved {len(trade_data)} trades")

            # Save equity curve
            if self.portfolio.equity_curve:
                with self.conn.cursor() as cur:
                    equity_data = []
                    for point in self.portfolio.equity_curve:
                        equity_data.append((
                            run_id,
                            point['time'],
                            point['equity'],
                            point['cash'],
                            point['positions_value'],
                            point['open_positions']
                        ))

                    cur.executemany("""
                        INSERT INTO backtest_equity_curve (
                            backtest_run_id, time, equity, cash, positions_value, open_positions
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, equity_data)

                    logger.info(f"Saved {len(equity_data)} equity points")

            # Commit transaction
            self.conn.commit()

        except Exception as e:
            logger.error(f"Error saving results: {e}")
            self.conn.rollback()
            raise

    def analyze_constraints(self):
        """Analyze what constraints limited performance."""
        logger.info("")
        logger.info("🔍 Constraint Analysis:")

        total_signals = sum(self.portfolio.signals_generated.values())
        total_blocked = sum(self.portfolio.signals_blocked.values())

        if total_signals > 0:
            blocked_pct = (total_blocked / (total_signals + total_blocked)) * 100
            logger.info(f"  Signals Generated: {total_signals}")
            logger.info(f"  Signals Blocked: {total_blocked} ({blocked_pct:.1f}%)")

        # Analyze by symbol
        for symbol in self.portfolio.signals_generated.keys():
            generated = self.portfolio.signals_generated[symbol]
            blocked = self.portfolio.signals_blocked.get(symbol, 0)
            if generated > 0 or blocked > 0:
                logger.info(f"  {symbol}: {generated} signals, {blocked} blocked")

        # Recommend limits if needed
        if total_blocked > 0:
            max_positions_needed = len(self.portfolio.positions) + total_blocked
            logger.info(f"  💡 To capture all signals, you'd need:")
            logger.info(f"     Max Positions: {max_positions_needed} (currently {self.parameters.get('max_positions', 3)})")
            logger.info(f"     Initial Capital: ${self.portfolio.initial_capital * (max_positions_needed / max(1, len(self.portfolio.positions))):,.0f}")

    def generate_report(self) -> Dict:
        """Generate comprehensive backtest report."""
        stats = self.portfolio.get_summary_stats()
        version = self.version

        report = {
            'version_info': {
                'engine_version': version.engine_version,
                'strategy_version': version.strategy_version,
                'config_version': version.config_version,
                'timestamp': version.timestamp,
                'description': version.description
            },
            'parameters': self.parameters,
            'summary_stats': stats,
            'trades': self.portfolio.trades,
            'equity_curve': self.portfolio.equity_curve,
            'constraint_analysis': {
                'signals_generated': self.portfolio.signals_generated,
                'signals_blocked': self.portfolio.signals_blocked,
                'blocked_percentage': (sum(self.portfolio.signals_blocked.values()) /
                                     (sum(self.portfolio.signals_generated.values()) +
                                      sum(self.portfolio.signals_blocked.values()))) * 100
                if (sum(self.portfolio.signals_generated.values()) +
                    sum(self.portfolio.signals_blocked.values())) > 0 else 0
            }
        }

        return report

    def print_summary(self):
        """Print summary of backtest results."""
        stats = self.portfolio.get_summary_stats()

        logger.info("")
        logger.info("📊 Backtest Summary:")
        logger.info(f"  Total Trades: {stats['total_trades']}")
        logger.info(f"  Winning Trades: {stats['winning_trades']}")
        logger.info(f"  Losing Trades: {stats['losing_trades']}")
        logger.info(f"  Win Rate: {stats['win_rate']:.1f}%")
        logger.info(f"  Total P&L: ${stats['total_pnl']:,.2f}")
        logger.info(f"  Return: {stats['total_pnl_pct']:.2f}%")
        logger.info(f"  Avg Win: ${stats['avg_win']:.2f}")
        logger.info(f"  Avg Loss: ${stats['avg_loss']:.2f}")
        logger.info(f"  Largest Win: ${stats['largest_win']:.2f}")
        logger.info(f"  Largest Loss: ${stats['largest_loss']:.2f}")

        # Print constraint analysis
        self.analyze_constraints()

    def export_results(self, filename: str):
        """Export detailed results to file."""
        report = self.generate_report()

        import json
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Results exported to {filename}")

    def compare_with_baseline(self, baseline_stats: Dict) -> Dict:
        """Compare results with baseline performance."""
        current_stats = self.portfolio.get_summary_stats()

        comparison = {
            'win_rate_change': current_stats['win_rate'] - baseline_stats.get('win_rate', 0),
            'pnl_change': current_stats['total_pnl'] - baseline_stats.get('total_pnl', 0),
            'trade_count_change': current_stats['total_trades'] - baseline_stats.get('total_trades', 0),
            'improvement_areas': [],
            'regression_areas': []
        }

        # Analyze improvements/regressions
        if comparison['win_rate_change'] > 5:
            comparison['improvement_areas'].append(f"Win rate improved by {comparison['win_rate_change']:.1f}%")
        elif comparison['win_rate_change'] < -5:
            comparison['regression_areas'].append(f"Win rate declined by {abs(comparison['win_rate_change']):.1f}%")

        if comparison['pnl_change'] > 100:
            comparison['improvement_areas'].append(f"P&L improved by ${comparison['pnl_change']:.2f}")
        elif comparison['pnl_change'] < -100:
            comparison['regression_areas'].append(f"P&L declined by ${abs(comparison['pnl_change']):.2f}")

        return comparison

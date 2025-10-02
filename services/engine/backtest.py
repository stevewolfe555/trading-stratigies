#!/usr/bin/env python3
"""
Trading Strategy Backtest Engine - CLI Interface

Modular backtesting system with proper multi-stock portfolio simulation.
Supports individual stock testing, unlimited mode, and constraint analysis.

Usage:
    python backtest.py --symbols AAPL,MSFT --years 1
    python backtest.py --individual AAPL --years 0.5
    python backtest.py --unlimited AAPL,MSFT --years 1
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.backtest_config import BacktestConfig
from app.backtest_data import BacktestDataLoader
from app.backtest_position import BacktestPortfolio
from app.backtest_engine import BacktestEngine
from app.backtest_analysis import BacktestAnalyzer
from app.versions import bump_engine_version, get_version_info

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def parse_arguments():
    """Parse command line arguments."""
    import argparse

    parser = argparse.ArgumentParser(description='Trading Strategy Backtest Engine')
    
    # Symbol selection
    parser.add_argument('--symbols', type=str, help='Comma-separated list of symbols (e.g., AAPL,MSFT,GOOGL)')
    parser.add_argument('--all-symbols', action='store_true', help='Test all available symbols')

    # Time period
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')

    # Test modes
    parser.add_argument('--individual', type=str, help='Run individual test for single symbol')
    parser.add_argument('--unlimited', action='store_true', help='Run unlimited mode (no position/capital limits)')
    
    # Run ID (for UI integration)
    parser.add_argument('--run-id', type=int, help='Existing run ID to update (instead of creating new)')

    # Parameters
    parser.add_argument('--initial-capital', type=float, default=100000, help='Initial capital')
    parser.add_argument('--max-positions', type=int, default=3, help='Maximum positions')
    parser.add_argument('--risk-per-trade', type=float, default=1.0, help='Risk per trade (%)')
    # Output
    parser.add_argument('--export', type=str, help='Export results to JSON file')

    return parser.parse_args()


def get_available_symbols() -> List[str]:
    """Get list of available symbols from database."""
    try:
        config = BacktestConfig()
        with config.get_connection().cursor() as cur:
            cur.execute("SELECT symbol FROM symbols ORDER BY symbol")
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logging.error(f"Error getting symbols: {e}")
        return []


def calculate_date_range(years: float) -> tuple[datetime, datetime]:
    """Calculate start and end dates based on years."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(years * 365.25))
    return start_date, end_date


def run_portfolio_backtest(symbols: List[str], start_date: datetime, end_date: datetime, parameters: Dict):
    """Run standard portfolio backtest."""
    logging.info("🚀 Running portfolio backtest...")
    
    engine = BacktestEngine(parameters)
    run_id = parameters.get('run_id')
    engine.run_backtest(symbols, start_date, end_date, run_id=run_id)
    
    return engine.analyzer.generate_report()


def run_individual_backtest(symbol: str, start_date: datetime, end_date: datetime, parameters: Dict):
    """Run individual stock backtest."""
    logging.info(f"🔬 Running individual backtest for {symbol}...")
    
    # Create separate engine for individual test
    engine = BacktestEngine(parameters)
    
    # Load candles for single symbol
    data_loader = BacktestDataLoader(engine.config.get_connection())
    candles = data_loader.load_candles(symbol, start_date, end_date)
    
    if not candles:
        logging.error(f"No data found for {symbol}")
        return None
    
    # Create run record
    run_id = engine._create_run([symbol], start_date, end_date)
    
    # Process each bar
    for i, bar in enumerate(candles):
        if i >= 20:  # Need history for indicators
            engine.portfolio.update_positions({symbol: bar})
            engine.portfolio.check_stops_and_targets({symbol: bar})
            
            signal = engine.check_entry_signal(symbol, bar['symbol_id'], bar['time'])
            if signal:
                position_cost = engine._calculate_position_cost(signal, engine.portfolio.get_available_cash())
                if position_cost > 0:
                    engine.portfolio.signals_generated[symbol] = engine.portfolio.signals_generated.get(symbol, 0) + 1
                    
                    position = engine.portfolio.positions.get(symbol)
                    if not position:  # Only enter if no position
                        from app.backtest_position import Position
                        position = Position(
                            symbol=symbol,
                            symbol_id=bar['symbol_id'],
                            entry_time=bar['time'],
                            entry_price=signal['entry_price'],
                            quantity=int(position_cost / signal['entry_price']),
                            stop_loss=signal['stop_loss'],
                            take_profit=signal['take_profit'],
                            direction=signal['side'],
                            entry_reason=signal['reason']
                        )
                        
                        engine.portfolio.enter_position(position, position_cost)

        # Record equity periodically
        if i % 100 == 0:
            engine.portfolio.record_equity_point(bar['time'], {symbol: bar['close']})
    
    # Close position
    if symbol in engine.portfolio.positions:
        engine.portfolio.exit_position(symbol, candles[-1]['close'], candles[-1]['time'], 'End of Test')
    
    # Save and analyze
    engine.analyzer.save_results(run_id)
    engine.analyzer.print_summary()
    
    return engine.analyzer.generate_report()


def run_unlimited_backtest(symbols: List[str], start_date: datetime, end_date: datetime, parameters: Dict):
    """Run backtest without position or cash limits."""
    logging.info("🚀 Running unlimited backtest...")
    
    # Modify parameters to disable limits
    unlimited_params = parameters.copy()
    unlimited_params['test_mode'] = 'unlimited'
    
    engine = BacktestEngine(unlimited_params)
    run_id = unlimited_params.get('run_id')
    engine.run_backtest(symbols, start_date, end_date, run_id=run_id)
    
    return engine.analyzer.generate_report()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Get symbols
    if args.individual:
        symbols = [args.individual]
    elif args.all_symbols:
        symbols = get_available_symbols()
        logging.info(f"Testing all available symbols: {len(symbols)} symbols")
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]
    else:
        logging.error("Must specify --symbols, --individual, or --all-symbols")
        sys.exit(1)
    
    # Get date range
    if args.start_date and args.end_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    elif args.years:
        start_date, end_date = calculate_date_range(args.years)
    else:
        logging.error("Must specify --years or both --start-date and --end-date")
        sys.exit(1)
    
    # Prepare parameters
    parameters = {
        'initial_capital': args.initial_capital,
        'max_positions': args.max_positions,
        'risk_per_trade_pct': args.risk_per_trade,
        'min_aggression_score': 70,
        'atr_stop_multiplier': 1.5,
        'atr_target_multiplier': 3.0,
        'test_mode': 'unlimited' if args.unlimited else 'portfolio',
        'enable_position_limits': not args.unlimited,
        'enable_cash_limits': not args.unlimited,
        'run_id': args.run_id if hasattr(args, 'run_id') and args.run_id else None
    }
    
    # Log version info
    version = get_version_info()
    logging.info(f"Backtest Engine v{version.engine_version}")
    logging.info(f"Strategy v{version.strategy_version}")
    logging.info("")
    
    try:
        # Run appropriate backtest
        if args.individual:
            report = run_individual_backtest(symbols[0], start_date, end_date, parameters)
        elif args.unlimited:
            report = run_unlimited_backtest(symbols, start_date, end_date, parameters)
        else:
            report = run_portfolio_backtest(symbols, start_date, end_date, parameters)
        
        # Export if requested
        if args.export and report:
            import json
            with open(args.export, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            logging.info(f"Results exported to {args.export}")
            
    except KeyboardInterrupt:
        logging.info("Backtest interrupted by user")
    except Exception as e:
        logging.error(f"Backtest failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

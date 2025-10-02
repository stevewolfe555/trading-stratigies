"""
Automated Trading Strategy

Simple strategy based on Market State + Aggressive Flow confirmation.

Entry Rules:
- Market state is IMBALANCE (up or down)
- Aggressive flow score > 70
- Direction matches market state

Exit Rules:
- 2% stop loss
- 4% take profit (2:1 R:R)
- Or opposite signal

Position Sizing:
- 1% risk per trade
- Max 1 position at a time
"""

from __future__ import annotations
import psycopg2
from typing import Optional, Dict
from loguru import logger
from .alpaca_client import AlpacaTradingClient
from .position_manager import PositionManager
from .atr_calculator import get_atr_based_levels
from ..strategy_manager import StrategyManager
from ..strategies.auction_market_strategy import AuctionMarketStrategy


class AutoTradingStrategy:
    """
    Automated trading strategy using market state and aggressive flow.
    
    Now uses database-backed configuration via StrategyManager.
    """
    
    def __init__(self, db_conn, alpaca_client: AlpacaTradingClient, position_manager: PositionManager):
        self.conn = db_conn
        self.client = alpaca_client
        self.position_manager = position_manager
        self.strategy_manager = StrategyManager(db_conn)
        
        # Load initial configs
        self.strategy_manager.load_all_configs()
        
        # Strategy name
        self.strategy_name = 'auction_market'
        
        # Fallback to env vars if database config not available
        import os
        self.default_min_aggression = int(os.getenv("MIN_AGGRESSION_SCORE", "70"))
        self.default_stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "2.0"))
        self.default_take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "4.0"))
        self.enabled = True  # Master switch
        
        # Initialize shared strategy (will be updated per symbol)
        self.strategy = None
    
    def is_enabled_for_symbol(self, symbol: str) -> bool:
        """
        Check if strategy is enabled for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if enabled
        """
        return self.strategy_manager.is_strategy_enabled(symbol, self.strategy_name)
    
    def get_parameter(self, symbol: str, param_name: str, default=None):
        """
        Get strategy parameter for a symbol.
        
        Args:
            symbol: Stock symbol
            param_name: Parameter name
            default: Default value
            
        Returns:
            Parameter value
        """
        return self.strategy_manager.get_strategy_parameter(
            symbol, self.strategy_name, param_name, default
        )
    
    def evaluate_entry_signal(self, symbol_id: int, symbol: str) -> Optional[Dict]:
        """
        Evaluate if we should enter a trade.
        
        Uses shared AuctionMarketStrategy for evaluation logic.
        
        Returns:
            Signal dict if entry conditions met, None otherwise
        """
        try:
            # Check if strategy is enabled for this symbol
            if not self.is_enabled_for_symbol(symbol):
                return None
            
            # Get symbol-specific parameters (or use defaults)
            min_aggression = self.get_parameter(symbol, 'min_aggression_score', self.default_min_aggression)
            atr_stop_mult = self.get_parameter(symbol, 'atr_stop_multiplier', 1.5)
            atr_target_mult = self.get_parameter(symbol, 'atr_target_multiplier', 3.0)
            
            # Initialize strategy with symbol-specific parameters
            self.strategy = AuctionMarketStrategy({
                'min_aggression_score': min_aggression,
                'atr_stop_multiplier': atr_stop_mult,
                'atr_target_multiplier': atr_target_mult
            })
            
            # Get current price
            cur = self.conn.cursor()
            cur.execute("""
                SELECT close FROM candles 
                WHERE symbol_id = %s 
                ORDER BY time DESC 
                LIMIT 1
            """, (symbol_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            current_price = float(row[0])
            
            # Get market state
            cur.execute("""
                SELECT state, confidence 
                FROM market_state 
                WHERE symbol_id = %s 
                ORDER BY time DESC 
                LIMIT 1
            """, (symbol_id,))
            
            state_row = cur.fetchone()
            if not state_row:
                return None
            
            market_state = state_row[0]
            confidence = int(state_row[1])
            
            # Get aggressive flow (last 5 buckets)
            cur.execute("""
                SELECT cumulative_delta, buy_pressure, sell_pressure
                FROM order_flow 
                WHERE symbol_id = %s 
                ORDER BY bucket DESC 
                LIMIT 5
            """, (symbol_id,))
            
            flow_rows = cur.fetchall()
            if not flow_rows:
                return None
            
            # Extract flow metrics
            current_flow = flow_rows[0]
            buy_pressure = float(current_flow[1])
            sell_pressure = float(current_flow[2])
            
            # CVD momentum
            if len(flow_rows) >= 2:
                cvd_start = int(flow_rows[-1][0])
                cvd_end = int(flow_rows[0][0])
                cvd_momentum = cvd_end - cvd_start
            else:
                cvd_momentum = 0
            
            # Get ATR
            cur.execute("""
                SELECT atr FROM candles 
                WHERE symbol_id = %s 
                ORDER BY time DESC 
                LIMIT 1
            """, (symbol_id,))
            
            atr_row = cur.fetchone()
            if not atr_row or not atr_row[0]:
                # Fallback: calculate ATR from get_atr_based_levels
                _, _ = get_atr_based_levels(self.conn, symbol_id, current_price, 'buy')
                atr = 1.0  # Fallback value
            else:
                atr = float(atr_row[0])
            
            # Use shared strategy to evaluate entry signal
            signal = self.strategy.evaluate_entry_signal(
                market_state=market_state,
                confidence=confidence,
                buy_pressure=buy_pressure,
                sell_pressure=sell_pressure,
                cvd_momentum=cvd_momentum,
                current_price=current_price,
                atr=atr,
                symbol=symbol
            )
            
            # Log evaluation
            if signal:
                logger.bind(module="AUTO-TRADE").info(
                    f"🎯 ENTRY SIGNAL: {symbol} - {signal['reason']}"
                )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error evaluating entry signal for {symbol}: {e}")
            return None
    
    def execute_trade(self, signal: Dict) -> bool:
        """
        Execute a trade based on signal.
        
        Returns:
            True if trade executed successfully
        """
        try:
            symbol = signal['symbol']
            side = signal['side']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            take_profit = signal['take_profit']
            
            # Check if we can trade
            can_trade, reason = self.position_manager.can_open_position(symbol)
            if not can_trade:
                logger.warning(f"Cannot trade {symbol}: {reason}")
                return False
            
            # Calculate position size
            qty = self.position_manager.calculate_position_size(
                symbol, entry_price, stop_loss
            )
            
            if qty == 0:
                logger.warning(f"Position size is 0 for {symbol}")
                return False
            
            # Place bracket order (entry + stop loss + take profit)
            logger.info(
                f"🚀 EXECUTING TRADE: {side.upper()} {qty} {symbol} @ ${entry_price:.2f} "
                f"(SL: ${stop_loss:.2f}, TP: ${take_profit:.2f})"
            )
            logger.info(f"Reason: {signal['reason']}")
            
            order = self.client.place_bracket_order(
                symbol=symbol,
                qty=qty,
                side=side,
                take_profit_price=take_profit,
                stop_loss_price=stop_loss
            )
            
            if order:
                # Log trade
                self.position_manager.log_trade(
                    symbol=symbol,
                    action=side.upper(),
                    qty=qty,
                    price=entry_price,
                    order_id=order.get('id'),
                    reason=signal['reason']
                )
                
                logger.info(f"✅ Trade executed successfully! Order ID: {order.get('id')}")
                return True
            else:
                logger.error(f"❌ Failed to execute trade for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return False
    
    def check_and_execute(self, symbol_id: int, symbol: str):
        """
        Check for entry signals and execute if conditions met.
        """
        if not self.enabled:
            return
        
        try:
            # Check if we already have a position
            position = self.client.get_position(symbol)
            if position:
                logger.debug(f"Already have position in {symbol}, skipping")
                return
            
            # Evaluate entry signal
            signal = self.evaluate_entry_signal(symbol_id, symbol)
            
            if signal:
                logger.info(f"🎯 ENTRY SIGNAL DETECTED: {signal['symbol']} - {signal['reason']}")
                
                # Execute trade
                self.execute_trade(signal)
            
        except Exception as e:
            logger.error(f"Error in check_and_execute for {symbol}: {e}")


def run_auto_trading(db_conn):
    """
    Main function to run automated trading.
    Called periodically by the engine service.
    """
    try:
        # Initialize clients
        alpaca_client = AlpacaTradingClient(paper=True)
        position_manager = PositionManager(db_conn, alpaca_client)
        strategy = AutoTradingStrategy(db_conn, alpaca_client, position_manager)
        
        # Get all active symbols
        cur = db_conn.cursor()
        cur.execute("SELECT id, symbol FROM symbols")
        symbols = cur.fetchall()
        
        for symbol_id, symbol_name in symbols:
            strategy.check_and_execute(symbol_id, symbol_name)
            
    except Exception as e:
        logger.error(f"Error in auto trading: {e}")

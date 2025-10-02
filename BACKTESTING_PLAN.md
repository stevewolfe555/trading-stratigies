# Backtesting & Optimization Plan

**Last Updated**: 2025-10-02  
**Status**: 🎯 NEXT PHASE  
**Priority**: HIGH  
**Timeline**: 1-2 weeks

Validate and optimize the Auction Market trading strategy  
**Data Source**: Alpaca SIP feed (7 years historical data available)  
**Timeline**: 1-2 weeks

---
## 📊 Current System Status

### ✅ What We Have
- **Live trading system** - Automated execution on Alpaca paper account
- **Strategy logic** - Market state + aggressive flow + ATR-based targets
- **Database schema** - TimescaleDB with candles, signals, market_state tables
- **Risk management** - Position sizing, stop-loss, take-profit
- **30 stocks monitored** - Mag 7 + Tech/Finance/Healthcare/Energy/ETFs

### ❌ What We Need
- **Historical data loader** - Import 2-7 years of 1-min bars
- **Backtest engine** - Simulate strategy on historical data
- **Performance metrics** - Win rate, profit factor, Sharpe ratio, drawdown
- **Parameter optimization** - Find optimal thresholds
- **Reporting** - Equity curves, trade lists, monthly returns

---

## 🎯 Phase 1: Historical Data Import (4-6 hours)

### Component 1.1: Alpaca Historical Data Loader

**File**: `services/backtest/historical_loader.py`

**What it does:**
- Connects to Alpaca SIP feed (requires paid subscription)
- Downloads 1-minute bars for all 30 stocks
- Stores in existing `candles` table
- Handles date ranges and pagination

**Implementation:**
```python
class AlpacaHistoricalLoader:
    """
    Load historical data from Alpaca SIP feed.
    
    Alpaca SIP provides:
    - 1-minute bars
    - Up to 7 years of history
    - All US stocks
    - Included with paid subscription
    """
    
    def load_historical_data(
        self,
        symbol: str,
        start_date: str,  # 'YYYY-MM-DD'
        end_date: str,
        timeframe: str = '1Min'
    ):
        """
        Download and store historical candles.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date
            end_date: End date
            timeframe: Bar size (1Min, 5Min, etc.)
        """
        # Use Alpaca API to fetch bars
        # Insert into candles table
        # Handle duplicates (ON CONFLICT DO NOTHING)
        # Show progress bar
```

**Usage:**
```bash
# Load 2 years of data for all 30 stocks
docker compose run --rm backtest python3 load_historical.py \
  --start-date 2023-01-01 \
  --end-date 2025-01-01 \
  --symbols AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD,NFLX,INTC,CSCO,ORCL,CRM,ADBE,AVGO,JPM,BAC,WFC,GS,MS,JNJ,UNH,PFE,ABBV,MRK,XOM,CVX,SPY,QQQ,DIA
```

**Deliverables:**
- [ ] Python script to download data
- [ ] Progress tracking and logging
- [ ] Error handling and retries
- [ ] Data validation (check for gaps)

---

### Component 1.2: Data Quality Checker

**File**: `services/backtest/data_validator.py`

**What it does:**
- Verifies data completeness
- Checks for gaps in timestamps
- Validates OHLCV data integrity
- Reports statistics

**Implementation:**
```python
def validate_historical_data(symbol: str, start_date: str, end_date: str):
    """
    Check data quality.
    
    Checks:
    - No missing days (except weekends/holidays)
    - No missing minutes during market hours
    - OHLC relationships valid (H >= O,C,L)
    - Volume > 0
    """
    # Query database
    # Check for gaps
    # Validate relationships
    # Return report
```

**Deliverables:**
- [ ] Data validation script
- [ ] Gap detection
- [ ] Quality report generation

---

## 🚀 Phase 2: Backtest Engine (8-12 hours)

### Component 2.1: Core Backtest Engine

**File**: `services/backtest/engine.py`

**What it does:**
- Loops through historical candles chronologically
- Runs existing strategy logic (market state, aggressive flow, ATR)
- Simulates trades with realistic slippage/commissions
- Tracks positions and P&L

**Implementation:**
```python
class BacktestEngine:
    """
    Simulate trading strategy on historical data.
    """
    
    def __init__(self, db_conn, start_date, end_date, symbols, initial_capital=100000):
        self.conn = db_conn
        self.start_date = start_date
        self.end_date = end_date
        self.symbols = symbols
        self.capital = initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        
    def run(self):
        """
        Main backtest loop.
        
        For each minute:
        1. Update market data
        2. Calculate indicators (market state, aggressive flow, ATR)
        3. Evaluate strategy signals
        4. Execute trades (if conditions met)
        5. Update positions and P&L
        6. Record equity
        """
        # Get all candles in date range
        candles = self.load_candles()
        
        for candle in candles:
            # Update current price
            self.update_market_data(candle)
            
            # Calculate indicators
            market_state = self.detect_market_state(candle.symbol_id)
            aggression = self.calculate_aggressive_flow(candle.symbol_id)
            
            # Check for signals
            signal = self.evaluate_strategy(candle.symbol_id, market_state, aggression)
            
            if signal:
                # Execute trade
                self.execute_trade(signal, candle)
            
            # Update open positions
            self.update_positions(candle)
            
            # Record equity
            self.record_equity(candle.time)
        
        return self.generate_report()
```

**Key Features:**
- **Realistic execution** - Market orders with slippage
- **Bracket orders** - Stop-loss and take-profit simulation
- **Position management** - Max positions, risk limits
- **Commission modeling** - Alpaca commission structure
- **Slippage modeling** - 0.01-0.05% per trade

**Deliverables:**
- [ ] Core backtest engine
- [ ] Trade execution simulator
- [ ] Position tracking
- [ ] Equity curve generation

---

### Component 2.2: Strategy Integration

**File**: `services/backtest/strategy_runner.py`

**What it does:**
- Uses existing strategy logic from `services/engine/app/trading/auto_strategy.py`
- Runs market state detection
- Runs aggressive flow calculation
- Generates signals exactly as live system does

**Implementation:**
```python
class BacktestStrategyRunner:
    """
    Run live strategy logic in backtest mode.
    """
    
    def __init__(self, db_conn):
        self.conn = db_conn
        # Import existing components
        from app.detectors.market_state import detect_market_state
        from app.indicators.aggressive_flow import calculate_aggressive_flow
        from app.trading.atr_calculator import get_atr_based_levels
        
    def evaluate_signal(self, symbol_id, current_time):
        """
        Use exact same logic as live trading.
        """
        # Run market state detection
        market_state = detect_market_state(self.conn, symbol_id, current_time)
        
        # Run aggressive flow
        aggression = calculate_aggressive_flow(self.conn, symbol_id, current_time)
        
        # Check entry conditions
        if market_state in ['IMBALANCE_UP', 'IMBALANCE_DOWN']:
            if aggression['score'] >= 70:
                # Generate signal
                return self.create_signal(symbol_id, market_state, aggression)
        
        return None
```

**Deliverables:**
- [ ] Strategy integration layer
- [ ] Indicator calculation in backtest mode
- [ ] Signal generation matching live system

---

## 📈 Phase 3: Performance Metrics (4-6 hours)

### Component 3.1: Metrics Calculator

**File**: `services/backtest/metrics.py`

**What it does:**
- Calculates comprehensive performance statistics
- Generates equity curves
- Analyzes trade distribution
- Computes risk-adjusted returns

**Implementation:**
```python
class PerformanceMetrics:
    """
    Calculate strategy performance metrics.
    """
    
    def calculate_all_metrics(self, trades, equity_curve, initial_capital):
        """
        Comprehensive performance analysis.
        
        Returns:
            dict with all metrics
        """
        return {
            # Basic metrics
            'total_trades': len(trades),
            'winning_trades': len([t for t in trades if t['pnl'] > 0]),
            'losing_trades': len([t for t in trades if t['pnl'] < 0]),
            'win_rate': self.calculate_win_rate(trades),
            
            # P&L metrics
            'total_pnl': sum(t['pnl'] for t in trades),
            'total_return_pct': self.calculate_total_return(equity_curve, initial_capital),
            'average_win': self.calculate_average_win(trades),
            'average_loss': self.calculate_average_loss(trades),
            'largest_win': max(t['pnl'] for t in trades),
            'largest_loss': min(t['pnl'] for t in trades),
            
            # Risk metrics
            'profit_factor': self.calculate_profit_factor(trades),
            'sharpe_ratio': self.calculate_sharpe_ratio(equity_curve),
            'sortino_ratio': self.calculate_sortino_ratio(equity_curve),
            'max_drawdown': self.calculate_max_drawdown(equity_curve),
            'max_drawdown_pct': self.calculate_max_drawdown_pct(equity_curve),
            
            # Trade analysis
            'avg_trade_duration': self.calculate_avg_duration(trades),
            'avg_bars_in_trade': self.calculate_avg_bars(trades),
            'expectancy': self.calculate_expectancy(trades),
            
            # Risk-reward
            'avg_risk_reward': self.calculate_avg_rr(trades),
            'best_rr': max(t['risk_reward'] for t in trades),
            'worst_rr': min(t['risk_reward'] for t in trades),
        }
```

**Key Metrics:**

1. **Win Rate** - % of winning trades
2. **Profit Factor** - Gross profit / Gross loss
3. **Sharpe Ratio** - Risk-adjusted returns
4. **Max Drawdown** - Largest peak-to-trough decline
5. **Expectancy** - Average $ per trade
6. **Average R:R** - Average risk:reward ratio

**Deliverables:**
- [ ] Metrics calculation functions
- [ ] Statistical analysis
- [ ] Risk-adjusted return calculations

---

### Component 3.2: Report Generator

**File**: `services/backtest/reporter.py`

**What it does:**
- Generates HTML/PDF reports
- Creates equity curve charts
- Shows trade distribution
- Displays monthly returns

**Implementation:**
```python
class BacktestReporter:
    """
    Generate backtest reports.
    """
    
    def generate_report(self, results, output_path='backtest_report.html'):
        """
        Create comprehensive HTML report.
        
        Includes:
        - Summary statistics
        - Equity curve chart
        - Drawdown chart
        - Monthly returns table
        - Trade list
        - Parameter settings
        """
        # Generate HTML with charts
        # Use matplotlib for charts
        # Export to HTML/PDF
```

**Report Sections:**
1. **Summary** - Key metrics at a glance
2. **Equity Curve** - Portfolio value over time
3. **Drawdown Chart** - Underwater equity curve
4. **Monthly Returns** - Calendar heatmap
5. **Trade List** - All trades with details
6. **Parameter Settings** - Strategy configuration

**Deliverables:**
- [ ] HTML report generator
- [ ] Chart creation (matplotlib)
- [ ] Trade list export (CSV)
- [ ] Summary statistics table

---

## 🔧 Phase 4: Parameter Optimization (6-8 hours)

### Component 4.1: Grid Search Optimizer

**File**: `services/backtest/optimizer.py`

**What it does:**
- Tests multiple parameter combinations
- Finds optimal settings
- Prevents overfitting with walk-forward analysis

**Implementation:**
```python
class ParameterOptimizer:
    """
    Find optimal strategy parameters.
    """
    
    def grid_search(self, parameter_ranges):
        """
        Test all parameter combinations.
        
        Parameters to optimize:
        - min_aggression_score: [50, 60, 70, 80]
        - atr_stop_multiplier: [1.0, 1.5, 2.0]
        - atr_target_multiplier: [2.0, 3.0, 4.0]
        - risk_per_trade_pct: [0.5, 1.0, 1.5, 2.0]
        """
        results = []
        
        for aggression in [50, 60, 70, 80]:
            for stop_mult in [1.0, 1.5, 2.0]:
                for target_mult in [2.0, 3.0, 4.0]:
                    # Run backtest with these parameters
                    result = self.run_backtest_with_params(
                        aggression, stop_mult, target_mult
                    )
                    results.append(result)
        
        # Find best combination
        best = max(results, key=lambda x: x['sharpe_ratio'])
        return best
```

**Optimization Criteria:**
- **Primary**: Sharpe Ratio (risk-adjusted returns)
- **Secondary**: Profit Factor
- **Constraint**: Max Drawdown < 20%
- **Constraint**: Win Rate > 45%

**Deliverables:**
- [ ] Grid search implementation
- [ ] Parameter testing framework
- [ ] Results comparison
- [ ] Best parameters identification

---

### Component 4.2: Walk-Forward Analysis

**File**: `services/backtest/walk_forward.py`

**What it does:**
- Validates parameters don't overfit
- Tests on out-of-sample data
- Simulates real-world parameter selection

**Implementation:**
```python
class WalkForwardAnalyzer:
    """
    Walk-forward optimization to prevent overfitting.
    
    Process:
    1. Split data into windows (e.g., 6 months each)
    2. Optimize on first window (in-sample)
    3. Test on second window (out-of-sample)
    4. Roll forward and repeat
    5. Compare in-sample vs out-of-sample performance
    """
    
    def run_walk_forward(self, window_size_months=6):
        """
        Run walk-forward analysis.
        """
        # Split data into windows
        # Optimize on each in-sample period
        # Test on following out-of-sample period
        # Compare performance
```

**Deliverables:**
- [ ] Walk-forward implementation
- [ ] In-sample vs out-of-sample comparison
- [ ] Overfitting detection

---

## 📅 Implementation Timeline

### Week 1: Data & Engine (Days 1-5)

**Day 1-2: Historical Data Import**
- [ ] Create Alpaca historical loader
- [ ] Download 2 years of data for 30 stocks
- [ ] Validate data quality
- [ ] Store in database

**Day 3-4: Backtest Engine**
- [ ] Build core backtest loop
- [ ] Integrate strategy logic
- [ ] Implement trade execution simulator
- [ ] Test with small dataset

**Day 5: Testing & Debugging**
- [ ] Run first full backtest
- [ ] Debug issues
- [ ] Verify results make sense

### Week 2: Metrics & Optimization (Days 6-10)

**Day 6-7: Performance Metrics**
- [ ] Implement metrics calculator
- [ ] Generate equity curves
- [ ] Create HTML reports
- [ ] Export trade lists

**Day 8-9: Parameter Optimization**
- [ ] Grid search implementation
- [ ] Test parameter combinations
- [ ] Find optimal settings
- [ ] Walk-forward validation

**Day 10: Final Report & Documentation**
- [ ] Generate comprehensive report
- [ ] Document findings
- [ ] Update strategy parameters
- [ ] Prepare for live trading

---

## 💰 Data Requirements & Costs

### Alpaca SIP Feed Subscription

**What you get:**
- Real-time market data (Level 1)
- Historical data (up to 7 years)
- 1-minute bars
- All US stocks
- Unlimited API calls

**Cost:** ~$9-49/month depending on plan

**Recommendation:** Start with 2 years, expand to 7 if needed

### Data Volume Estimates

**2 years of 1-min data for 30 stocks:**
- ~250 trading days/year × 2 years = 500 days
- ~390 minutes/day × 500 days = 195,000 minutes
- 195,000 minutes × 30 stocks = 5,850,000 candles
- Storage: ~500 MB compressed

**7 years of data:**
- ~20,475,000 candles
- Storage: ~1.5 GB compressed

---

## 🎯 Success Criteria

### Minimum Viable Strategy
- **Win Rate**: > 45%
- **Profit Factor**: > 1.5
- **Sharpe Ratio**: > 1.0
- **Max Drawdown**: < 20%
- **Average R:R**: > 1.5:1

### Excellent Strategy
- **Win Rate**: > 55%
- **Profit Factor**: > 2.0
- **Sharpe Ratio**: > 2.0
- **Max Drawdown**: < 15%
- **Average R:R**: > 2:1

### Red Flags (Don't Trade Live)
- Win Rate < 40%
- Profit Factor < 1.2
- Max Drawdown > 30%
- Sharpe Ratio < 0.5
- Large gap between in-sample and out-of-sample

---

## 📊 Expected Deliverables

### Code
- [ ] Historical data loader
- [ ] Backtest engine
- [ ] Metrics calculator
- [ ] Report generator
- [ ] Parameter optimizer
- [ ] Walk-forward analyzer

### Reports
- [ ] 2-year backtest report (all 30 stocks)
- [ ] Parameter optimization results
- [ ] Walk-forward validation report
- [ ] Trade list (CSV)
- [ ] Equity curve charts
- [ ] Monthly returns table

### Documentation
- [ ] Backtest methodology
- [ ] Parameter selection rationale
- [ ] Performance analysis
- [ ] Risk assessment
- [ ] Recommendations for live trading

---

## 🚀 Getting Started

### Step 1: Subscribe to Alpaca SIP Feed
1. Go to https://alpaca.markets/data
2. Subscribe to appropriate plan
3. Update API keys in `.env`

### Step 2: Create Backtest Service
```bash
# Create new Docker service
mkdir -p services/backtest
cd services/backtest

# Create structure
mkdir -p app/{loaders,engine,metrics,reports,optimizers}
touch app/__init__.py
touch app/loaders/__init__.py
touch app/engine/__init__.py
touch app/metrics/__init__.py
touch app/reports/__init__.py
touch app/optimizers/__init__.py
```

### Step 3: Add to Docker Compose
```yaml
# Add to docker-compose.yml
backtest:
  build: ./services/backtest
  depends_on:
    - db
  environment:
    - ALPACA_API_KEY=${ALPACA_API_KEY}
    - ALPACA_SECRET_KEY=${ALPACA_SECRET_KEY}
  volumes:
    - ./services/backtest:/app
    - ./backtest_results:/results
```

### Step 4: Run First Backtest
```bash
# Load historical data
docker compose run --rm backtest python3 load_historical.py \
  --start-date 2023-01-01 \
  --end-date 2025-01-01 \
  --symbols AAPL,MSFT,GOOGL

# Run backtest
docker compose run --rm backtest python3 run_backtest.py \
  --start-date 2023-01-01 \
  --end-date 2025-01-01 \
  --symbols AAPL,MSFT,GOOGL \
  --output /results/backtest_report.html
```

---

## ✅ Summary

**Total Time**: 10-15 hours of development  
**Total Cost**: $9-49/month for Alpaca SIP feed  
**Expected Outcome**: Validated strategy with optimal parameters  

**After completion, you'll know:**
- ✅ If the strategy is profitable
- ✅ Optimal aggression threshold
- ✅ Best ATR multipliers
- ✅ Expected win rate and profit factor
- ✅ Maximum drawdown to expect
- ✅ If it's ready for live trading

**Ready to start building!** 🚀

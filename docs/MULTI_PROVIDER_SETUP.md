# Multi-Provider Data Architecture

**Created**: 2025-10-01 22:42 (UTC+3)  
**Goal**: Route different markets to different data providers  
**Use Case**: IG for LSE/European markets, Alpaca for US markets

---

## 🎯 Provider Capabilities

### Alpaca (Current - US Markets)
**What you get:**
- ✅ US stocks (NYSE, NASDAQ)
- ✅ Real-time Level 1 data
- ✅ Historical data (7 years with SIP)
- ✅ Free paper trading
- ❌ No Level 2 data
- ❌ No LSE/European markets

**Best for:** US stocks (AAPL, MSFT, GOOGL, etc.)

---

### IG Markets (New - UK/European Markets)
**What you get:**
- ✅ LSE (London Stock Exchange)
- ✅ European markets (DAX, CAC, etc.)
- ✅ Level 1 data (bid, ask, last)
- ✅ Level 2 data (order book depth!)
- ✅ Forex, commodities, indices
- ✅ Free with demo account
- ⚠️ Share price info limited
- ⚠️ Rate limits apply

**Best for:** UK/European stocks, forex, indices

**API Docs:** https://labs.ig.com/rest-trading-api-reference

---

## 🏗️ Architecture Design

### Current (Single Provider)
```
Alpaca WebSocket
  ↓
Ingestion Service
  ↓
Database (all symbols)
```

### New (Multi-Provider Router)
```
┌─────────────────┐     ┌─────────────────┐
│ Alpaca WS       │     │ IG REST/Stream  │
│ (US Markets)    │     │ (UK/EU Markets) │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────┬───────────────┘
                 ↓
         ┌──────────────┐
         │ Data Router  │
         │ (by market)  │
         └──────┬───────┘
                ↓
         ┌──────────────┐
         │ Ingestion    │
         │ Service      │
         └──────┬───────┘
                ↓
         ┌──────────────┐
         │ Database     │
         │ (all markets)│
         └──────────────┘
```

---

## 📋 Implementation Plan

### Phase 1: IG Provider Integration (4-6 hours)

#### Component 1.1: IG API Client

**File**: `services/ingestion/app/providers/ig_client.py`

**What it does:**
- Connects to IG REST API
- Authenticates with API key
- Fetches Level 1 & Level 2 data
- Streams real-time updates

**Implementation:**
```python
class IGProvider:
    """
    IG Markets data provider.
    
    Supports:
    - LSE stocks
    - European indices
    - Forex pairs
    - Level 1 & Level 2 data
    """
    
    def __init__(self, api_key, username, password, demo=True):
        self.api_key = api_key
        self.username = username
        self.password = password
        self.base_url = 'https://demo-api.ig.com/gateway/deal' if demo else 'https://api.ig.com/gateway/deal'
        self.session_token = None
        self.cst_token = None
        
    def authenticate(self):
        """
        Authenticate with IG API.
        
        Returns session tokens for subsequent requests.
        """
        headers = {
            'X-IG-API-KEY': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json; charset=UTF-8',
            'Version': '2'
        }
        
        payload = {
            'identifier': self.username,
            'password': self.password
        }
        
        response = requests.post(
            f'{self.base_url}/session',
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            self.cst_token = response.headers['CST']
            self.session_token = response.headers['X-SECURITY-TOKEN']
            return True
        return False
    
    def get_market_details(self, epic):
        """
        Get market details for a symbol.
        
        Args:
            epic: IG market identifier (e.g., 'IX.D.FTSE.DAILY.IP' for FTSE 100)
        
        Returns:
            Market details including bid, ask, last price
        """
        headers = {
            'X-IG-API-KEY': self.api_key,
            'CST': self.cst_token,
            'X-SECURITY-TOKEN': self.session_token,
            'Version': '3'
        }
        
        response = requests.get(
            f'{self.base_url}/markets/{epic}',
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'symbol': epic,
                'bid': data['snapshot']['bid'],
                'ask': data['snapshot']['offer'],
                'last': data['snapshot']['lastTradedPrice'],
                'volume': data['snapshot']['volume'],
                'timestamp': data['snapshot']['updateTime']
            }
        return None
    
    def get_level2_data(self, epic):
        """
        Get Level 2 order book data.
        
        Returns:
            Order book with bid/ask depth
        """
        headers = {
            'X-IG-API-KEY': self.api_key,
            'CST': self.cst_token,
            'X-SECURITY-TOKEN': self.session_token,
            'Version': '1'
        }
        
        response = requests.get(
            f'{self.base_url}/marketdepth/{epic}',
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'bids': data['bids'],  # List of {price, size}
                'asks': data['asks'],  # List of {price, size}
                'timestamp': data['timestamp']
            }
        return None
    
    def stream_prices(self, epics, callback):
        """
        Stream real-time price updates.
        
        Uses Lightstreamer protocol (IG's streaming API).
        """
        # IG uses Lightstreamer for streaming
        # This requires a separate library
        from lightstreamer_client import LightstreamerClient
        
        # Connect to IG streaming endpoint
        # Subscribe to price updates
        # Call callback on each update
```

**Deliverables:**
- [ ] IG authentication
- [ ] Level 1 data fetching
- [ ] Level 2 order book
- [ ] Real-time streaming

---

#### Component 1.2: Provider Router

**File**: `services/ingestion/app/router.py`

**What it does:**
- Routes symbols to correct provider
- Configurable via database or config file
- Handles multiple providers simultaneously

**Implementation:**
```python
class ProviderRouter:
    """
    Route symbols to appropriate data providers.
    
    Configuration example:
    {
        "AAPL": "alpaca",
        "MSFT": "alpaca",
        "VOD.L": "ig",  # Vodafone on LSE
        "BP.L": "ig",   # BP on LSE
        "^FTSE": "ig"   # FTSE 100 index
    }
    """
    
    def __init__(self, db_conn):
        self.conn = db_conn
        self.providers = {}
        self.symbol_routing = {}
        
    def register_provider(self, name, provider_instance):
        """
        Register a data provider.
        
        Args:
            name: Provider name ('alpaca', 'ig', etc.)
            provider_instance: Provider object
        """
        self.providers[name] = provider_instance
        
    def load_routing_config(self):
        """
        Load symbol routing from database.
        
        Table: symbol_providers
        Columns: symbol, provider, market, level
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT symbol, provider, market, level
            FROM symbol_providers
        """)
        
        for row in cur.fetchall():
            self.symbol_routing[row[0]] = {
                'provider': row[1],
                'market': row[2],
                'level': row[3]
            }
    
    def get_provider_for_symbol(self, symbol):
        """
        Get the provider for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Provider instance
        """
        if symbol in self.symbol_routing:
            provider_name = self.symbol_routing[symbol]['provider']
            return self.providers.get(provider_name)
        
        # Default to Alpaca for US symbols
        if '.' not in symbol:  # US symbols don't have suffix
            return self.providers.get('alpaca')
        
        # LSE symbols end in .L
        if symbol.endswith('.L'):
            return self.providers.get('ig')
        
        return None
    
    def fetch_data(self, symbol):
        """
        Fetch data for a symbol using correct provider.
        """
        provider = self.get_provider_for_symbol(symbol)
        if provider:
            return provider.get_market_data(symbol)
        return None
```

**Deliverables:**
- [ ] Provider registration
- [ ] Symbol routing logic
- [ ] Database configuration
- [ ] Multi-provider support

---

### Phase 2: Database Schema Updates (1-2 hours)

#### New Tables

**Table: `symbol_providers`**
```sql
CREATE TABLE symbol_providers (
    symbol VARCHAR(20) PRIMARY KEY,
    provider VARCHAR(20) NOT NULL,  -- 'alpaca', 'ig', etc.
    market VARCHAR(10) NOT NULL,    -- 'NYSE', 'LSE', 'DAX', etc.
    level INT NOT NULL,             -- 1 or 2 (data level)
    epic VARCHAR(50),               -- IG-specific market ID
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Example data
INSERT INTO symbol_providers VALUES
    ('AAPL', 'alpaca', 'NASDAQ', 1, NULL, true),
    ('MSFT', 'alpaca', 'NASDAQ', 1, NULL, true),
    ('VOD.L', 'ig', 'LSE', 2, 'IX.D.VOD.DAILY.IP', true),
    ('BP.L', 'ig', 'LSE', 2, 'IX.D.BP.DAILY.IP', true),
    ('^FTSE', 'ig', 'LSE', 1, 'IX.D.FTSE.DAILY.IP', true);
```

**Table: `order_book` (for Level 2 data)**
```sql
CREATE TABLE order_book (
    time TIMESTAMPTZ NOT NULL,
    symbol_id INT NOT NULL REFERENCES symbols(id),
    side VARCHAR(4) NOT NULL,  -- 'BID' or 'ASK'
    price DECIMAL(18, 8) NOT NULL,
    size DECIMAL(18, 8) NOT NULL,
    level INT NOT NULL,  -- Order book level (1-10)
    PRIMARY KEY (time, symbol_id, side, level)
);

SELECT create_hypertable('order_book', 'time');

-- Compression after 1 day
ALTER TABLE order_book SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol_id,side'
);

SELECT add_compression_policy('order_book', INTERVAL '1 day');
```

**Deliverables:**
- [ ] Create symbol_providers table
- [ ] Create order_book table
- [ ] Migration script
- [ ] Seed data for common symbols

---

### Phase 3: Configuration System (2-3 hours)

#### Environment Variables

**File**: `.env`

```bash
# IG Markets API
IG_API_KEY=your_ig_api_key
IG_USERNAME=your_ig_username
IG_PASSWORD=your_ig_password
IG_DEMO=true  # Use demo account

# Provider routing
ALPACA_MARKETS=NASDAQ,NYSE,AMEX
IG_MARKETS=LSE,DAX,CAC,FOREX

# Symbols to track
US_SYMBOLS=AAPL,MSFT,GOOGL,AMZN,NVDA
LSE_SYMBOLS=VOD.L,BP.L,HSBA.L,LLOY.L,BARC.L
INDEX_SYMBOLS=^FTSE,^GDAXI,^FCHI
```

#### Configuration Manager

**File**: `services/ingestion/app/config_manager.py`

```python
class ConfigManager:
    """
    Manage multi-provider configuration.
    """
    
    def __init__(self, db_conn):
        self.conn = db_conn
        
    def setup_default_routing(self):
        """
        Set up default symbol routing.
        
        Rules:
        - US symbols → Alpaca
        - LSE symbols (.L suffix) → IG
        - European indices (^) → IG
        """
        # US symbols
        us_symbols = os.getenv('US_SYMBOLS', '').split(',')
        for symbol in us_symbols:
            self.add_symbol_routing(symbol, 'alpaca', 'NASDAQ', 1)
        
        # LSE symbols
        lse_symbols = os.getenv('LSE_SYMBOLS', '').split(',')
        for symbol in lse_symbols:
            epic = self.get_ig_epic(symbol)
            self.add_symbol_routing(symbol, 'ig', 'LSE', 2, epic)
    
    def add_symbol_routing(self, symbol, provider, market, level, epic=None):
        """
        Add symbol routing configuration.
        """
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO symbol_providers (symbol, provider, market, level, epic)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE
            SET provider = EXCLUDED.provider,
                market = EXCLUDED.market,
                level = EXCLUDED.level,
                epic = EXCLUDED.epic
        """, (symbol, provider, market, level, epic))
        self.conn.commit()
```

**Deliverables:**
- [ ] Environment variable setup
- [ ] Configuration manager
- [ ] Default routing rules
- [ ] Symbol mapping

---

### Phase 4: Dashboard Updates (2-3 hours)

#### Multi-Market Overview

**File**: `web/app/Livewire/MultiMarketOverview.php`

**What it shows:**
- Separate sections for US and LSE markets
- Provider indicator (Alpaca/IG)
- Data level indicator (L1/L2)
- Order book visualization for L2 data

**UI Mockup:**
```
┌─────────────────────────────────────────────┐
│ 🇺🇸 US Markets (Alpaca - Level 1)          │
├─────────────────────────────────────────────┤
│ AAPL  │ $254.20 │ ➖ BALANCE │ 💤 0        │
│ MSFT  │ $425.80 │ ➖ BALANCE │ 💤 0        │
│ GOOGL │ $178.50 │ ➖ BALANCE │ 💤 0        │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ 🇬🇧 LSE Markets (IG - Level 2)             │
├─────────────────────────────────────────────┤
│ VOD.L │ 72.50p  │ ➖ BALANCE │ 💤 0        │
│ BP.L  │ 485.20p │ ➖ BALANCE │ 💤 0        │
│                                             │
│ 📊 Order Book (VOD.L)                       │
│ Bids          │ Price  │ Asks              │
│ 1,000 @ 72.48 │ 72.50  │ 72.52 @ 800       │
│ 2,500 @ 72.46 │        │ 72.54 @ 1,200     │
└─────────────────────────────────────────────┘
```

**Deliverables:**
- [ ] Multi-market overview component
- [ ] Provider badges
- [ ] Order book widget (for L2 data)
- [ ] Market grouping

---

## 🚀 Quick Start Guide

### Step 1: Get IG API Credentials

1. **Create IG Account**: https://www.ig.com/uk
2. **Generate API Key**: https://labs.ig.com/gettingstarted
3. **Get Demo Credentials**: Use demo account for testing

### Step 2: Update Configuration

```bash
# Add to .env
IG_API_KEY=your_key_here
IG_USERNAME=your_username
IG_PASSWORD=your_password
IG_DEMO=true

# Add LSE symbols
LSE_SYMBOLS=VOD.L,BP.L,HSBA.L,LLOY.L,BARC.L
```

### Step 3: Run Database Migration

```bash
# Create new tables
docker compose exec -T db psql -U postgres -d trading < sql/multi_provider_schema.sql

# Seed routing configuration
docker compose exec engine python3 -c "
from app.config_manager import ConfigManager
import psycopg2

conn = psycopg2.connect(host='db', user='postgres', password='postgres', dbname='trading')
config = ConfigManager(conn)
config.setup_default_routing()
"
```

### Step 4: Restart Ingestion

```bash
docker compose restart ingestion
```

### Step 5: Verify

```bash
# Check IG connection
docker compose logs ingestion | grep "IG"

# Should see:
# ✅ IG authenticated successfully
# ✅ Subscribed to VOD.L, BP.L, HSBA.L...
```

---

## 📊 IG Market Identifiers (EPICs)

### LSE Stocks
- **Vodafone**: `IX.D.VOD.DAILY.IP`
- **BP**: `IX.D.BP.DAILY.IP`
- **HSBC**: `IX.D.HSBA.DAILY.IP`
- **Lloyds**: `IX.D.LLOY.DAILY.IP`
- **Barclays**: `IX.D.BARC.DAILY.IP`

### Indices
- **FTSE 100**: `IX.D.FTSE.DAILY.IP`
- **DAX**: `IX.D.DAX.DAILY.IP`
- **CAC 40**: `IX.D.CAC.DAILY.IP`

### Forex
- **GBP/USD**: `CS.D.GBPUSD.TODAY.IP`
- **EUR/USD**: `CS.D.EURUSD.TODAY.IP`

---

## ⚠️ Important Notes

### IG API Limitations
- **Rate limits**: 60 requests/minute (demo), 300/minute (live)
- **Share prices**: Limited for some stocks
- **Streaming**: Uses Lightstreamer protocol (requires library)
- **Market hours**: LSE 08:00-16:30 GMT

### Data Quality
- **Level 1**: Bid, ask, last price ✅
- **Level 2**: Order book depth (5-10 levels) ✅
- **Historical**: Limited compared to Alpaca
- **Tick data**: Not available

### Cost
- **Demo account**: Free ✅
- **Live account**: Free with funded account
- **No subscription fees** for API access

---

## ✅ Summary

**What you'll get:**
- ✅ US markets via Alpaca (30 stocks)
- ✅ LSE markets via IG (UK stocks)
- ✅ Level 2 order book data (IG only)
- ✅ Multi-market dashboard
- ✅ Configurable routing

**Timeline:**
- Phase 1: IG integration (4-6 hours)
- Phase 2: Database updates (1-2 hours)
- Phase 3: Configuration (2-3 hours)
- Phase 4: Dashboard (2-3 hours)
- **Total**: 9-14 hours

**Cost:**
- IG API: $0 (free with demo account)
- Alpaca: $0 (paper trading)
- **Total**: $0

**Ready to start building the multi-provider system!** 🚀

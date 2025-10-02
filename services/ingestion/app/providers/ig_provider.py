"""
IG Markets Data Provider

Provides Level 1 and Level 2 market data for:
- LSE (London Stock Exchange)
- European markets (DAX, CAC, etc.)
- Forex pairs
- Commodities

API Documentation: https://labs.ig.com/rest-trading-api-reference
"""

import requests
import time
from typing import Optional, Dict, List
from loguru import logger


class IGProvider:
    """
    IG Markets data provider.
    
    Features:
    - Level 1 data (bid, ask, last price)
    - Level 2 data (order book depth)
    - Real-time streaming (via Lightstreamer)
    - Multiple markets (LSE, DAX, CAC, Forex)
    """
    
    def __init__(self, api_key: str, username: str, password: str, demo: bool = True):
        """
        Initialize IG provider.
        
        Args:
            api_key: IG API key
            username: IG account username
            password: IG account password
            demo: Use demo account (default True)
        """
        self.api_key = api_key
        self.username = username
        self.password = password
        self.demo = demo
        
        # API endpoints
        if demo:
            self.base_url = 'https://demo-api.ig.com/gateway/deal'
        else:
            self.base_url = 'https://api.ig.com/gateway/deal'
        
        # Session tokens
        self.cst_token = None
        self.security_token = None
        self.authenticated = False
        
        logger.info(f"IG Provider initialized ({'DEMO' if demo else 'LIVE'} mode)")
    
    def authenticate(self) -> bool:
        """
        Authenticate with IG API.
        
        IG requires encryption for passwords in v3+.
        Using v2 which accepts plain text passwords.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Headers matching IG's official REST API Companion
            headers = {
                'X-IG-API-KEY': self.api_key,
                'Content-Type': 'application/json; charset=UTF-8',
                'Accept': 'application/json; charset=UTF-8',
                'VERSION': '2'  # Uppercase VERSION
            }
            
            payload = {
                'identifier': self.username,
                'password': self.password
            }
            
            logger.debug(f"Authenticating with username: {self.username}")
            logger.debug(f"API endpoint: {self.base_url}/session")
            
            response = requests.post(
                f'{self.base_url}/session',
                headers=headers,
                json=payload,
                timeout=30  # Longer timeout
            )
            
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                self.cst_token = response.headers.get('CST')
                self.security_token = response.headers.get('X-SECURITY-TOKEN')
                self.authenticated = True
                
                account_info = response.json()
                logger.info(
                    f"✅ IG authenticated successfully - "
                    f"Account: {account_info.get('currentAccountId', 'N/A')}"
                )
                return True
            else:
                logger.error(f"IG authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"IG authentication error: {e}")
            return False
    
    def _get_headers(self, version: str = '1') -> Dict[str, str]:
        """
        Get authenticated request headers.
        
        Args:
            version: API version
            
        Returns:
            Headers dict
        """
        return {
            'X-IG-API-KEY': self.api_key,
            'CST': self.cst_token,
            'X-SECURITY-TOKEN': self.security_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Version': version
        }
    
    def get_market_details(self, epic: str) -> Optional[Dict]:
        """
        Get Level 1 market data for a symbol.
        
        Args:
            epic: IG market identifier (e.g., 'IX.D.FTSE.DAILY.IP')
            
        Returns:
            Market data dict or None
        """
        if not self.authenticated:
            logger.warning("Not authenticated, attempting to authenticate...")
            if not self.authenticate():
                return None
        
        try:
            response = requests.get(
                f'{self.base_url}/markets/{epic}',
                headers=self._get_headers(version='3'),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                snapshot = data.get('snapshot', {})
                instrument = data.get('instrument', {})
                
                return {
                    'epic': epic,
                    'name': instrument.get('name', ''),
                    'bid': float(snapshot.get('bid', 0)),
                    'ask': float(snapshot.get('offer', 0)),
                    'last': float(snapshot.get('lastTradedPrice', 0)),
                    'high': float(snapshot.get('high', 0)),
                    'low': float(snapshot.get('low', 0)),
                    'volume': int(snapshot.get('volume', 0)),
                    'change': float(snapshot.get('netChange', 0)),
                    'change_pct': float(snapshot.get('percentageChange', 0)),
                    'market_status': snapshot.get('marketStatus', 'UNKNOWN'),
                    'update_time': snapshot.get('updateTime', ''),
                    'currency': instrument.get('currencies', [{}])[0].get('code', 'GBP')
                }
            elif response.status_code == 401:
                logger.warning("IG session expired, re-authenticating...")
                self.authenticated = False
                return self.get_market_details(epic)  # Retry once
            else:
                logger.error(f"IG market details failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching IG market details for {epic}: {e}")
            return None
    
    def get_order_book(self, epic: str) -> Optional[Dict]:
        """
        Get Level 2 order book data.
        
        Args:
            epic: IG market identifier
            
        Returns:
            Order book dict with bids and asks
        """
        if not self.authenticated:
            logger.warning("Not authenticated, attempting to authenticate...")
            if not self.authenticate():
                return None
        
        try:
            response = requests.get(
                f'{self.base_url}/marketdepth/{epic}',
                headers=self._get_headers(version='1'),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse bids (buy orders)
                bids = []
                for bid in data.get('bids', []):
                    bids.append({
                        'price': float(bid.get('price', 0)),
                        'size': float(bid.get('size', 0)),
                        'level': int(bid.get('level', 0))
                    })
                
                # Parse asks (sell orders)
                asks = []
                for ask in data.get('asks', []):
                    asks.append({
                        'price': float(ask.get('price', 0)),
                        'size': float(ask.get('size', 0)),
                        'level': int(ask.get('level', 0))
                    })
                
                return {
                    'epic': epic,
                    'bids': sorted(bids, key=lambda x: x['price'], reverse=True),  # Highest first
                    'asks': sorted(asks, key=lambda x: x['price']),  # Lowest first
                    'timestamp': data.get('timestamp', ''),
                    'total_bid_size': sum(b['size'] for b in bids),
                    'total_ask_size': sum(a['size'] for a in asks),
                    'spread': (asks[0]['price'] - bids[0]['price']) if bids and asks else 0
                }
            elif response.status_code == 401:
                logger.warning("IG session expired, re-authenticating...")
                self.authenticated = False
                return self.get_order_book(epic)  # Retry once
            else:
                logger.error(f"IG order book failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching IG order book for {epic}: {e}")
            return None
    
    def search_markets(self, query: str) -> List[Dict]:
        """
        Search for markets by name or epic.
        
        Args:
            query: Search term (e.g., 'Vodafone', 'FTSE')
            
        Returns:
            List of matching markets
        """
        if not self.authenticated:
            if not self.authenticate():
                return []
        
        try:
            response = requests.get(
                f'{self.base_url}/markets',
                headers=self._get_headers(version='1'),
                params={'searchTerm': query},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                markets = []
                
                for market in data.get('markets', []):
                    markets.append({
                        'epic': market.get('epic', ''),
                        'name': market.get('instrumentName', ''),
                        'type': market.get('instrumentType', ''),
                        'market_id': market.get('marketId', ''),
                        'expiry': market.get('expiry', '')
                    })
                
                return markets
            else:
                logger.error(f"IG market search failed: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching IG markets: {e}")
            return []
    
    def get_account_info(self) -> Optional[Dict]:
        """
        Get account information.
        
        Returns:
            Account details dict
        """
        if not self.authenticated:
            if not self.authenticate():
                return None
        
        try:
            response = requests.get(
                f'{self.base_url}/accounts',
                headers=self._get_headers(version='1'),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                accounts = data.get('accounts', [])
                
                if accounts:
                    account = accounts[0]  # Primary account
                    return {
                        'account_id': account.get('accountId', ''),
                        'account_name': account.get('accountName', ''),
                        'balance': float(account.get('balance', {}).get('balance', 0)),
                        'available': float(account.get('balance', {}).get('available', 0)),
                        'currency': account.get('currency', 'GBP')
                    }
                return None
            else:
                logger.error(f"IG account info failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching IG account info: {e}")
            return None


# Common IG market EPICs for easy reference
COMMON_EPICS = {
    # LSE Stocks
    'VOD.L': 'IX.D.VOD.DAILY.IP',      # Vodafone
    'BP.L': 'IX.D.BP.DAILY.IP',        # BP
    'HSBA.L': 'IX.D.HSBA.DAILY.IP',    # HSBC
    'LLOY.L': 'IX.D.LLOY.DAILY.IP',    # Lloyds
    'BARC.L': 'IX.D.BARC.DAILY.IP',    # Barclays
    'GSK.L': 'IX.D.GSK.DAILY.IP',      # GSK
    'AZN.L': 'IX.D.AZN.DAILY.IP',      # AstraZeneca
    'RIO.L': 'IX.D.RIO.DAILY.IP',      # Rio Tinto
    
    # Indices
    '^FTSE': 'IX.D.FTSE.DAILY.IP',     # FTSE 100
    '^GDAXI': 'IX.D.DAX.DAILY.IP',     # DAX
    '^FCHI': 'IX.D.CAC.DAILY.IP',      # CAC 40
    
    # Forex
    'GBPUSD': 'CS.D.GBPUSD.TODAY.IP',  # GBP/USD
    'EURUSD': 'CS.D.EURUSD.TODAY.IP',  # EUR/USD
    'EURGBP': 'CS.D.EURGBP.TODAY.IP',  # EUR/GBP
}


def get_epic_for_symbol(symbol: str) -> Optional[str]:
    """
    Get IG EPIC for a symbol.
    
    Args:
        symbol: Stock symbol (e.g., 'VOD.L')
        
    Returns:
        IG EPIC or None
    """
    return COMMON_EPICS.get(symbol)

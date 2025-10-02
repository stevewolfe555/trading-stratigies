#!/usr/bin/env python3
"""
Test IG Markets API Connection

This script tests the IG provider integration:
1. Authentication
2. Level 1 data fetching
3. Level 2 order book
4. Provider routing
"""

import os
import sys
from app.providers.ig_provider import IGProvider, COMMON_EPICS
from app.provider_router import ProviderRouter

def test_ig_authentication():
    """Test IG API authentication."""
    print("\n🔐 Testing IG Authentication...")
    
    api_key = os.getenv('IG_API_KEY')
    username = os.getenv('IG_USERNAME')
    password = os.getenv('IG_PASSWORD')
    demo = os.getenv('IG_DEMO', 'true').lower() == 'true'
    
    if not all([api_key, username, password]):
        print("❌ Missing IG credentials in .env file")
        print("   Please set: IG_API_KEY, IG_USERNAME, IG_PASSWORD")
        return None
    
    provider = IGProvider(api_key, username, password, demo=demo)
    
    if provider.authenticate():
        print("✅ Authentication successful!")
        return provider
    else:
        print("❌ Authentication failed")
        return None


def test_level1_data(provider):
    """Test Level 1 market data."""
    print("\n📊 Testing Level 1 Data...")
    
    # Test FTSE 100 index
    epic = COMMON_EPICS['^FTSE']
    print(f"\nFetching data for FTSE 100 ({epic})...")
    
    data = provider.get_market_details(epic)
    
    if data:
        print("✅ Level 1 data retrieved successfully!")
        print(f"   Name: {data['name']}")
        print(f"   Bid: {data['bid']:.2f}")
        print(f"   Ask: {data['ask']:.2f}")
        print(f"   Last: {data['last']:.2f}")
        print(f"   Change: {data['change']:+.2f} ({data['change_pct']:+.2f}%)")
        print(f"   Volume: {data['volume']:,}")
        print(f"   Status: {data['market_status']}")
        return True
    else:
        print("❌ Failed to fetch Level 1 data")
        return False


def test_level2_data(provider):
    """Test Level 2 order book data."""
    print("\n📈 Testing Level 2 Order Book...")
    
    # Test Vodafone
    epic = COMMON_EPICS['VOD.L']
    print(f"\nFetching order book for Vodafone ({epic})...")
    
    data = provider.get_order_book(epic)
    
    if data:
        print("✅ Level 2 data retrieved successfully!")
        print(f"\n   Spread: {data['spread']:.4f}")
        print(f"   Total Bid Size: {data['total_bid_size']:,.0f}")
        print(f"   Total Ask Size: {data['total_ask_size']:,.0f}")
        
        print("\n   Top 5 Bids:")
        for i, bid in enumerate(data['bids'][:5], 1):
            print(f"   {i}. {bid['size']:>10,.0f} @ {bid['price']:.4f}")
        
        print("\n   Top 5 Asks:")
        for i, ask in enumerate(data['asks'][:5], 1):
            print(f"   {i}. {ask['size']:>10,.0f} @ {ask['price']:.4f}")
        
        return True
    else:
        print("❌ Failed to fetch Level 2 data")
        return False


def test_provider_router():
    """Test provider routing."""
    print("\n🔀 Testing Provider Router...")
    
    router = ProviderRouter()
    router.load_routing_config()
    
    # Test symbol routing
    test_symbols = [
        ('AAPL', 'alpaca'),
        ('VOD.L', 'ig'),
        ('^FTSE', 'ig'),
        ('GBPUSD', 'ig')
    ]
    
    print("\nTesting symbol routing:")
    for symbol, expected_provider in test_symbols:
        info = router.get_routing_info(symbol)
        actual_provider = info['provider']
        
        if actual_provider == expected_provider:
            print(f"   ✅ {symbol:10s} → {actual_provider:10s} (Level {info['level']})")
        else:
            print(f"   ❌ {symbol:10s} → {actual_provider:10s} (expected {expected_provider})")
    
    return True


def test_account_info(provider):
    """Test account information."""
    print("\n💰 Testing Account Info...")
    
    account = provider.get_account_info()
    
    if account:
        print("✅ Account info retrieved successfully!")
        print(f"   Account ID: {account['account_id']}")
        print(f"   Account Name: {account['account_name']}")
        print(f"   Balance: {account['currency']} {account['balance']:,.2f}")
        print(f"   Available: {account['currency']} {account['available']:,.2f}")
        return True
    else:
        print("❌ Failed to fetch account info")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("IG Markets API Connection Test")
    print("=" * 60)
    
    # Test authentication
    provider = test_ig_authentication()
    if not provider:
        print("\n❌ Cannot proceed without authentication")
        sys.exit(1)
    
    # Test Level 1 data
    if not test_level1_data(provider):
        print("\n⚠️  Level 1 data test failed")
    
    # Test Level 2 data
    if not test_level2_data(provider):
        print("\n⚠️  Level 2 data test failed")
    
    # Test account info
    if not test_account_info(provider):
        print("\n⚠️  Account info test failed")
    
    # Test provider router
    test_provider_router()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Update .env with your IG credentials")
    print("2. Run: docker compose restart ingestion")
    print("3. Check dashboard for LSE stocks")
    print("=" * 60)


if __name__ == '__main__':
    main()

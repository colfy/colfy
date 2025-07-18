#!/usr/bin/env python3
"""
Test script for original_bot.py to verify it can be imported and basic functionality works
"""

import os
import sys
import asyncio
from unittest.mock import patch

# Set up test environment variables
os.environ['DISCORD_BOT_TOKEN'] = 'test_token'
os.environ['BLOCKCYPHER_API_TOKEN'] = 'test_api_token'
os.environ['MASTER_WALLET_ADDRESS'] = 'test_address'
os.environ['MASTER_WALLET_PRIVATE_KEY'] = 'test_private_key'

def test_import():
    """Test that the original bot can be imported"""
    try:
        import original_bot
        print("✅ Successfully imported original_bot.py")
        return True
    except Exception as e:
        print(f"❌ Failed to import original_bot.py: {e}")
        return False

def test_classes():
    """Test that key classes can be instantiated"""
    try:
        from original_bot import APIRateLimiter, AtomicFileManager, BlockCypherHandler
        
        # Test APIRateLimiter
        rate_limiter = APIRateLimiter()
        print("✅ APIRateLimiter instantiated successfully")
        
        # Test AtomicFileManager
        file_manager = AtomicFileManager()
        print("✅ AtomicFileManager instantiated successfully")
        
        # Test BlockCypherHandler
        blockchain_handler = BlockCypherHandler(rate_limiter)
        print("✅ BlockCypherHandler instantiated successfully")
        
        return True
    except Exception as e:
        print(f"❌ Failed to instantiate classes: {e}")
        return False

def test_bot_initialization():
    """Test that the bot can be initialized"""
    try:
        from original_bot import OriginalCryptoBattleBot
        
        # Mock discord.py to avoid actual connection
        with patch('discord.ext.commands.Bot.__init__'):
            bot = OriginalCryptoBattleBot()
            print("✅ OriginalCryptoBattleBot instantiated successfully")
            
            # Test that improved backend systems are initialized
            assert hasattr(bot, 'rate_limiter'), "rate_limiter not initialized"
            assert hasattr(bot, 'blockchain_handler'), "blockchain_handler not initialized"
            assert hasattr(bot, 'file_manager'), "file_manager not initialized"
            
            print("✅ All backend systems initialized correctly")
            
        return True
    except Exception as e:
        print(f"❌ Failed to initialize bot: {e}")
        return False

def test_constants():
    """Test that original constants are defined"""
    try:
        from original_bot import (
            CRYPTOCURRENCIES, FIAT_RATES, BET_CHANNEL_ID, 
            TICKET_CATEGORY_NAME, BOT_PREFIX, DICE_SIDES, 
            COINFLIP_OPTIONS, MIN_BET_AMOUNT, MAX_BET_AMOUNT
        )
        
        print("✅ All original constants are defined")
        
        # Test that cryptocurrencies are properly configured
        assert 'BTC' in CRYPTOCURRENCIES, "BTC not in CRYPTOCURRENCIES"
        assert 'LTC' in CRYPTOCURRENCIES, "LTC not in CRYPTOCURRENCIES"
        
        print("✅ Cryptocurrency configuration is correct")
        
        return True
    except Exception as e:
        print(f"❌ Failed to verify constants: {e}")
        return False

def test_ui_components():
    """Test that UI components can be imported"""
    try:
        from original_bot import (
            CryptoSelectView, GameModeView, TipView, 
            OpponentModal, WithdrawModal, BattleRequestView
        )
        
        print("✅ All UI components imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import UI components: {e}")
        return False

async def test_file_operations():
    """Test that file operations work"""
    try:
        from original_bot import AtomicFileManager
        
        # Test saving and loading JSON
        test_data = {"test": "data", "number": 123}
        test_file = "test_file.json"
        
        # Save data
        await AtomicFileManager.save_json_with_lock(test_file, test_data)
        print("✅ JSON save operation successful")
        
        # Load data
        loaded_data = await AtomicFileManager.load_json_with_lock(test_file)
        assert loaded_data == test_data, "Loaded data doesn't match saved data"
        print("✅ JSON load operation successful")
        
        # Clean up
        if os.path.exists(test_file):
            os.remove(test_file)
        
        return True
    except Exception as e:
        print(f"❌ File operations test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing original_bot.py compatibility layer...")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_import),
        ("Classes Test", test_classes),
        ("Bot Initialization Test", test_bot_initialization),
        ("Constants Test", test_constants),
        ("UI Components Test", test_ui_components),
        ("File Operations Test", lambda: asyncio.run(test_file_operations())),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name}...")
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The compatibility layer is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
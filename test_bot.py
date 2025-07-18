#!/usr/bin/env python3
"""
Test script for Crypto Battle Bot
Tests core functionality without requiring Discord connection
"""

import asyncio
import os
import tempfile
import shutil
from unittest.mock import Mock, patch
import json

# Import bot components
from crypto_battle_bot import (
    Config, APIRateLimiter, AtomicFileManager, BlockCypherHandler,
    Player, Battle, CryptoBattleBot, ConfigurationError
)

async def test_config():
    """Test configuration validation"""
    print("Testing configuration...")
    
    # Test missing environment variables
    try:
        config = Config()
        print("❌ Config should have failed with missing env vars")
    except ConfigurationError as e:
        print(f"✅ Config validation works: {e}")
    
    # Test with valid environment variables
    os.environ.update({
        'DISCORD_BOT_TOKEN': 'test_token',
        'BLOCKCYPHER_API_TOKEN': 'test_api_token',
        'MASTER_WALLET_ADDRESS': 'test_address',
        'MASTER_WALLET_PRIVATE_KEY': 'test_private_key'
    })
    
    try:
        config = Config()
        print("✅ Config validation passed with valid env vars")
    except Exception as e:
        print(f"❌ Config failed unexpectedly: {e}")

async def test_rate_limiter():
    """Test rate limiting functionality"""
    print("\nTesting rate limiter...")
    
    rate_limiter = APIRateLimiter(requests_per_hour=5, requests_per_minute=2)
    
    # Test basic rate limiting
    start_time = asyncio.get_event_loop().time()
    
    for i in range(3):
        await rate_limiter.acquire("test_endpoint")
    
    end_time = asyncio.get_event_loop().time()
    elapsed = end_time - start_time
    
    if elapsed >= 60:  # Should have waited due to per-minute limit
        print("✅ Rate limiter enforced per-minute limits")
    else:
        print("⚠️ Rate limiter may not be enforcing limits properly")

async def test_file_manager():
    """Test atomic file operations"""
    print("\nTesting file manager...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test.json")
        test_data = {"test": "data", "number": 42}
        
        # Test save and load
        await AtomicFileManager.save_json_with_lock(test_file, test_data)
        loaded_data = await AtomicFileManager.load_json_with_lock(test_file)
        
        if loaded_data == test_data:
            print("✅ File manager save/load works correctly")
        else:
            print(f"❌ File manager failed: {loaded_data} != {test_data}")
        
        # Test default value for missing file
        missing_file = os.path.join(temp_dir, "missing.json")
        default_data = await AtomicFileManager.load_json_with_lock(missing_file, {"default": True})
        
        if default_data == {"default": True}:
            print("✅ File manager default values work correctly")
        else:
            print(f"❌ File manager default failed: {default_data}")

async def test_player_model():
    """Test player data model"""
    print("\nTesting player model...")
    
    # Create player
    player = Player(user_id=12345, username="testuser", balance=100000)
    
    # Test serialization
    player_dict = player.to_dict()
    restored_player = Player.from_dict(player_dict)
    
    if (restored_player.user_id == player.user_id and 
        restored_player.username == player.username and
        restored_player.balance == player.balance):
        print("✅ Player model serialization works correctly")
    else:
        print("❌ Player model serialization failed")

async def test_battle_model():
    """Test battle data model"""
    print("\nTesting battle model...")
    
    # Create battle
    battle = Battle(
        battle_id="test_battle",
        player1_id=12345,
        player2_id=67890,
        amount=50000
    )
    
    # Test serialization
    battle_dict = battle.to_dict()
    restored_battle = Battle.from_dict(battle_dict)
    
    if (restored_battle.battle_id == battle.battle_id and
        restored_battle.player1_id == battle.player1_id and
        restored_battle.amount == battle.amount):
        print("✅ Battle model serialization works correctly")
    else:
        print("❌ Battle model serialization failed")

async def test_address_validation():
    """Test Bitcoin address validation"""
    print("\nTesting address validation...")
    
    # Mock bot for testing
    class MockBot:
        def _is_valid_bitcoin_address(self, address):
            from crypto_battle_bot import CryptoBattleBot
            return CryptoBattleBot._is_valid_bitcoin_address(self, address)
    
    bot = MockBot()
    
    # Test valid addresses
    valid_addresses = [
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Legacy
        "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # P2SH
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # Bech32
        "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx"   # Testnet Bech32
    ]
    
    invalid_addresses = [
        "",
        "invalid",
        "1234567890",
        "bc1invalid"
    ]
    
    valid_count = sum(1 for addr in valid_addresses if bot._is_valid_bitcoin_address(addr))
    invalid_count = sum(1 for addr in invalid_addresses if not bot._is_valid_bitcoin_address(addr))
    
    if valid_count == len(valid_addresses) and invalid_count == len(invalid_addresses):
        print("✅ Address validation works correctly")
    else:
        print(f"❌ Address validation failed: {valid_count}/{len(valid_addresses)} valid, {invalid_count}/{len(invalid_addresses)} invalid")

async def test_blockchain_handler():
    """Test blockchain handler (mocked)"""
    print("\nTesting blockchain handler...")
    
    # Mock the requests to avoid actual API calls
    with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
        # Mock balance response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"balance": 100000}
        
        # Mock transaction responses
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "tx": {"hash": "test_tx_hash"},
            "tosign": ["test_tosign"]
        }
        
        config = Config()
        rate_limiter = APIRateLimiter()
        handler = BlockCypherHandler(config, rate_limiter)
        
        try:
            # Test balance check
            balance = await handler.get_address_balance("test_address")
            if balance == 100000:
                print("✅ Blockchain handler balance check works")
            else:
                print(f"❌ Blockchain handler balance failed: {balance}")
            
            # Test transaction creation
            tx = await handler.create_transaction("from_addr", "to_addr", 50000)
            if "tx" in tx:
                print("✅ Blockchain handler transaction creation works")
            else:
                print("❌ Blockchain handler transaction creation failed")
                
        except Exception as e:
            print(f"❌ Blockchain handler test failed: {e}")

async def run_all_tests():
    """Run all tests"""
    print("🧪 Running Crypto Battle Bot Tests\n")
    
    try:
        await test_config()
        await test_rate_limiter()
        await test_file_manager()
        await test_player_model()
        await test_battle_model()
        await test_address_validation()
        await test_blockchain_handler()
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_all_tests())
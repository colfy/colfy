#!/usr/bin/env python3
"""
Configuration Validator for Crypto Battle Bot
Validates environment variables and configuration before starting the bot
"""

import os
import re
from dotenv import load_dotenv

def validate_discord_token(token):
    """Validate Discord bot token format"""
    if not token:
        return False, "Discord token is empty"
    
    # Basic Discord token format validation
    if len(token) < 50:
        return False, "Discord token appears too short"
    
    return True, "Valid"

def validate_bitcoin_address(address):
    """Validate Bitcoin address format"""
    if not address:
        return False, "Address is empty"
    
    # Basic Bitcoin address validation
    if len(address) < 26 or len(address) > 62:
        return False, "Invalid address length"
    
    # Check for valid prefixes
    valid_prefixes = ['1', '3', 'bc1', 'tb1']
    if not any(address.startswith(prefix) for prefix in valid_prefixes):
        return False, "Invalid address prefix"
    
    return True, "Valid"

def validate_private_key(private_key):
    """Validate private key format"""
    if not private_key:
        return False, "Private key is empty"
    
    # Basic validation - should be hex string
    if len(private_key) not in [51, 52, 64]:  # WIF or hex formats
        return False, "Invalid private key length"
    
    return True, "Valid (format check only - not cryptographically verified)"

def validate_blockcypher_token(token):
    """Validate BlockCypher API token"""
    if not token:
        return False, "BlockCypher token is empty"
    
    # Basic format check
    if len(token) < 30:
        return False, "BlockCypher token appears too short"
    
    return True, "Valid"

def validate_network(network):
    """Validate network setting"""
    valid_networks = ['main', 'test3']
    if network not in valid_networks:
        return False, f"Invalid network. Must be one of: {valid_networks}"
    
    return True, "Valid"

def validate_amount(amount_str, name):
    """Validate amount settings"""
    try:
        amount = int(amount_str)
        if amount <= 0:
            return False, f"{name} must be positive"
        return True, "Valid"
    except (ValueError, TypeError):
        return False, f"{name} must be a valid integer"

def main():
    """Main validation function"""
    print("🔍 Validating Crypto Battle Bot Configuration...")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Configuration checks
    checks = [
        ("Discord Bot Token", os.getenv('DISCORD_BOT_TOKEN'), validate_discord_token),
        ("BlockCypher API Token", os.getenv('BLOCKCYPHER_API_TOKEN'), validate_blockcypher_token),
        ("Master Wallet Address", os.getenv('MASTER_WALLET_ADDRESS'), validate_bitcoin_address),
        ("Master Wallet Private Key", os.getenv('MASTER_WALLET_PRIVATE_KEY'), validate_private_key),
        ("Network", os.getenv('NETWORK', 'test3'), validate_network),
        ("Min Withdrawal Amount", os.getenv('MIN_WITHDRAWAL_AMOUNT', '10000'), lambda x: validate_amount(x, "Min withdrawal amount")),
        ("Max Withdrawal Amount", os.getenv('MAX_WITHDRAWAL_AMOUNT', '1000000'), lambda x: validate_amount(x, "Max withdrawal amount")),
    ]
    
    all_valid = True
    
    for name, value, validator in checks:
        try:
            is_valid, message = validator(value)
            status = "✅" if is_valid else "❌"
            print(f"{status} {name}: {message}")
            
            if not is_valid:
                all_valid = False
                
        except Exception as e:
            print(f"❌ {name}: Validation error - {e}")
            all_valid = False
    
    print("=" * 60)
    
    # Additional checks
    print("\n🔧 Additional Checks:")
    
    # Check if .env file exists
    if os.path.exists('.env'):
        print("✅ .env file found")
    else:
        print("⚠️  .env file not found - using system environment variables")
    
    # Check file permissions
    required_files = ['crypto_battle_bot.py', 'requirements.txt']
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} missing")
            all_valid = False
    
    # Check Python version
    import sys
    if sys.version_info >= (3, 8):
        print(f"✅ Python version: {sys.version.split()[0]}")
    else:
        print(f"❌ Python version too old: {sys.version.split()[0]} (requires 3.8+)")
        all_valid = False
    
    # Check dependencies
    try:
        import discord
        import requests
        import aiofiles
        print("✅ All required packages installed")
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        all_valid = False
    
    print("=" * 60)
    
    if all_valid:
        print("🎉 Configuration validation passed! Bot should start successfully.")
        print("\n📋 Next steps:")
        print("1. Run: python3 crypto_battle_bot.py")
        print("2. Invite bot to your Discord server")
        print("3. Test with: !help command")
        return 0
    else:
        print("❌ Configuration validation failed! Please fix the issues above.")
        print("\n🔧 Common fixes:")
        print("1. Copy .env.example to .env and fill in your values")
        print("2. Install dependencies: pip3 install -r requirements.txt")
        print("3. Check that all tokens and addresses are correct")
        return 1

if __name__ == "__main__":
    exit(main())
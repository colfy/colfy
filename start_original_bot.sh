#!/bin/bash

# Crypto Battle Bot - Original Bot Compatibility Layer Startup Script
# This script starts the original bot with improved backend systems

set -e

echo "🎮 Starting Crypto Battle Bot (Original Compatibility Layer)..."
echo "=================================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "📝 Please copy .env.example to .env and configure your settings:"
    echo "   cp .env.example .env"
    echo "   # Edit .env with your actual values"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Startup cancelled."
        exit 1
    fi
fi

# Check if Python dependencies are installed
echo "🔍 Checking Python dependencies..."
python3 -c "
import discord
import requests
import aiofiles
from dotenv import load_dotenv
print('✅ All dependencies are installed')
" 2>/dev/null || {
    echo "❌ Missing dependencies! Please install them:"
    echo "   pip install -r requirements.txt"
    exit 1
}

# Run tests if requested
if [ "$1" = "--test" ]; then
    echo "🧪 Running compatibility tests..."
    python3 test_original_bot.py
    if [ $? -ne 0 ]; then
        echo "❌ Tests failed! Please check the issues above."
        exit 1
    fi
    echo ""
fi

# Check environment variables
echo "🔧 Validating environment configuration..."
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()

required_vars = ['DISCORD_BOT_TOKEN', 'BLOCKCYPHER_API_TOKEN']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f'❌ Missing required environment variables: {\", \".join(missing_vars)}')
    exit(1)
else:
    print('✅ Environment configuration is valid')
" || exit 1

# Create backup of data files if they exist
if [ -f user_wallets.json ] || [ -f deposit_addresses.json ]; then
    echo "💾 Creating backup of existing data files..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    mkdir -p backups
    
    if [ -f user_wallets.json ]; then
        cp user_wallets.json "backups/user_wallets_${timestamp}.json"
        echo "   ✅ Backed up user_wallets.json"
    fi
    
    if [ -f deposit_addresses.json ]; then
        cp deposit_addresses.json "backups/deposit_addresses_${timestamp}.json"
        echo "   ✅ Backed up deposit_addresses.json"
    fi
fi

echo ""
echo "🚀 Starting Original Crypto Battle Bot..."
echo "📊 Bot will maintain original interface with improved backend"
echo "📝 Logs will be written to crypto_battle_bot.log"
echo "🛑 Press Ctrl+C to stop the bot"
echo ""

# Start the bot
exec python3 original_bot.py

#!/bin/bash

# Crypto Battle Bot Startup Script

set -e

echo "🤖 Starting Crypto Battle Bot..."

# Check if configuration is valid
echo "🔍 Validating configuration..."
if ! python3 validate_config.py; then
    echo "❌ Configuration validation failed. Please fix the issues and try again."
    exit 1
fi

echo "✅ Configuration validated successfully!"

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the bot with proper error handling
echo "🚀 Starting bot..."
python3 crypto_battle_bot.py 2>&1 | tee -a logs/startup.log
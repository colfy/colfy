#!/bin/bash

# Crypto Battle Bot Deployment Script

set -e

echo "🚀 Deploying Crypto Battle Bot..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip."
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env file with your actual configuration values:"
    echo "   - DISCORD_BOT_TOKEN"
    echo "   - BLOCKCYPHER_API_TOKEN"
    echo "   - MASTER_WALLET_ADDRESS"
    echo "   - MASTER_WALLET_PRIVATE_KEY"
    echo ""
    echo "❌ Deployment paused. Please configure .env file and run this script again."
    exit 1
fi

# Validate environment configuration
echo "🔍 Validating configuration..."
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()

required_vars = [
    'DISCORD_BOT_TOKEN',
    'BLOCKCYPHER_API_TOKEN', 
    'MASTER_WALLET_ADDRESS',
    'MASTER_WALLET_PRIVATE_KEY'
]

missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    print(f'❌ Missing environment variables: {missing}')
    exit(1)
else:
    print('✅ Configuration validated')
"

# Run tests
echo "🧪 Running tests..."
python3 test_bot.py

# Create systemd service file (optional)
if command -v systemctl &> /dev/null; then
    echo "🔧 Creating systemd service..."
    
    SERVICE_FILE="/etc/systemd/system/crypto-battle-bot.service"
    CURRENT_DIR=$(pwd)
    USER=$(whoami)
    
    sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Crypto Battle Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/python3 $CURRENT_DIR/crypto_battle_bot.py
Restart=always
RestartSec=10
Environment=PATH=/usr/bin:/usr/local/bin
Environment=PYTHONPATH=$CURRENT_DIR

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable crypto-battle-bot
    
    echo "✅ Systemd service created. You can now:"
    echo "   sudo systemctl start crypto-battle-bot    # Start the bot"
    echo "   sudo systemctl stop crypto-battle-bot     # Stop the bot"
    echo "   sudo systemctl status crypto-battle-bot   # Check status"
    echo "   sudo journalctl -u crypto-battle-bot -f   # View logs"
fi

# Create log directory
mkdir -p logs

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "🎯 Next steps:"
echo "1. Ensure your Discord bot has the necessary permissions in your server"
echo "2. Make sure your master wallet has sufficient Bitcoin for withdrawals"
echo "3. Start the bot:"
if command -v systemctl &> /dev/null; then
    echo "   sudo systemctl start crypto-battle-bot"
else
    echo "   python3 crypto_battle_bot.py"
fi
echo ""
echo "📊 Monitor the bot:"
echo "   tail -f crypto_battle_bot.log"
echo ""
echo "🔧 Test the bot in Discord:"
echo "   !help - Show available commands"
echo "   !balance - Check your balance"
echo ""
echo "⚠️  Remember: This bot handles real Bitcoin. Test thoroughly on testnet first!"
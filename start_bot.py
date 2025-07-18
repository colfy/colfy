#!/usr/bin/env python3
"""
Simple startup script for the Crypto Battle Bot
This script provides a simplified interface similar to the original bot structure
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the main bot
from crypto_battle_bot import CryptoBattleBot, ConfigurationError

def main():
    """Main function to start the bot"""
    try:
        # Check if .env file exists
        if not os.path.exists('.env'):
            print("❌ .env file not found. Please copy .env.example to .env and configure it.")
            sys.exit(1)
        
        # Create and run bot
        bot = CryptoBattleBot()
        
        print("🚀 Starting Crypto Battle Bot...")
        print("=" * 50)
        
        # Run the bot
        asyncio.run(bot.start(bot.config.discord_token))
        
    except ConfigurationError as e:
        print(f"❌ Configuration Error: {e}")
        print("Please check your .env file and ensure all required variables are set.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Bot shutdown requested by user")
    except Exception as e:
        print(f"❌ Fatal Error: {e}")
        logging.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
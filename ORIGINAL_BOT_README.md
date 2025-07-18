# Original Bot Compatibility Layer

This document describes the `original_bot.py` compatibility layer that maintains the exact same structure, commands, and functionality as the original bot while using the improved backend systems.

## Overview

The `original_bot.py` file is a drop-in replacement that:
- ✅ Maintains 100% compatibility with the original bot's user interface
- ✅ Uses improved rate limiting with `APIRateLimiter`
- ✅ Uses atomic file operations with `AtomicFileManager`
- ✅ Uses improved withdrawal system with proper error handling
- ✅ Uses environment variables for configuration
- ✅ Uses proper logging instead of print statements

## Key Features Maintained

### Original Discord Commands
- `!setup` - Create your crypto battle account
- `!deposit` - Get your unique deposit address
- `!balance` - Check your balance and battle stats
- `!withdraw` - Withdraw cryptocurrency to external address
- `!transactions` - View your transaction history
- `!roll` - Start a battle game
- `!help` - Show help information

### Original Discord UI Components
- `CryptoSelectView` - Cryptocurrency selection interface
- `GameModeView` - Game mode selection (dice/coinflip)
- `TipView` - Bot tip interface
- `OpponentModal` - Opponent selection for battles
- `WithdrawModal` - Withdrawal input interface
- `BattleRequestView` - Battle request acceptance/decline

### Original Game Logic
- **Dice Games**: Roll dice against opponents, higher roll wins
- **Coinflip Battles**: Call heads or tails, winner takes all
- **Ticket System**: Support ticket category integration
- **Battle Flow**: Complete battle request and execution system

### Original Data Structures
- `active_bets` - Active betting data
- `pending_confirmations` - Pending transaction confirmations
- `dice_games` - Active dice game sessions
- `opponent_requests` - Battle requests between players

### Original Configuration Constants
- `BET_CHANNEL_ID` - Discord channel for battles
- `TICKET_CATEGORY_NAME` - Support ticket category
- `CRYPTOCURRENCIES` - Supported crypto configuration
- `FIAT_RATES` - Currency conversion rates
- `DICE_SIDES`, `COINFLIP_OPTIONS` - Game parameters
- `MIN_BET_AMOUNT`, `MAX_BET_AMOUNT` - Betting limits

### Original File Names
- `user_wallets.json` - User wallet data
- `deposit_addresses.json` - Deposit address mappings

## Improvements Integrated

### 1. APIRateLimiter
- Robust async rate limiting with exponential backoff
- Concurrent request handling
- Per-endpoint rate limiting
- Automatic retry with backoff on rate limit errors

### 2. AtomicFileManager
- Atomic file operations to prevent corruption
- File locking for concurrent access safety
- Temporary file usage with atomic moves
- Comprehensive error handling

### 3. Improved Withdrawal System
- Comprehensive input validation
- Proper Bitcoin address validation
- Balance checking before withdrawal
- Transaction creation, signing, and broadcasting
- Detailed error messages and logging

### 4. Environment Configuration
- All sensitive data moved to environment variables
- Validation of required environment variables
- Fallback defaults for optional settings
- Support for both testnet and mainnet

### 5. Enhanced Logging
- Structured logging with timestamps
- Multiple log levels (INFO, WARNING, ERROR)
- File and console output
- Detailed error tracking

## Usage

### Starting the Bot

```bash
# Using the original bot compatibility layer
python3 original_bot.py

# Or using the startup script
python3 start_original_bot.py
```

### Environment Setup

Copy and configure the environment file:
```bash
cp .env.example .env
# Edit .env with your actual values
```

Required environment variables:
- `DISCORD_BOT_TOKEN` - Your Discord bot token
- `BLOCKCYPHER_API_TOKEN` - Your BlockCypher API token
- `MASTER_WALLET_ADDRESS` - Master wallet address for withdrawals
- `MASTER_WALLET_PRIVATE_KEY` - Master wallet private key

Optional environment variables:
- `BOT_PREFIX` - Command prefix (default: !)
- `BET_CHANNEL_ID` - Discord channel ID for battles
- `NETWORK` - Bitcoin network (test3/main, default: test3)
- `MIN_WITHDRAWAL_AMOUNT` - Minimum withdrawal in satoshis
- `MAX_WITHDRAWAL_AMOUNT` - Maximum withdrawal in satoshis
- `BTC_TIP_ADDRESS` - Bitcoin tip address
- `LTC_TIP_ADDRESS` - Litecoin tip address
- `TICKET_CATEGORY_NAME` - Discord ticket category name

## Testing

Run the test suite to verify functionality:
```bash
python3 test_original_bot.py
```

The test suite verifies:
- ✅ Module import functionality
- ✅ Class instantiation
- ✅ Bot initialization with backend systems
- ✅ Original constants and configuration
- ✅ UI component availability
- ✅ File operation functionality

## Compatibility Notes

### Data Format Compatibility
- Uses the same JSON structure for `user_wallets.json`
- Uses the same JSON structure for `deposit_addresses.json`
- Maintains the same user data fields and formats

### Discord Interface Compatibility
- Same embed styles and colors
- Same button labels and interactions
- Same command syntax and responses
- Same error messages and user feedback

### Game Mechanics Compatibility
- Same dice rolling mechanics (1-6)
- Same coinflip options (heads/tails)
- Same betting limits and validation
- Same battle flow and winner determination

## Migration from Original Bot

To migrate from the original bot to this compatibility layer:

1. **Stop the original bot**
2. **Backup your data files**:
   ```bash
   cp user_wallets.json user_wallets.json.backup
   cp deposit_addresses.json deposit_addresses.json.backup
   ```
3. **Update environment variables** (see .env.example)
4. **Start the compatibility layer**:
   ```bash
   python3 original_bot.py
   ```

The bot will automatically use your existing data files without any conversion needed.

## Architecture

### Backend Systems Integration
```
Original Bot Interface
├── Discord Commands (!setup, !deposit, !balance, etc.)
├── UI Components (Views, Modals, Buttons)
├── Game Logic (Dice, Coinflip, Battles)
└── Improved Backend Systems
    ├── APIRateLimiter (Rate limiting with backoff)
    ├── AtomicFileManager (Safe file operations)
    ├── BlockCypherHandler (Blockchain interactions)
    └── Enhanced Error Handling
```

### Data Flow
```
User Command → Original Command Handler → Improved Backend → Response
     ↓                    ↓                      ↓             ↓
Discord UI → Original UI Component → Safe File Ops → User Feedback
```

## Error Handling

The compatibility layer includes comprehensive error handling:

- **Configuration Errors**: Missing environment variables
- **Rate Limit Errors**: Automatic retry with exponential backoff
- **Withdrawal Errors**: Detailed validation and blockchain errors
- **Data Corruption Errors**: File corruption detection and recovery
- **Discord Errors**: Command and interaction error handling

## Logging

All operations are logged with appropriate levels:
- **INFO**: Normal operations, bot startup, successful transactions
- **WARNING**: Rate limiting, retries, non-critical issues
- **ERROR**: Failed operations, configuration issues, critical errors

Logs are written to both console and `crypto_battle_bot.log` file.

## Security Features

- Environment-based configuration for sensitive data
- Input validation for all user inputs
- Bitcoin address format validation
- Balance verification before withdrawals
- Rate limiting to prevent API abuse
- Atomic file operations to prevent data corruption

## Support

If you encounter any issues with the compatibility layer:

1. Check the logs in `crypto_battle_bot.log`
2. Verify your environment configuration
3. Run the test suite: `python3 test_original_bot.py`
4. Ensure all required dependencies are installed

The compatibility layer maintains the exact same user experience while providing improved reliability and security through the enhanced backend systems.
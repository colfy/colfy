# Crypto Battle Bot

A Discord bot for crypto battles with Bitcoin withdrawal functionality. Players can deposit Bitcoin, battle other players, and withdraw their winnings.

## 🚀 Features

- **Bitcoin Integration**: Real Bitcoin deposits and withdrawals using BlockCypher API
- **Battle System**: Challenge other players to battles with Bitcoin stakes  
- **Rate Limiting**: Robust rate limiting system to prevent API abuse
- **Data Safety**: Atomic file operations with locking to prevent data corruption
- **Error Handling**: Comprehensive error handling and logging
- **Security**: Environment-based configuration for sensitive data

## 📁 Bot Versions

This repository contains two versions of the bot:

### 1. **original_bot.py** - Compatibility Layer (Recommended)
- Maintains the exact same user interface and commands as the original bot
- Uses improved backend systems for withdrawal and rate limiting
- Drop-in replacement that fixes all the issues
- Compatible with existing `user_wallets.json` and `deposit_addresses.json` files

### 2. **crypto_battle_bot.py** - Modern Implementation  
- Completely rewritten with modern architecture
- Advanced features and monitoring capabilities
- Uses different data models and file structures

## 🛠 Setup

### Prerequisites

- Python 3.8+
- Discord Bot Token
- BlockCypher API Token
- Bitcoin wallet for master funds

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd crypto-battle-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your actual values
```

4. Run the bot:

**For the original bot (recommended):**
```bash
python original_bot.py
```

**For the modern implementation:**
```bash
python crypto_battle_bot.py
```

## 🔧 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_BOT_TOKEN` | Discord bot token | Yes |
| `BLOCKCYPHER_API_TOKEN` | BlockCypher API token | Yes |
| `MASTER_WALLET_ADDRESS` | Master wallet address for withdrawals | Yes |
| `MASTER_WALLET_PRIVATE_KEY` | Master wallet private key | Yes |
| `NETWORK` | Bitcoin network (test3/main) | No (default: test3) |
| `MIN_WITHDRAWAL_AMOUNT` | Minimum withdrawal in satoshis | No (default: 10000) |
| `MAX_WITHDRAWAL_AMOUNT` | Maximum withdrawal in satoshis | No (default: 1000000) |

## Commands

- `!balance` - Check your balance and battle stats
- `!deposit` - Get your unique deposit address
- `!withdraw <address> <amount>` - Withdraw Bitcoin to external address
- `!battle <@user> <amount>` - Challenge another player to a battle
- `!help` - Show help information

## Architecture

### Key Components

1. **APIRateLimiter**: Handles rate limiting with exponential backoff
2. **AtomicFileManager**: Provides atomic file operations with locking
3. **BlockCypherHandler**: Manages blockchain interactions
4. **CryptoBattleBot**: Main bot class with Discord integration
5. **BattleView**: Interactive Discord UI for battles

### Data Models

- **Player**: User data with balance, stats, and deposit address
- **Battle**: Battle information with participants and results

### Error Handling

Custom exception classes for different error types:
- `CryptoBattleBotError`: Base exception
- `RateLimitError`: Rate limiting issues
- `WithdrawalError`: Withdrawal failures
- `DataCorruptionError`: File corruption
- `ConfigurationError`: Invalid configuration

### Security Features

- Environment variable configuration
- Input validation for Bitcoin addresses
- Rate limiting to prevent API abuse
- Atomic file operations to prevent data corruption
- Comprehensive logging for audit trails

## File Structure

```
crypto_battle_bot.py     # Main improved bot file
original_bot.py          # Original bot compatibility layer
start_original_bot.py    # Original bot startup script
start_original_bot.sh    # Original bot shell startup script
test_original_bot.py     # Compatibility layer test suite
requirements.txt         # Python dependencies
.env.example            # Environment variables template
README.md               # This file
ORIGINAL_BOT_README.md  # Original bot compatibility documentation
user_wallets.json       # User wallet data (created automatically)
deposit_addresses.json  # Deposit address mapping (created automatically)
crypto_battle_bot.log   # Log file (created automatically)
backups/                # Automatic data backups
```

## Bot Versions

### Improved Bot (`crypto_battle_bot.py`)
- Modern architecture with data models
- Enhanced error handling and logging
- Optimized for production use
- Uses `players.json` and `battles.json`

### Original Bot Compatibility Layer (`original_bot.py`)
- Maintains exact original interface and commands
- Uses improved backend systems (rate limiting, file operations, withdrawals)
- 100% compatible with original bot data files
- Uses `user_wallets.json` and `deposit_addresses.json`
- See [ORIGINAL_BOT_README.md](ORIGINAL_BOT_README.md) for details

## Production Considerations

### Security

1. **Private Key Management**: Use hardware wallets or secure key management systems
2. **Address Generation**: Implement proper HD wallet address generation
3. **Rate Limiting**: Monitor and adjust rate limits based on usage
4. **Input Validation**: Add more comprehensive input validation
5. **Audit Logging**: Implement detailed audit logging for all transactions

### Scalability

1. **Database**: Replace JSON files with a proper database (PostgreSQL, MongoDB)
2. **Caching**: Implement Redis caching for frequently accessed data
3. **Queue System**: Use message queues for transaction processing
4. **Load Balancing**: Implement load balancing for multiple bot instances

### Monitoring

1. **Health Checks**: Implement health check endpoints
2. **Metrics**: Add Prometheus metrics for monitoring
3. **Alerting**: Set up alerts for critical errors
4. **Performance**: Monitor API response times and error rates

## Testing

### Testnet Usage

The bot is configured to use Bitcoin testnet by default. To get testnet Bitcoin:

1. Use a testnet faucet to get test coins
2. Send them to your master wallet address
3. Players can then battle with testnet Bitcoin

### Unit Tests

```bash
# Run tests (when implemented)
python -m pytest tests/
```

## Troubleshooting

### Common Issues

1. **Rate Limiting**: If you hit rate limits, the bot will automatically retry with exponential backoff
2. **Insufficient Balance**: Ensure the master wallet has sufficient funds for withdrawals
3. **Invalid Addresses**: The bot validates Bitcoin address formats before processing
4. **File Corruption**: Atomic operations prevent corruption, but backups are recommended

### Logs

Check `crypto_battle_bot.log` for detailed error information and debugging.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This bot handles real Bitcoin transactions. Use at your own risk. Always test thoroughly on testnet before using with real funds. The developers are not responsible for any loss of funds.

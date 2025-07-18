#!/usr/bin/env python3
"""
Crypto Battle Bot - A Discord bot for crypto battles with withdrawal functionality
Includes comprehensive fixes for withdrawal, rate limiting, and data management issues.
"""

import os
import json
import asyncio
import logging
import threading
import time
import random
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from contextlib import asynccontextmanager
import fcntl
import tempfile
import shutil

import discord
from discord.ext import commands, tasks
import requests
import aiofiles
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crypto_battle_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Custom Exception Classes
class CryptoBattleBotError(Exception):
    """Base exception for crypto battle bot errors"""
    pass

class RateLimitError(CryptoBattleBotError):
    """Raised when rate limit is exceeded"""
    pass

class WithdrawalError(CryptoBattleBotError):
    """Raised when withdrawal operations fail"""
    pass

class DataCorruptionError(CryptoBattleBotError):
    """Raised when data file corruption is detected"""
    pass

class ConfigurationError(CryptoBattleBotError):
    """Raised when configuration is invalid"""
    pass

# Environment Configuration with Validation
class Config:
    """Configuration manager with environment variable validation"""
    
    def __init__(self):
        self.validate_environment()
        
    def validate_environment(self):
        """Validate all required environment variables are present"""
        required_vars = [
            'BOT_TOKEN',
            'BLOCKCYPHER_API_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ConfigurationError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        logger.info("Environment configuration validated successfully")
    
    @property
    def discord_token(self) -> str:
        return os.getenv('BOT_TOKEN')
    
    @property
    def blockcypher_token(self) -> str:
        return os.getenv('BLOCKCYPHER_API_KEY')
    
    @property
    def bet_channel_id(self) -> int:
        return int(os.getenv('BET_CHANNEL_ID', '0'))
    
    @property
    def bot_prefix(self) -> str:
        return os.getenv('BOT_PREFIX', '!')
    
    @property
    def ltc_tip_address(self) -> str:
        return os.getenv('LTC_TIP_ADDRESS', '')
    
    @property
    def btc_tip_address(self) -> str:
        return os.getenv('BTC_TIP_ADDRESS', '')
    
    @property
    def network(self) -> str:
        return os.getenv('NETWORK', 'test3')  # Default to testnet
    
    @property
    def min_withdrawal_amount(self) -> int:
        return int(os.getenv('MIN_WITHDRAWAL_AMOUNT', '10000'))  # satoshis
    
    @property
    def max_withdrawal_amount(self) -> int:
        return int(os.getenv('MAX_WITHDRAWAL_AMOUNT', '1000000'))  # satoshis

# Rate Limiting System
@dataclass
class RateLimitBucket:
    """Rate limit bucket for tracking API calls"""
    requests: int = 0
    reset_time: float = 0
    lock: threading.Lock = None
    
    def __post_init__(self):
        if self.lock is None:
            self.lock = threading.Lock()

class APIRateLimiter:
    """Robust async rate limiter with exponential backoff and concurrent request handling"""
    
    def __init__(self, requests_per_hour: int = 200, requests_per_minute: int = 5):
        self.requests_per_hour = requests_per_hour
        self.requests_per_minute = requests_per_minute
        self.buckets: Dict[str, RateLimitBucket] = {}
        self.global_lock = asyncio.Lock()
        
        logger.info(f"Rate limiter initialized: {requests_per_hour}/hour, {requests_per_minute}/minute")
    
    async def acquire(self, endpoint: str = "default") -> None:
        """Acquire rate limit permission for an endpoint"""
        async with self.global_lock:
            await self._check_and_wait(endpoint)
    
    async def _check_and_wait(self, endpoint: str) -> None:
        """Check rate limits and wait if necessary"""
        current_time = time.time()
        
        # Initialize bucket if not exists
        if endpoint not in self.buckets:
            self.buckets[endpoint] = RateLimitBucket()
        
        bucket = self.buckets[endpoint]
        
        with bucket.lock:
            # Reset counters if time window has passed
            if current_time >= bucket.reset_time:
                bucket.requests = 0
                bucket.reset_time = current_time + 3600  # 1 hour window
            
            # Check if we're at the limit
            if bucket.requests >= self.requests_per_hour:
                wait_time = bucket.reset_time - current_time
                if wait_time > 0:
                    logger.warning(f"Rate limit reached for {endpoint}, waiting {wait_time:.2f} seconds")
                    await asyncio.sleep(wait_time)
                    # Reset after waiting
                    bucket.requests = 0
                    bucket.reset_time = time.time() + 3600
            
            # Increment request counter
            bucket.requests += 1
            
            # Add small delay between requests to avoid minute-level limits
            await asyncio.sleep(60 / self.requests_per_minute)
    
    async def with_backoff(self, func, *args, max_retries: int = 3, **kwargs):
        """Execute function with exponential backoff on rate limit errors"""
        for attempt in range(max_retries):
            try:
                await self.acquire()
                return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            except RateLimitError as e:
                if attempt == max_retries - 1:
                    raise e
                
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Rate limit error, retrying in {wait_time:.2f} seconds (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
        
        raise RateLimitError(f"Max retries ({max_retries}) exceeded")

# File Operations with Atomic Writes and Locking
class AtomicFileManager:
    """Manages atomic file operations with locking to prevent corruption"""
    
    @staticmethod
    @asynccontextmanager
    async def atomic_write(filepath: str):
        """Context manager for atomic file writes"""
        temp_path = None
        try:
            # Create temporary file in same directory
            dir_path = os.path.dirname(filepath) or '.'
            with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, delete=False, suffix='.tmp') as temp_file:
                temp_path = temp_file.name
                yield temp_file
            
            # Atomic move
            shutil.move(temp_path, filepath)
            logger.debug(f"Atomically wrote file: {filepath}")
            
        except Exception as e:
            # Clean up temp file on error
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            logger.error(f"Atomic write failed for {filepath}: {e}")
            raise
    
    @staticmethod
    async def load_json_with_lock(filepath: str, default: Any = None) -> Any:
        """Load JSON file with file locking"""
        if not os.path.exists(filepath):
            if default is not None:
                return default
            raise FileNotFoundError(f"File not found: {filepath}")
        
        try:
            async with aiofiles.open(filepath, 'r') as f:
                # Get file descriptor for locking
                fd = f.fileno()
                fcntl.flock(fd, fcntl.LOCK_SH)  # Shared lock for reading
                
                content = await f.read()
                data = json.loads(content)
                
                fcntl.flock(fd, fcntl.LOCK_UN)  # Unlock
                return data
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {filepath}: {e}")
            raise DataCorruptionError(f"Corrupted JSON file: {filepath}")
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
            raise
    
    @staticmethod
    async def save_json_with_lock(filepath: str, data: Any) -> None:
        """Save JSON file with atomic write and locking"""
        try:
            async with AtomicFileManager.atomic_write(filepath) as temp_file:
                # Get file descriptor for locking
                fd = temp_file.fileno()
                fcntl.flock(fd, fcntl.LOCK_EX)  # Exclusive lock for writing
                
                json.dump(data, temp_file, indent=2, ensure_ascii=False)
                temp_file.flush()
                os.fsync(fd)  # Force write to disk
                
                fcntl.flock(fd, fcntl.LOCK_UN)  # Unlock
                
            logger.debug(f"Saved JSON file: {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving {filepath}: {e}")
            raise

# Blockchain Transaction Handler
class BlockCypherHandler:
    """Handles BlockCypher API interactions with proper error handling"""
    
    def __init__(self, config: Config, rate_limiter: APIRateLimiter):
        self.config = config
        self.rate_limiter = rate_limiter
        self.base_url = f"https://api.blockcypher.com/v1/btc/{config.network}"
        
    async def get_address_balance(self, address: str) -> int:
        """Get address balance in satoshis"""
        try:
            url = f"{self.base_url}/addrs/{address}/balance"
            params = {'token': self.config.blockcypher_token}
            
            response = await self.rate_limiter.with_backoff(
                requests.get, url, params=params, timeout=30
            )
            
            if response.status_code == 429:
                raise RateLimitError("BlockCypher rate limit exceeded")
            
            response.raise_for_status()
            data = response.json()
            
            return data.get('balance', 0)
            
        except requests.RequestException as e:
            logger.error(f"Error getting balance for {address}: {e}")
            raise WithdrawalError(f"Failed to get balance: {e}")
    
    async def create_transaction(self, from_address: str, to_address: str, amount: int) -> Dict:
        """Create a new transaction"""
        try:
            url = f"{self.base_url}/txs/new"
            params = {'token': self.config.blockcypher_token}
            
            # Get current balance to calculate fee
            balance = await self.get_address_balance(from_address)
            if balance < amount:
                raise WithdrawalError(f"Insufficient balance: {balance} < {amount}")
            
            # Create transaction payload
            payload = {
                "inputs": [{"addresses": [from_address]}],
                "outputs": [{"addresses": [to_address], "value": amount}]
            }
            
            response = await self.rate_limiter.with_backoff(
                requests.post, url, json=payload, params=params, timeout=30
            )
            
            if response.status_code == 429:
                raise RateLimitError("BlockCypher rate limit exceeded")
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Error creating transaction: {e}")
            raise WithdrawalError(f"Failed to create transaction: {e}")
    
    async def sign_transaction(self, tx_skeleton: Dict, private_key: str) -> Dict:
        """Sign transaction with private key"""
        try:
            url = f"{self.base_url}/txs/send"
            params = {'token': self.config.blockcypher_token}
            
            # Add private key to transaction
            tx_skeleton['privkeys'] = [private_key]
            
            response = await self.rate_limiter.with_backoff(
                requests.post, url, json=tx_skeleton, params=params, timeout=30
            )
            
            if response.status_code == 429:
                raise RateLimitError("BlockCypher rate limit exceeded")
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Error signing transaction: {e}")
            raise WithdrawalError(f"Failed to sign transaction: {e}")
    
    async def broadcast_transaction(self, signed_tx: Dict) -> str:
        """Broadcast signed transaction"""
        try:
            # Transaction is already broadcast in sign_transaction for BlockCypher
            # Return the transaction hash
            return signed_tx.get('tx', {}).get('hash', '')
            
        except Exception as e:
            logger.error(f"Error broadcasting transaction: {e}")
            raise WithdrawalError(f"Failed to broadcast transaction: {e}")

# Data Models
@dataclass
class Player:
    """Player data model"""
    user_id: int
    username: str
    balance: int = 0
    wins: int = 0
    losses: int = 0
    total_battles: int = 0
    deposit_address: Optional[str] = None
    last_battle: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            'user_id': self.user_id,
            'username': self.username,
            'balance': self.balance,
            'wins': self.wins,
            'losses': self.losses,
            'total_battles': self.total_battles,
            'deposit_address': self.deposit_address,
            'last_battle': self.last_battle.isoformat() if self.last_battle else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Player':
        last_battle = None
        if data.get('last_battle'):
            last_battle = datetime.fromisoformat(data['last_battle'])
        
        return cls(
            user_id=data['user_id'],
            username=data['username'],
            balance=data.get('balance', 0),
            wins=data.get('wins', 0),
            losses=data.get('losses', 0),
            total_battles=data.get('total_battles', 0),
            deposit_address=data.get('deposit_address'),
            last_battle=last_battle
        )

@dataclass
class Battle:
    """Battle data model"""
    battle_id: str
    player1_id: int
    player2_id: int
    amount: int
    status: str = "pending"  # pending, active, completed, cancelled
    winner_id: Optional[int] = None
    created_at: datetime = None
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            'battle_id': self.battle_id,
            'player1_id': self.player1_id,
            'player2_id': self.player2_id,
            'amount': self.amount,
            'status': self.status,
            'winner_id': self.winner_id,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Battle':
        created_at = datetime.fromisoformat(data['created_at'])
        completed_at = None
        if data.get('completed_at'):
            completed_at = datetime.fromisoformat(data['completed_at'])
        
        return cls(
            battle_id=data['battle_id'],
            player1_id=data['player1_id'],
            player2_id=data['player2_id'],
            amount=data['amount'],
            status=data.get('status', 'pending'),
            winner_id=data.get('winner_id'),
            created_at=created_at,
            completed_at=completed_at
        )

# Main Bot Class
class CryptoBattleBot(commands.Bot):
    """Main Discord bot class with crypto battle functionality"""
    
    def __init__(self):
        # Initialize config first
        self.config = Config()
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        
        super().__init__(command_prefix=self.config.bot_prefix, intents=intents)
        
        # Initialize components
        self.rate_limiter = APIRateLimiter()
        self.blockchain_handler = BlockCypherHandler(self.config, self.rate_limiter)
        self.file_manager = AtomicFileManager()
        
        # Data storage
        self.players_file = 'players.json'
        self.battles_file = 'battles.json'
        self.deposit_addresses_file = 'deposit_addresses.json'
        
        # In-memory caches
        self.players: Dict[int, Player] = {}
        self.battles: Dict[str, Battle] = {}
        self.pending_battles: Dict[int, str] = {}  # user_id -> battle_id
        
        logger.info("CryptoBattleBot initialized")
    
    async def setup_hook(self):
        """Setup hook called when bot starts"""
        await self.load_data()
        self.check_deposits.start()
        logger.info("Bot setup completed")
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
    
    async def load_data(self):
        """Load all data from files"""
        try:
            # Load players
            players_data = await self.file_manager.load_json_with_lock(self.players_file, {})
            self.players = {
                int(user_id): Player.from_dict(data) 
                for user_id, data in players_data.items()
            }
            
            # Load battles
            battles_data = await self.file_manager.load_json_with_lock(self.battles_file, {})
            self.battles = {
                battle_id: Battle.from_dict(data)
                for battle_id, data in battles_data.items()
            }
            
            # Rebuild pending battles
            self.pending_battles = {
                battle.player1_id: battle.battle_id
                for battle in self.battles.values()
                if battle.status == 'pending'
            }
            
            logger.info(f"Loaded {len(self.players)} players and {len(self.battles)} battles")
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise
    
    async def save_data(self):
        """Save all data to files"""
        try:
            # Save players
            players_data = {
                str(user_id): player.to_dict()
                for user_id, player in self.players.items()
            }
            await self.file_manager.save_json_with_lock(self.players_file, players_data)
            
            # Save battles
            battles_data = {
                battle_id: battle.to_dict()
                for battle_id, battle in self.battles.items()
            }
            await self.file_manager.save_json_with_lock(self.battles_file, battles_data)
            
            logger.debug("Data saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            raise
    
    async def get_or_create_player(self, user: discord.User) -> Player:
        """Get existing player or create new one"""
        if user.id not in self.players:
            self.players[user.id] = Player(
                user_id=user.id,
                username=user.name
            )
            await self.save_data()
            logger.info(f"Created new player: {user.name} ({user.id})")
        
        return self.players[user.id]
    
    async def generate_deposit_address(self, user_id: int) -> str:
        """Generate a unique deposit address for a user"""
        try:
            # In a real implementation, you would generate a new address
            # For this example, we'll create a deterministic address based on user ID
            # This is NOT secure for production use
            
            # Load existing addresses
            addresses = await self.file_manager.load_json_with_lock(self.deposit_addresses_file, {})
            
            if str(user_id) in addresses:
                return addresses[str(user_id)]
            
            # Generate new address (placeholder - use proper address generation in production)
            # This is a simplified example
            address_seed = f"demo_master_address_{user_id}"
            address_hash = hashlib.sha256(address_seed.encode()).hexdigest()[:34]
            deposit_address = f"tb1{address_hash}"  # Testnet bech32 format
            
            # Save address
            addresses[str(user_id)] = deposit_address
            await self.file_manager.save_json_with_lock(self.deposit_addresses_file, addresses)
            
            logger.info(f"Generated deposit address for user {user_id}: {deposit_address}")
            return deposit_address
            
        except Exception as e:
            logger.error(f"Error generating deposit address: {e}")
            raise WithdrawalError(f"Failed to generate deposit address: {e}")
    
    async def send_withdrawal(self, user_id: int, address: str, amount: int) -> str:
        """Send withdrawal with comprehensive error handling"""
        try:
            player = self.players.get(user_id)
            if not player:
                raise WithdrawalError("Player not found")
            
            # Validate amount
            if amount < self.config.min_withdrawal_amount:
                raise WithdrawalError(f"Amount below minimum: {self.config.min_withdrawal_amount} satoshis")
            
            if amount > self.config.max_withdrawal_amount:
                raise WithdrawalError(f"Amount above maximum: {self.config.max_withdrawal_amount} satoshis")
            
            if player.balance < amount:
                raise WithdrawalError(f"Insufficient balance: {player.balance} < {amount}")
            
            # Validate address format (basic validation)
            if not self._is_valid_bitcoin_address(address):
                raise WithdrawalError("Invalid Bitcoin address format")
            
            logger.info(f"Processing withdrawal: {amount} satoshis to {address} for user {user_id}")
            
            # Create transaction (simplified for demo - in production use proper wallet management)
            tx_skeleton = await self.blockchain_handler.create_transaction(
                "demo_master_address",  # Replace with actual master wallet address
                address,
                amount
            )
            
            # Sign and broadcast transaction
            signed_tx = await self.blockchain_handler.sign_transaction(
                tx_skeleton,
                "demo_private_key"  # Replace with actual private key management
            )
            
            tx_hash = await self.blockchain_handler.broadcast_transaction(signed_tx)
            
            # Update player balance
            player.balance -= amount
            await self.save_data()
            
            logger.info(f"Withdrawal successful: {tx_hash}")
            return tx_hash
            
        except WithdrawalError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in withdrawal: {e}")
            raise WithdrawalError(f"Withdrawal failed: {e}")
    
    def _is_valid_bitcoin_address(self, address: str) -> bool:
        """Basic Bitcoin address validation"""
        if not address:
            return False
        
        # Basic length and format checks
        if len(address) < 26 or len(address) > 62:
            return False
        
        # Check for valid prefixes
        valid_prefixes = ['1', '3', 'bc1', 'tb1']  # Legacy, P2SH, Bech32 mainnet/testnet
        
        return any(address.startswith(prefix) for prefix in valid_prefixes)
    
    @tasks.loop(minutes=5)
    async def check_deposits(self):
        """Check for new deposits periodically"""
        try:
            for user_id, player in self.players.items():
                if player.deposit_address:
                    # Check balance (simplified - in production, track transactions)
                    balance = await self.blockchain_handler.get_address_balance(player.deposit_address)
                    if balance > 0:
                        # Credit player (this is simplified)
                        player.balance += balance
                        logger.info(f"Credited {balance} satoshis to player {user_id}")
            
            await self.save_data()
            
        except Exception as e:
            logger.error(f"Error checking deposits: {e}")
    
    # Discord Commands
    
    @commands.command(name='balance')
    async def balance_command(self, ctx):
        """Check player balance"""
        try:
            player = await self.get_or_create_player(ctx.author)
            
            embed = discord.Embed(
                title="💰 Your Balance",
                description=f"**{player.balance:,} satoshis**",
                color=discord.Color.gold()
            )
            embed.add_field(name="Wins", value=player.wins, inline=True)
            embed.add_field(name="Losses", value=player.losses, inline=True)
            embed.add_field(name="Total Battles", value=player.total_battles, inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in balance command: {e}")
            await ctx.send("❌ Error checking balance. Please try again.")
    
    @commands.command(name='deposit')
    async def deposit_command(self, ctx):
        """Get deposit address"""
        try:
            player = await self.get_or_create_player(ctx.author)
            
            if not player.deposit_address:
                player.deposit_address = await self.generate_deposit_address(ctx.author.id)
                await self.save_data()
            
            embed = discord.Embed(
                title="💳 Deposit Address",
                description=f"Send Bitcoin to this address to add funds to your account:",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Address",
                value=f"`{player.deposit_address}`",
                inline=False
            )
            embed.add_field(
                name="⚠️ Important",
                value="Only send Bitcoin to this address. Other cryptocurrencies will be lost!",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in deposit command: {e}")
            await ctx.send("❌ Error generating deposit address. Please try again.")
    
    @commands.command(name='withdraw')
    async def withdraw_command(self, ctx, address: str, amount: int):
        """Withdraw Bitcoin to external address"""
        try:
            if amount <= 0:
                await ctx.send("❌ Amount must be positive.")
                return
            
            # Send withdrawal
            tx_hash = await self.send_withdrawal(ctx.author.id, address, amount)
            
            embed = discord.Embed(
                title="✅ Withdrawal Successful",
                description=f"Sent **{amount:,} satoshis** to `{address}`",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Transaction Hash",
                value=f"`{tx_hash}`",
                inline=False
            )
            embed.add_field(
                name="Network",
                value=self.config.network,
                inline=True
            )
            
            await ctx.send(embed=embed)
            
        except WithdrawalError as e:
            await ctx.send(f"❌ Withdrawal failed: {e}")
        except Exception as e:
            logger.error(f"Error in withdraw command: {e}")
            await ctx.send("❌ Withdrawal failed. Please try again.")
    
    @commands.command(name='battle')
    async def battle_command(self, ctx, opponent: discord.Member, amount: int):
        """Challenge another player to a battle"""
        try:
            if opponent.id == ctx.author.id:
                await ctx.send("❌ You cannot battle yourself!")
                return
            
            if amount <= 0:
                await ctx.send("❌ Battle amount must be positive.")
                return
            
            # Check if players have pending battles
            if ctx.author.id in self.pending_battles:
                await ctx.send("❌ You already have a pending battle!")
                return
            
            if opponent.id in self.pending_battles:
                await ctx.send("❌ Your opponent already has a pending battle!")
                return
            
            # Get or create players
            player1 = await self.get_or_create_player(ctx.author)
            player2 = await self.get_or_create_player(opponent)
            
            # Check balances
            if player1.balance < amount:
                await ctx.send(f"❌ Insufficient balance! You have {player1.balance:,} satoshis.")
                return
            
            if player2.balance < amount:
                await ctx.send(f"❌ {opponent.mention} has insufficient balance for this battle.")
                return
            
            # Create battle
            battle_id = f"{ctx.author.id}_{opponent.id}_{int(time.time())}"
            battle = Battle(
                battle_id=battle_id,
                player1_id=ctx.author.id,
                player2_id=opponent.id,
                amount=amount
            )
            
            self.battles[battle_id] = battle
            self.pending_battles[ctx.author.id] = battle_id
            await self.save_data()
            
            # Create battle view
            view = BattleView(self, battle)
            
            embed = discord.Embed(
                title="⚔️ Battle Challenge",
                description=f"{ctx.author.mention} challenges {opponent.mention} to a battle!",
                color=discord.Color.red()
            )
            embed.add_field(name="Amount", value=f"{amount:,} satoshis", inline=True)
            embed.add_field(name="Status", value="Waiting for acceptance", inline=True)
            
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Error in battle command: {e}")
            await ctx.send("❌ Error creating battle. Please try again.")
    
    @commands.command(name='help')
    async def help_command(self, ctx):
        """Show help information"""
        embed = discord.Embed(
            title="🤖 Crypto Battle Bot Help",
            description="Battle other players with Bitcoin!",
            color=discord.Color.blue()
        )
        
        commands_info = [
            ("!balance", "Check your balance and stats"),
            ("!deposit", "Get your deposit address"),
            ("!withdraw <address> <amount>", "Withdraw Bitcoin to external address"),
            ("!battle <@user> <amount>", "Challenge another player to a battle"),
            ("!help", "Show this help message")
        ]
        
        for cmd, desc in commands_info:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        embed.add_field(
            name="⚠️ Important Notes",
            value="• All amounts are in satoshis (1 BTC = 100,000,000 satoshis)\n"
                  "• Minimum withdrawal: 10,000 satoshis\n"
                  "• Only send Bitcoin to deposit addresses",
            inline=False
        )
        
        await ctx.send(embed=embed)

# Discord Views for Interactive Components
class BattleView(discord.ui.View):
    """Interactive view for battle challenges"""
    
    def __init__(self, bot: CryptoBattleBot, battle: Battle):
        super().__init__(timeout=300)  # 5 minute timeout
        self.bot = bot
        self.battle = battle
    
    @discord.ui.button(label='Accept Battle', style=discord.ButtonStyle.green, emoji='⚔️')
    async def accept_battle(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Accept battle challenge"""
        try:
            if interaction.user.id != self.battle.player2_id:
                await interaction.response.send_message("❌ Only the challenged player can accept!", ephemeral=True)
                return
            
            if self.battle.status != 'pending':
                await interaction.response.send_message("❌ This battle is no longer available!", ephemeral=True)
                return
            
            # Get players
            player1 = self.bot.players[self.battle.player1_id]
            player2 = self.bot.players[self.battle.player2_id]
            
            # Check balances again
            if player1.balance < self.battle.amount or player2.balance < self.battle.amount:
                await interaction.response.send_message("❌ Insufficient balance for battle!", ephemeral=True)
                return
            
            # Deduct amounts
            player1.balance -= self.battle.amount
            player2.balance -= self.battle.amount
            
            # Determine winner (50/50 chance)
            winner = random.choice([player1, player2])
            loser = player2 if winner == player1 else player1
            
            # Award winnings (winner takes all)
            winner.balance += self.battle.amount * 2
            winner.wins += 1
            loser.losses += 1
            
            # Update battle
            self.battle.status = 'completed'
            self.battle.winner_id = winner.user_id
            self.battle.completed_at = datetime.now()
            
            # Update stats
            player1.total_battles += 1
            player2.total_battles += 1
            player1.last_battle = datetime.now()
            player2.last_battle = datetime.now()
            
            # Remove from pending
            if self.battle.player1_id in self.bot.pending_battles:
                del self.bot.pending_battles[self.battle.player1_id]
            
            await self.bot.save_data()
            
            # Create result embed
            embed = discord.Embed(
                title="⚔️ Battle Complete!",
                color=discord.Color.gold()
            )
            embed.add_field(
                name="Winner",
                value=f"<@{winner.user_id}> wins {self.battle.amount * 2:,} satoshis!",
                inline=False
            )
            embed.add_field(
                name="Battle Amount",
                value=f"{self.battle.amount:,} satoshis each",
                inline=True
            )
            embed.add_field(
                name="Total Prize",
                value=f"{self.battle.amount * 2:,} satoshis",
                inline=True
            )
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error accepting battle: {e}")
            await interaction.response.send_message("❌ Error processing battle. Please try again.", ephemeral=True)
    
    @discord.ui.button(label='Decline Battle', style=discord.ButtonStyle.red, emoji='❌')
    async def decline_battle(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Decline battle challenge"""
        try:
            if interaction.user.id != self.battle.player2_id:
                await interaction.response.send_message("❌ Only the challenged player can decline!", ephemeral=True)
                return
            
            # Update battle status
            self.battle.status = 'cancelled'
            
            # Remove from pending
            if self.battle.player1_id in self.bot.pending_battles:
                del self.bot.pending_battles[self.battle.player1_id]
            
            await self.bot.save_data()
            
            embed = discord.Embed(
                title="❌ Battle Declined",
                description=f"<@{self.battle.player2_id}> declined the battle challenge.",
                color=discord.Color.red()
            )
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error declining battle: {e}")
            await interaction.response.send_message("❌ Error processing decline. Please try again.", ephemeral=True)
    
    async def on_timeout(self):
        """Handle view timeout"""
        try:
            # Update battle status
            self.battle.status = 'cancelled'
            
            # Remove from pending
            if self.battle.player1_id in self.bot.pending_battles:
                del self.bot.pending_battles[self.battle.player1_id]
            
            await self.bot.save_data()
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
        except Exception as e:
            logger.error(f"Error handling timeout: {e}")

# Main execution
async def main():
    """Main function to run the bot"""
    try:
        bot = CryptoBattleBot()
        
        # Add error handler
        @bot.event
        async def on_command_error(ctx, error):
            if isinstance(error, commands.CommandNotFound):
                return  # Ignore unknown commands
            
            logger.error(f"Command error: {error}")
            await ctx.send("❌ An error occurred while processing your command.")
        
        # Start the bot
        await bot.start(bot.config.discord_token)
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Configuration error: {e}")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        print(f"Startup error: {e}")

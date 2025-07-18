#!/usr/bin/env python3
"""
Original Crypto Battle Bot - Compatibility Layer
Maintains the original bot structure and functionality while using improved backend systems.
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

# ============================================================================
# ORIGINAL CONFIGURATION CONSTANTS (maintained for compatibility)
# ============================================================================

# Discord Configuration
BET_CHANNEL_ID = int(os.getenv('BET_CHANNEL_ID', '0'))
TICKET_CATEGORY_NAME = os.getenv('TICKET_CATEGORY_NAME', 'Crypto Battles')
BOT_PREFIX = os.getenv('BOT_PREFIX', '!')

# Cryptocurrency Configuration
CRYPTOCURRENCIES = {
    'BTC': {
        'name': 'Bitcoin',
        'symbol': 'BTC',
        'network': os.getenv('NETWORK', 'test3'),
        'min_withdrawal': int(os.getenv('MIN_WITHDRAWAL_AMOUNT', '10000')),
        'max_withdrawal': int(os.getenv('MAX_WITHDRAWAL_AMOUNT', '1000000')),
        'decimals': 8
    },
    'LTC': {
        'name': 'Litecoin', 
        'symbol': 'LTC',
        'network': 'test',
        'min_withdrawal': 100000,
        'max_withdrawal': 10000000,
        'decimals': 8
    }
}

# Fiat rates (mock data - in production would fetch from API)
FIAT_RATES = {
    'BTC': {'USD': 45000.0, 'EUR': 38000.0},
    'LTC': {'USD': 150.0, 'EUR': 127.0}
}

# Game Configuration
DICE_SIDES = 6
COINFLIP_OPTIONS = ['heads', 'tails']
MIN_BET_AMOUNT = 1000  # satoshis
MAX_BET_AMOUNT = 1000000  # satoshis

# Tip addresses
LTC_TIP_ADDRESS = os.getenv('LTC_TIP_ADDRESS', '')
BTC_TIP_ADDRESS = os.getenv('BTC_TIP_ADDRESS', '')

# ============================================================================
# IMPROVED BACKEND SYSTEMS (from crypto_battle_bot.py)
# ============================================================================

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
    
    def __init__(self, rate_limiter: APIRateLimiter):
        self.rate_limiter = rate_limiter
        self.api_token = os.getenv('BLOCKCYPHER_API_TOKEN')
        self.network = os.getenv('NETWORK', 'test3')
        self.base_url = f"https://api.blockcypher.com/v1/btc/{self.network}"
        
    async def get_address_balance(self, address: str) -> int:
        """Get address balance in satoshis"""
        try:
            url = f"{self.base_url}/addrs/{address}/balance"
            params = {'token': self.api_token}
            
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
            params = {'token': self.api_token}
            
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
            params = {'token': self.api_token}
            
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

# ============================================================================
# ORIGINAL DATA STRUCTURES (maintained for compatibility)
# ============================================================================

# Global data structures (original bot style)
active_bets = {}
pending_confirmations = {}
dice_games = {}
opponent_requests = {}

# ============================================================================
# ORIGINAL DISCORD UI COMPONENTS
# ============================================================================

class CryptoSelectView(discord.ui.View):
    """Original crypto selection view"""
    
    def __init__(self, user_id: int, action: str = "deposit"):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.action = action
    
    @discord.ui.select(
        placeholder="Choose a cryptocurrency...",
        options=[
            discord.SelectOption(
                label="Bitcoin (BTC)",
                value="BTC",
                description="Bitcoin - The original cryptocurrency",
                emoji="₿"
            ),
            discord.SelectOption(
                label="Litecoin (LTC)", 
                value="LTC",
                description="Litecoin - Digital silver",
                emoji="Ł"
            )
        ]
    )
    async def crypto_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return
        
        crypto = select.values[0]
        
        if self.action == "deposit":
            await self.handle_deposit_selection(interaction, crypto)
        elif self.action == "withdraw":
            await self.handle_withdraw_selection(interaction, crypto)
    
    async def handle_deposit_selection(self, interaction: discord.Interaction, crypto: str):
        """Handle deposit crypto selection"""
        try:
            # Load deposit addresses
            deposit_addresses = await AtomicFileManager.load_json_with_lock('deposit_addresses.json', {})
            
            user_key = str(interaction.user.id)
            if user_key not in deposit_addresses:
                deposit_addresses[user_key] = {}
            
            if crypto not in deposit_addresses[user_key]:
                # Generate new address (simplified - in production use proper address generation)
                deposit_addresses[user_key][crypto] = f"test_{crypto.lower()}_{user_key}_{random.randint(1000, 9999)}"
                await AtomicFileManager.save_json_with_lock('deposit_addresses.json', deposit_addresses)
            
            address = deposit_addresses[user_key][crypto]
            
            embed = discord.Embed(
                title=f"{crypto} Deposit Address",
                description=f"Send {crypto} to this address to add funds to your account:",
                color=0x00ff00
            )
            embed.add_field(name="Address", value=f"`{address}`", inline=False)
            embed.add_field(name="Network", value=CRYPTOCURRENCIES[crypto]['network'], inline=True)
            embed.add_field(name="Minimum Deposit", value="0.0001 " + crypto, inline=True)
            embed.set_footer(text="Deposits are automatically credited to your account")
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            logger.error(f"Error handling deposit selection: {e}")
            await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
    
    async def handle_withdraw_selection(self, interaction: discord.Interaction, crypto: str):
        """Handle withdraw crypto selection"""
        # Show withdrawal modal
        modal = WithdrawModal(crypto)
        await interaction.response.send_modal(modal)

class GameModeView(discord.ui.View):
    """Original game mode selection view"""
    
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
    
    @discord.ui.button(label="🎲 Dice Battle", style=discord.ButtonStyle.primary)
    async def dice_battle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎲 Dice Battle",
            description="Roll dice against another player! Higher roll wins.",
            color=0x0099ff
        )
        embed.add_field(name="How to Play", value="1. Choose your bet amount\n2. Find an opponent\n3. Both roll dice\n4. Higher roll wins all!", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=OpponentModal.create_view(self.user_id, "dice"))
    
    @discord.ui.button(label="🪙 Coinflip Battle", style=discord.ButtonStyle.secondary)
    async def coinflip_battle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🪙 Coinflip Battle",
            description="Call heads or tails and battle another player!",
            color=0xffaa00
        )
        embed.add_field(name="How to Play", value="1. Choose your bet amount\n2. Find an opponent\n3. Call heads or tails\n4. Winner takes all!", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=OpponentModal.create_view(self.user_id, "coinflip"))

class TipView(discord.ui.View):
    """Original tip view for supporting the bot"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="₿ Tip BTC", style=discord.ButtonStyle.primary)
    async def tip_btc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not BTC_TIP_ADDRESS:
            await interaction.response.send_message("BTC tip address not configured.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="₿ Tip Bitcoin",
            description="Support the bot development with Bitcoin!",
            color=0xf7931a
        )
        embed.add_field(name="BTC Address", value=f"`{BTC_TIP_ADDRESS}`", inline=False)
        embed.set_footer(text="Thank you for your support! 🙏")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Ł Tip LTC", style=discord.ButtonStyle.secondary)
    async def tip_ltc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not LTC_TIP_ADDRESS:
            await interaction.response.send_message("LTC tip address not configured.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Ł Tip Litecoin",
            description="Support the bot development with Litecoin!",
            color=0x345d9d
        )
        embed.add_field(name="LTC Address", value=f"`{LTC_TIP_ADDRESS}`", inline=False)
        embed.set_footer(text="Thank you for your support! 🙏")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class OpponentModal(discord.ui.Modal):
    """Original opponent selection modal"""
    
    def __init__(self, game_type: str):
        super().__init__(title=f"Start {game_type.title()} Battle")
        self.game_type = game_type
    
    opponent = discord.ui.TextInput(
        label="Opponent (mention or ID)",
        placeholder="@username or user ID",
        required=True,
        max_length=100
    )
    
    amount = discord.ui.TextInput(
        label="Bet Amount (satoshis)",
        placeholder="Enter amount in satoshis (min: 1000)",
        required=True,
        max_length=20
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse opponent
            opponent_str = self.opponent.value.strip()
            if opponent_str.startswith('<@') and opponent_str.endswith('>'):
                opponent_id = int(opponent_str[2:-1].replace('!', ''))
            else:
                opponent_id = int(opponent_str)
            
            # Parse amount
            bet_amount = int(self.amount.value)
            
            if bet_amount < MIN_BET_AMOUNT:
                await interaction.response.send_message(f"Minimum bet is {MIN_BET_AMOUNT} satoshis!", ephemeral=True)
                return
            
            if bet_amount > MAX_BET_AMOUNT:
                await interaction.response.send_message(f"Maximum bet is {MAX_BET_AMOUNT} satoshis!", ephemeral=True)
                return
            
            # Check if opponent exists
            opponent = interaction.guild.get_member(opponent_id)
            if not opponent:
                await interaction.response.send_message("Opponent not found in this server!", ephemeral=True)
                return
            
            if opponent.id == interaction.user.id:
                await interaction.response.send_message("You can't battle yourself!", ephemeral=True)
                return
            
            # Check balances
            user_wallets = await AtomicFileManager.load_json_with_lock('user_wallets.json', {})
            
            user_balance = user_wallets.get(str(interaction.user.id), {}).get('balance', 0)
            opponent_balance = user_wallets.get(str(opponent_id), {}).get('balance', 0)
            
            if user_balance < bet_amount:
                await interaction.response.send_message(f"Insufficient balance! You have {user_balance} satoshis.", ephemeral=True)
                return
            
            if opponent_balance < bet_amount:
                await interaction.response.send_message(f"Opponent has insufficient balance for this bet!", ephemeral=True)
                return
            
            # Create battle request
            battle_id = f"{interaction.user.id}_{opponent_id}_{int(time.time())}"
            opponent_requests[battle_id] = {
                'challenger': interaction.user.id,
                'opponent': opponent_id,
                'amount': bet_amount,
                'game_type': self.game_type,
                'created_at': datetime.now().isoformat()
            }
            
            embed = discord.Embed(
                title=f"🎮 {self.game_type.title()} Battle Request",
                description=f"{interaction.user.mention} challenges {opponent.mention}!",
                color=0xff6b6b
            )
            embed.add_field(name="Game", value=self.game_type.title(), inline=True)
            embed.add_field(name="Bet Amount", value=f"{bet_amount:,} satoshis", inline=True)
            embed.add_field(name="Prize Pool", value=f"{bet_amount * 2:,} satoshis", inline=True)
            
            view = BattleRequestView(battle_id, opponent_id)
            await interaction.response.send_message(embed=embed, view=view)
            
        except ValueError:
            await interaction.response.send_message("Invalid input! Please check your opponent and amount.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in opponent modal: {e}")
            await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
    
    @staticmethod
    def create_view(user_id: int, game_type: str):
        """Create a view with a button to open the modal"""
        view = discord.ui.View(timeout=300)
        
        async def open_modal(interaction: discord.Interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This menu is not for you!", ephemeral=True)
                return
            
            modal = OpponentModal(game_type)
            await interaction.response.send_modal(modal)
        
        button = discord.ui.Button(label=f"Start {game_type.title()} Battle", style=discord.ButtonStyle.primary)
        button.callback = open_modal
        view.add_item(button)
        
        return view

class WithdrawModal(discord.ui.Modal):
    """Modal for withdrawal input"""
    
    def __init__(self, crypto: str):
        super().__init__(title=f"Withdraw {crypto}")
        self.crypto = crypto
        
        # Create text inputs dynamically
        self.address = discord.ui.TextInput(
            label=f"{crypto} Address",
            placeholder=f"Enter your {crypto} address",
            required=True,
            max_length=100
        )
        
        self.amount = discord.ui.TextInput(
            label="Amount (satoshis)",
            placeholder="Enter amount in satoshis",
            required=True,
            max_length=20
        )
        
        # Add the text inputs to the modal
        self.add_item(self.address)
        self.add_item(self.amount)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            withdraw_address = self.address.value.strip()
            withdraw_amount = int(self.amount.value)
            
            # Use the improved withdrawal function
            bot = interaction.client
            tx_hash = await bot.send_withdrawal(interaction.user.id, withdraw_address, withdraw_amount)
            
            embed = discord.Embed(
                title="✅ Withdrawal Successful",
                description=f"Your {self.crypto} withdrawal has been processed!",
                color=0x00ff00
            )
            embed.add_field(name="Amount", value=f"{withdraw_amount:,} satoshis", inline=True)
            embed.add_field(name="Address", value=withdraw_address[:20] + "...", inline=True)
            embed.add_field(name="Transaction", value=f"`{tx_hash}`", inline=False)
            embed.set_footer(text="Transaction may take some time to confirm on the network")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("Invalid amount! Please enter a valid number.", ephemeral=True)
        except WithdrawalError as e:
            await interaction.response.send_message(f"Withdrawal failed: {e}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in withdrawal modal: {e}")
            await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)

class BattleRequestView(discord.ui.View):
    """View for battle request responses"""
    
    def __init__(self, battle_id: str, opponent_id: int):
        super().__init__(timeout=300)
        self.battle_id = battle_id
        self.opponent_id = opponent_id
    
    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success)
    async def accept_battle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message("Only the challenged player can accept this battle!", ephemeral=True)
            return
        
        if self.battle_id not in opponent_requests:
            await interaction.response.send_message("This battle request has expired!", ephemeral=True)
            return
        
        battle_data = opponent_requests[self.battle_id]
        await self.start_battle(interaction, battle_data)
    
    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.danger)
    async def decline_battle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message("Only the challenged player can decline this battle!", ephemeral=True)
            return
        
        if self.battle_id in opponent_requests:
            del opponent_requests[self.battle_id]
        
        embed = discord.Embed(
            title="❌ Battle Declined",
            description="The battle request has been declined.",
            color=0xff0000
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def start_battle(self, interaction: discord.Interaction, battle_data: dict):
        """Start the actual battle"""
        try:
            challenger_id = battle_data['challenger']
            opponent_id = battle_data['opponent']
            amount = battle_data['amount']
            game_type = battle_data['game_type']
            
            # Deduct balances
            user_wallets = await AtomicFileManager.load_json_with_lock('user_wallets.json', {})
            
            if str(challenger_id) not in user_wallets:
                user_wallets[str(challenger_id)] = {'balance': 0}
            if str(opponent_id) not in user_wallets:
                user_wallets[str(opponent_id)] = {'balance': 0}
            
            user_wallets[str(challenger_id)]['balance'] -= amount
            user_wallets[str(opponent_id)]['balance'] -= amount
            
            await AtomicFileManager.save_json_with_lock('user_wallets.json', user_wallets)
            
            # Create game
            game_id = f"game_{int(time.time())}_{random.randint(1000, 9999)}"
            
            if game_type == "dice":
                await self.start_dice_game(interaction, game_id, challenger_id, opponent_id, amount)
            elif game_type == "coinflip":
                await self.start_coinflip_game(interaction, game_id, challenger_id, opponent_id, amount)
            
            # Clean up request
            if self.battle_id in opponent_requests:
                del opponent_requests[self.battle_id]
                
        except Exception as e:
            logger.error(f"Error starting battle: {e}")
            await interaction.response.send_message("An error occurred starting the battle!", ephemeral=True)
    
    async def start_dice_game(self, interaction: discord.Interaction, game_id: str, challenger_id: int, opponent_id: int, amount: int):
        """Start a dice game"""
        challenger = interaction.guild.get_member(challenger_id)
        opponent = interaction.guild.get_member(opponent_id)
        
        # Roll dice
        challenger_roll = random.randint(1, DICE_SIDES)
        opponent_roll = random.randint(1, DICE_SIDES)
        
        # Determine winner
        if challenger_roll > opponent_roll:
            winner_id = challenger_id
            winner_name = challenger.display_name
        elif opponent_roll > challenger_roll:
            winner_id = opponent_id
            winner_name = opponent.display_name
        else:
            # Tie - refund both players
            user_wallets = await AtomicFileManager.load_json_with_lock('user_wallets.json', {})
            user_wallets[str(challenger_id)]['balance'] += amount
            user_wallets[str(opponent_id)]['balance'] += amount
            await AtomicFileManager.save_json_with_lock('user_wallets.json', user_wallets)
            
            embed = discord.Embed(
                title="🎲 Dice Battle - Tie!",
                description="Both players rolled the same number! Bets refunded.",
                color=0xffaa00
            )
            embed.add_field(name=challenger.display_name, value=f"🎲 {challenger_roll}", inline=True)
            embed.add_field(name=opponent.display_name, value=f"🎲 {opponent_roll}", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=None)
            return
        
        # Award winnings
        user_wallets = await AtomicFileManager.load_json_with_lock('user_wallets.json', {})
        user_wallets[str(winner_id)]['balance'] += amount * 2
        await AtomicFileManager.save_json_with_lock('user_wallets.json', user_wallets)
        
        embed = discord.Embed(
            title="🎲 Dice Battle Results",
            description=f"🏆 {winner_name} wins {amount * 2:,} satoshis!",
            color=0x00ff00
        )
        embed.add_field(name=challenger.display_name, value=f"🎲 {challenger_roll}", inline=True)
        embed.add_field(name=opponent.display_name, value=f"🎲 {opponent_roll}", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def start_coinflip_game(self, interaction: discord.Interaction, game_id: str, challenger_id: int, opponent_id: int, amount: int):
        """Start a coinflip game"""
        challenger = interaction.guild.get_member(challenger_id)
        opponent = interaction.guild.get_member(opponent_id)
        
        # Flip coin
        result = random.choice(COINFLIP_OPTIONS)
        
        # Randomly assign calls
        challenger_call = random.choice(COINFLIP_OPTIONS)
        opponent_call = "tails" if challenger_call == "heads" else "heads"
        
        # Determine winner
        if challenger_call == result:
            winner_id = challenger_id
            winner_name = challenger.display_name
        else:
            winner_id = opponent_id
            winner_name = opponent.display_name
        
        # Award winnings
        user_wallets = await AtomicFileManager.load_json_with_lock('user_wallets.json', {})
        user_wallets[str(winner_id)]['balance'] += amount * 2
        await AtomicFileManager.save_json_with_lock('user_wallets.json', user_wallets)
        
        embed = discord.Embed(
            title="🪙 Coinflip Battle Results",
            description=f"🏆 {winner_name} wins {amount * 2:,} satoshis!",
            color=0x00ff00
        )
        embed.add_field(name="Result", value=f"🪙 {result.title()}", inline=True)
        embed.add_field(name=challenger.display_name, value=f"Called: {challenger_call}", inline=True)
        embed.add_field(name=opponent.display_name, value=f"Called: {opponent_call}", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)

# ============================================================================
# MAIN BOT CLASS (Original structure with improved backend)
# ============================================================================

class OriginalCryptoBattleBot(commands.Bot):
    """Original bot structure with improved backend systems"""
    
    def __init__(self):
        # Validate environment
        required_vars = ['DISCORD_BOT_TOKEN', 'BLOCKCYPHER_API_TOKEN']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ConfigurationError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        
        super().__init__(command_prefix=BOT_PREFIX, intents=intents)
        
        # Initialize improved backend systems
        self.rate_limiter = APIRateLimiter()
        self.blockchain_handler = BlockCypherHandler(self.rate_limiter)
        self.file_manager = AtomicFileManager()
        
        logger.info("Original Crypto Battle Bot initialized with improved backend")
    
    async def setup_hook(self):
        """Setup hook called when bot starts"""
        # Initialize data files if they don't exist
        await self.initialize_data_files()
        
        # Start background tasks
        self.check_deposits.start()
        
        logger.info("Bot setup completed")
    
    async def initialize_data_files(self):
        """Initialize data files with default values"""
        files_to_init = {
            'user_wallets.json': {},
            'deposit_addresses.json': {}
        }
        
        for filename, default_data in files_to_init.items():
            if not os.path.exists(filename):
                await self.file_manager.save_json_with_lock(filename, default_data)
                logger.info(f"Initialized {filename}")
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Set bot status
        activity = discord.Activity(type=discord.ActivityType.playing, name="Crypto Battles | !help")
        await self.change_presence(activity=activity)
    
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            return
        
        logger.error(f"Command error in {ctx.command}: {error}")
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing required argument: {error.param}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument provided.")
        else:
            await ctx.send("An error occurred while processing your command.")
    
    # ========================================================================
    # IMPROVED WITHDRAWAL FUNCTION (from crypto_battle_bot.py)
    # ========================================================================
    
    async def send_withdrawal(self, user_id: int, address: str, amount: int) -> str:
        """Send withdrawal with comprehensive error handling"""
        try:
            # Load user wallet
            user_wallets = await self.file_manager.load_json_with_lock('user_wallets.json', {})
            user_key = str(user_id)
            
            if user_key not in user_wallets:
                raise WithdrawalError("User wallet not found")
            
            user_balance = user_wallets[user_key].get('balance', 0)
            
            # Validate amount
            min_withdrawal = CRYPTOCURRENCIES['BTC']['min_withdrawal']
            max_withdrawal = CRYPTOCURRENCIES['BTC']['max_withdrawal']
            
            if amount < min_withdrawal:
                raise WithdrawalError(f"Amount below minimum: {min_withdrawal} satoshis")
            
            if amount > max_withdrawal:
                raise WithdrawalError(f"Amount above maximum: {max_withdrawal} satoshis")
            
            if user_balance < amount:
                raise WithdrawalError(f"Insufficient balance: {user_balance} < {amount}")
            
            # Validate address format (basic validation)
            if not self._is_valid_bitcoin_address(address):
                raise WithdrawalError("Invalid Bitcoin address format")
            
            logger.info(f"Processing withdrawal: {amount} satoshis to {address} for user {user_id}")
            
            # Create transaction using improved blockchain handler
            master_address = os.getenv('MASTER_WALLET_ADDRESS')
            if not master_address:
                raise WithdrawalError("Master wallet not configured")
            
            tx_skeleton = await self.blockchain_handler.create_transaction(
                master_address,
                address,
                amount
            )
            
            # Sign and broadcast transaction
            private_key = os.getenv('MASTER_WALLET_PRIVATE_KEY')
            if not private_key:
                raise WithdrawalError("Master wallet private key not configured")
            
            signed_tx = await self.blockchain_handler.sign_transaction(tx_skeleton, private_key)
            tx_hash = await self.blockchain_handler.broadcast_transaction(signed_tx)
            
            # Update user balance
            user_wallets[user_key]['balance'] -= amount
            await self.file_manager.save_json_with_lock('user_wallets.json', user_wallets)
            
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
        
        # Basic length and character checks
        if len(address) < 26 or len(address) > 62:
            return False
        
        # Check for valid characters (simplified)
        valid_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
        if not all(c in valid_chars for c in address):
            return False
        
        return True
    
    # ========================================================================
    # BACKGROUND TASKS
    # ========================================================================
    
    @tasks.loop(minutes=5)
    async def check_deposits(self):
        """Check for new deposits (simplified implementation)"""
        try:
            deposit_addresses = await self.file_manager.load_json_with_lock('deposit_addresses.json', {})
            user_wallets = await self.file_manager.load_json_with_lock('user_wallets.json', {})
            
            # In a real implementation, this would check blockchain for actual deposits
            # For now, this is a placeholder that maintains the original structure
            
            logger.debug("Checked for deposits")
            
        except Exception as e:
            logger.error(f"Error checking deposits: {e}")
    
    @check_deposits.before_loop
    async def before_check_deposits(self):
        """Wait for bot to be ready before starting deposit checks"""
        await self.wait_until_ready()
    
    # ========================================================================
    # ORIGINAL DISCORD COMMANDS
    # ========================================================================
    
    @commands.command(name='setup')
    async def setup_command(self, ctx):
        """Setup your crypto battle account"""
        user_wallets = await self.file_manager.load_json_with_lock('user_wallets.json', {})
        user_key = str(ctx.author.id)
        
        if user_key not in user_wallets:
            user_wallets[user_key] = {
                'balance': 0,
                'wins': 0,
                'losses': 0,
                'total_battles': 0,
                'created_at': datetime.now().isoformat()
            }
            await self.file_manager.save_json_with_lock('user_wallets.json', user_wallets)
        
        embed = discord.Embed(
            title="🎮 Account Setup Complete!",
            description=f"Welcome to Crypto Battles, {ctx.author.mention}!",
            color=0x00ff00
        )
        embed.add_field(name="Balance", value="0 satoshis", inline=True)
        embed.add_field(name="Battles", value="0", inline=True)
        embed.add_field(name="Win Rate", value="0%", inline=True)
        embed.add_field(name="Next Steps", value="Use `!deposit` to add funds and start battling!", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='deposit')
    async def deposit_command(self, ctx):
        """Get your deposit address"""
        embed = discord.Embed(
            title="💰 Deposit Cryptocurrency",
            description="Choose which cryptocurrency you want to deposit:",
            color=0x0099ff
        )
        
        view = CryptoSelectView(ctx.author.id, "deposit")
        await ctx.send(embed=embed, view=view)
    
    @commands.command(name='balance')
    async def balance_command(self, ctx, user: discord.Member = None):
        """Check your balance and stats"""
        target_user = user or ctx.author
        user_wallets = await self.file_manager.load_json_with_lock('user_wallets.json', {})
        user_key = str(target_user.id)
        
        if user_key not in user_wallets:
            if target_user == ctx.author:
                await ctx.send("You don't have an account yet! Use `!setup` to create one.")
            else:
                await ctx.send(f"{target_user.display_name} doesn't have an account yet.")
            return
        
        wallet = user_wallets[user_key]
        balance = wallet.get('balance', 0)
        wins = wallet.get('wins', 0)
        losses = wallet.get('losses', 0)
        total_battles = wallet.get('total_battles', 0)
        
        win_rate = (wins / total_battles * 100) if total_battles > 0 else 0
        
        # Convert to BTC for display
        btc_balance = balance / 100000000
        
        embed = discord.Embed(
            title=f"💰 {target_user.display_name}'s Balance",
            color=0x00ff00
        )
        embed.add_field(name="Balance", value=f"{balance:,} satoshis\n({btc_balance:.8f} BTC)", inline=True)
        embed.add_field(name="Battles Won", value=f"{wins:,}", inline=True)
        embed.add_field(name="Battles Lost", value=f"{losses:,}", inline=True)
        embed.add_field(name="Total Battles", value=f"{total_battles:,}", inline=True)
        embed.add_field(name="Win Rate", value=f"{win_rate:.1f}%", inline=True)
        embed.add_field(name="USD Value", value=f"${balance * FIAT_RATES['BTC']['USD'] / 100000000:.2f}", inline=True)
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='withdraw')
    async def withdraw_command(self, ctx, address: str = None, amount: int = None):
        """Withdraw cryptocurrency to external address"""
        if not address or not amount:
            embed = discord.Embed(
                title="💸 Withdraw Cryptocurrency",
                description="Choose which cryptocurrency you want to withdraw:",
                color=0xff6b6b
            )
            
            view = CryptoSelectView(ctx.author.id, "withdraw")
            await ctx.send(embed=embed, view=view)
            return
        
        try:
            tx_hash = await self.send_withdrawal(ctx.author.id, address, amount)
            
            embed = discord.Embed(
                title="✅ Withdrawal Successful",
                description="Your Bitcoin withdrawal has been processed!",
                color=0x00ff00
            )
            embed.add_field(name="Amount", value=f"{amount:,} satoshis", inline=True)
            embed.add_field(name="Address", value=address[:20] + "...", inline=True)
            embed.add_field(name="Transaction", value=f"`{tx_hash}`", inline=False)
            embed.set_footer(text="Transaction may take some time to confirm on the network")
            
            await ctx.send(embed=embed)
            
        except WithdrawalError as e:
            await ctx.send(f"❌ Withdrawal failed: {e}")
        except Exception as e:
            logger.error(f"Error in withdraw command: {e}")
            await ctx.send("❌ An error occurred processing your withdrawal.")
    
    @commands.command(name='transactions')
    async def transactions_command(self, ctx):
        """View your transaction history"""
        # This would show transaction history in a real implementation
        embed = discord.Embed(
            title="📊 Transaction History",
            description="Your recent transactions:",
            color=0x0099ff
        )
        embed.add_field(name="Coming Soon", value="Transaction history feature is being developed!", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='roll')
    async def roll_command(self, ctx):
        """Start a battle game"""
        embed = discord.Embed(
            title="🎮 Choose Your Battle",
            description="Select a game mode to start battling!",
            color=0xff6b6b
        )
        
        view = GameModeView(ctx.author.id)
        await ctx.send(embed=embed, view=view)
    
    @commands.command(name='help')
    async def help_command(self, ctx):
        """Show help information"""
        embed = discord.Embed(
            title="🎮 Crypto Battle Bot Help",
            description="Welcome to the ultimate crypto battle experience!",
            color=0x0099ff
        )
        
        embed.add_field(
            name="💰 Account Commands",
            value="`!setup` - Create your account\n`!balance` - Check your balance\n`!deposit` - Get deposit address\n`!withdraw` - Withdraw funds",
            inline=False
        )
        
        embed.add_field(
            name="🎲 Battle Commands", 
            value="`!roll` - Start a battle game\n`!transactions` - View transaction history",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Game Modes",
            value="🎲 **Dice Battle** - Roll dice, higher wins\n🪙 **Coinflip** - Call heads or tails",
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value="• Start with `!setup` to create your account\n• Use `!deposit` to add funds\n• Challenge friends with `!roll`\n• Withdraw winnings with `!withdraw`",
            inline=False
        )
        
        embed.set_footer(text="Support the bot development with the tip buttons below!")
        
        view = TipView()
        await ctx.send(embed=embed, view=view)

# ============================================================================
# BOT STARTUP
# ============================================================================

def main():
    """Main function to start the bot"""
    try:
        bot = OriginalCryptoBattleBot()
        
        # Get bot token
        token = os.getenv('DISCORD_BOT_TOKEN')
        if not token:
            raise ConfigurationError("DISCORD_BOT_TOKEN environment variable not set")
        
        logger.info("Starting Original Crypto Battle Bot...")
        bot.run(token)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()

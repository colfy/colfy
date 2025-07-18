#!/usr/bin/env python3
"""
Crypto Battle Bot Monitoring Script
Provides health checks and basic statistics
"""

import os
import json
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any

import requests
from dotenv import load_dotenv

load_dotenv()

class BotMonitor:
    """Monitor bot health and statistics"""
    
    def __init__(self):
        self.players_file = 'players.json'
        self.battles_file = 'battles.json'
        self.log_file = 'crypto_battle_bot.log'
    
    def load_json_file(self, filepath: str) -> Dict[str, Any]:
        """Load JSON file safely"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return {}
    
    def get_player_stats(self) -> Dict[str, Any]:
        """Get player statistics"""
        players_data = self.load_json_file(self.players_file)
        
        if not players_data:
            return {
                'total_players': 0,
                'total_balance': 0,
                'active_players': 0,
                'avg_balance': 0
            }
        
        total_balance = sum(player.get('balance', 0) for player in players_data.values())
        active_players = sum(1 for player in players_data.values() 
                           if player.get('last_battle') and 
                           datetime.fromisoformat(player['last_battle']) > 
                           datetime.now() - timedelta(days=7))
        
        avg_balance = total_balance // len(players_data) if players_data else 0
        
        return {
            'total_players': len(players_data),
            'total_balance': total_balance,
            'active_players': active_players,
            'avg_balance': avg_balance
        }
    
    def get_battle_stats(self) -> Dict[str, Any]:
        """Get battle statistics"""
        battles_data = self.load_json_file(self.battles_file)
        
        if not battles_data:
            return {
                'total_battles': 0,
                'completed_battles': 0,
                'pending_battles': 0,
                'cancelled_battles': 0,
                'total_volume': 0
            }
        
        completed = sum(1 for battle in battles_data.values() 
                       if battle.get('status') == 'completed')
        pending = sum(1 for battle in battles_data.values() 
                     if battle.get('status') == 'pending')
        total_volume = sum(battle.get('amount', 0) * 2 for battle in battles_data.values() 
                          if battle.get('status') == 'completed')
        
        cancelled = len(battles_data) - completed - pending
        
        return {
            'total_battles': len(battles_data),
            'completed_battles': completed,
            'pending_battles': pending,
            'cancelled_battles': cancelled,
            'total_volume': total_volume
        }
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get log file statistics"""
        if not os.path.exists(self.log_file):
            return {
                'log_size': 0,
                'recent_errors': 0,
                'last_activity': None
            }
        
        try:
            stat = os.stat(self.log_file)
            log_size = stat.st_size
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            
            # Count recent errors (last 1000 lines)
            recent_errors = 0
            try:
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                    recent_lines = lines[-1000:] if len(lines) > 1000 else lines
                    recent_errors = sum(1 for line in recent_lines if 'ERROR' in line)
            except Exception:
                pass
            
            return {
                'log_size': log_size,
                'log_size_mb': round(log_size / (1024 * 1024), 2),
                'recent_errors': recent_errors,
                'last_activity': last_modified.isoformat()
            }
        except Exception as e:
            return {
                'log_size': 0,
                'recent_errors': 0,
                'last_activity': None,
                'error': str(e)
            }
    
    def check_api_health(self) -> Dict[str, Any]:
        """Check BlockCypher API health"""
        api_token = os.getenv('BLOCKCYPHER_API_TOKEN')
        network = os.getenv('NETWORK', 'test3')
        
        if not api_token:
            return {'status': 'error', 'message': 'No API token configured'}
        
        try:
            url = f"https://api.blockcypher.com/v1/btc/{network}"
            params = {'token': api_token}
            
            start_time = time.time()
            response = requests.get(url, params=params, timeout=10)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'status': 'healthy',
                    'response_time': round(response_time, 3),
                    'height': data.get('height', 'unknown'),
                    'network': network
                }
            else:
                return {
                    'status': 'error',
                    'status_code': response.status_code,
                    'message': response.text[:200]
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def generate_report(self) -> str:
        """Generate comprehensive monitoring report"""
        print("🔍 Generating Crypto Battle Bot Health Report...")
        
        # Get all statistics
        player_stats = self.get_player_stats()
        battle_stats = self.get_battle_stats()
        log_stats = self.get_log_stats()
        api_health = self.check_api_health()
        
        
        # Generate report
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        CRYPTO BATTLE BOT HEALTH REPORT                      ║
║                        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                        ║
╠══════════════════════════════════════════════════════════════════════════════╣

📊 PLAYER STATISTICS
├─ Total Players: {player_stats['total_players']:,}
├─ Active Players (7 days): {player_stats['active_players']:,}
├─ Total Balance: {player_stats['total_balance']:,} satoshis
└─ Average Balance: {player_stats['avg_balance']:,} satoshis

⚔️  BATTLE STATISTICS
├─ Total Battles: {battle_stats['total_battles']:,}
├─ Completed: {battle_stats['completed_battles']:,}
├─ Pending: {battle_stats['pending_battles']:,}
├─ Cancelled: {battle_stats['cancelled_battles']:,}
└─ Total Volume: {battle_stats['total_volume']:,} satoshis

📝 LOG STATISTICS
├─ Log Size: {log_stats['log_size_mb']} MB
├─ Recent Errors: {log_stats['recent_errors']}
└─ Last Activity: {log_stats.get('last_activity', 'Unknown')}

🌐 API HEALTH
├─ Status: {api_health['status'].upper()}
├─ Network: {api_health.get('network', 'Unknown')}
├─ Response Time: {api_health.get('response_time', 'N/A')}s
└─ Block Height: {api_health.get('height', 'Unknown')}

╚══════════════════════════════════════════════════════════════════════════════╝
"""
        
        # Add warnings if needed
        warnings = []
        
        if log_stats['recent_errors'] > 10:
            warnings.append(f"⚠️  High error count: {log_stats['recent_errors']} recent errors")
        
        if api_health['status'] != 'healthy':
            warnings.append(f"⚠️  API issues: {api_health.get('message', 'Unknown error')}")
        
        if battle_stats['pending_battles'] > 10:
            warnings.append(f"⚠️  Many pending battles: {battle_stats['pending_battles']}")
        
        if log_stats.get('log_size_mb', 0) > 100:
            warnings.append(f"⚠️  Large log file: {log_stats['log_size_mb']} MB")
        
        if warnings:
            report += "\n🚨 WARNINGS:\n"
            for warning in warnings:
                report += f"   {warning}\n"
        else:
            report += "\n✅ No warnings detected. Bot appears healthy!\n"
        
        return report
    
    def save_report(self, report: str, filename: str = None):
        """Save report to file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"health_report_{timestamp}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write(report)
            print(f"📄 Report saved to: {filename}")
        except Exception as e:
            print(f"❌ Error saving report: {e}")

async def main():
    """Main monitoring function"""
    monitor = BotMonitor()
    
    # Generate and display report
    report = monitor.generate_report()
    print(report)
    
    # Save report
    monitor.save_report(report)
    
    # Check if we should send alerts (placeholder for future implementation)
    # This could integrate with Discord webhooks, email, Slack, etc.

if __name__ == "__main__":
    asyncio.run(main())

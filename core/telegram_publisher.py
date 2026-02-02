"""
Telegram Publisher - Smart Telegram Channel Manager
Handles posting to Telegram with duplicate detection and rate limiting
"""
import os
import json
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging


class TelegramPublisher:
    """Manages intelligent posting to Telegram channel with anti-spam."""
    
    def __init__(self, telegram_notifier, logger: Optional[logging.Logger] = None):
        self.notifier = telegram_notifier
        self.logger = logger or logging.getLogger(__name__)
        self.state_file = "telegram_state.json"
        self.load_state()
    
    def load_state(self):
        """Load previous state to track what was sent."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
            except:
                self.state = self._empty_state()
        else:
            self.state = self._empty_state()
    
    def save_state(self):
        """Save current state."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save Telegram state: {e}")
    
    def _empty_state(self) -> Dict:
        """Create empty state."""
        return {
            'last_post_time': None,
            'last_configs_hash': None,
            'post_count_today': 0,
            'last_reset_date': datetime.now().strftime('%Y-%m-%d')
        }
    
    def _reset_daily_counter(self):
        """Reset daily post counter if new day."""
        today = datetime.now().strftime('%Y-%m-%d')
        if self.state['last_reset_date'] != today:
            self.state['post_count_today'] = 0
            self.state['last_reset_date'] = today
            self.save_state()
    
    def _calculate_configs_hash(self, configs: List[str]) -> str:
        """Calculate hash of configs to detect duplicates."""
        # Sort configs to ensure consistent hash
        sorted_configs = sorted(configs)
        combined = '|'.join(sorted_configs)
        return hashlib.md5(combined.encode()).hexdigest()
    
    def should_post(self, configs: List[str]) -> tuple[bool, str]:
        """
        Determine if we should post to Telegram.
        Returns: (should_post, reason)
        """
        self._reset_daily_counter()
        
        # Check if configs changed
        current_hash = self._calculate_configs_hash(configs)
        if current_hash == self.state.get('last_configs_hash'):
            return False, "Configs unchanged - no new content to post"
        
        # Check daily limit (max 3 batches per day = 15 configs total)
        if self.state['post_count_today'] >= 3:
            return False, "Daily limit reached (3 batches/day)"
        
        # Check time since last post (minimum 2 hours)
        if self.state.get('last_post_time'):
            try:
                last_post = datetime.fromisoformat(self.state['last_post_time'])
                time_diff = datetime.now() - last_post
                if time_diff < timedelta(hours=2):
                    hours_left = 2 - (time_diff.total_seconds() / 3600)
                    return False, f"Too soon - wait {hours_left:.1f} more hours"
            except:
                pass
        
        return True, "Ready to post"
    
    async def post_configs(self, results: List[Dict]) -> bool:
        """
        Post top 5 configs to Telegram channel individually.
        
        Args:
            results: List of test results (already sorted by speed)
        
        Returns:
            bool: True if posted successfully
        """
        if not self.notifier.is_enabled:
            self.logger.info("Telegram not configured - skipping post")
            return False
        
        # Extract config URIs for duplicate detection
        configs = [r.get('uri', '') for r in results if r.get('uri')]
        should_post, reason = self.should_post(configs)
        
        if not should_post:
            self.logger.info(f"Skipping Telegram post: {reason}")
            return False
        
        # Get top 5 configs
        top_configs = results[:5]
        
        if not top_configs:
            self.logger.warning("No configs to post")
            return False
        
        # Post each config individually
        success_count = 0
        for config in top_configs:
            message = self._build_config_message(config)
            success = await self.notifier.send_message(message)
            
            if success:
                success_count += 1
                # Small delay between posts to avoid rate limiting
                await asyncio.sleep(2)
            else:
                self.logger.warning(f"Failed to post config: {config.get('uri', 'unknown')[:50]}...")
        
        if success_count > 0:
            # Update state
            self.state['last_post_time'] = datetime.now().isoformat()
            self.state['last_configs_hash'] = self._calculate_configs_hash(configs)
            self.state['post_count_today'] += 1
            self.save_state()
            self.logger.info(f"✅ Successfully posted {success_count}/5 configs to Telegram channel")
            return True
        
        return False
    
    def _build_config_message(self, result: Dict) -> str:
        """Build formatted message for individual config."""
        protocol = result.get('protocol', 'UNKNOWN').upper()
        ping = result.get('ping', 0)
        download_speed = result.get('download_speed', 0)
        country = result.get('country', 'Unknown')
        uri = result.get('uri', '')
        
        # Convert speed to MB/s (download_speed is in bytes/sec)
        speed_mb = download_speed / (1024 * 1024) if download_speed > 0 else 0
        
        # Build message with exact format requested
        message = f"""🟢 New Config Found

🔐 Protocol: {protocol}
📶 Ping: {ping:.0f} ms
⚡ Speed: {speed_mb:.2f} MB/s
🌍 Location: {country}

📋 Config (Tap to copy):
{uri}

🤝 نشر حداکثری این کانال برای دسترسی هموطنامون به اینترنت بر عهده ماست
🕊️ اینترنت آزاد برای مردم وطنم
🆔 @vpnbuying"""
        
        return message


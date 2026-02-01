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
        
        # Check daily limit (max 10 posts per day to avoid spam)
        if self.state['post_count_today'] >= 10:
            return False, "Daily limit reached (10 posts/day)"
        
        # Check time since last post (minimum 30 minutes)
        if self.state.get('last_post_time'):
            try:
                last_post = datetime.fromisoformat(self.state['last_post_time'])
                time_diff = datetime.now() - last_post
                if time_diff < timedelta(minutes=30):
                    minutes_left = 30 - int(time_diff.total_seconds() / 60)
                    return False, f"Too soon - wait {minutes_left} more minutes"
            except:
                pass
        
        return True, "Ready to post"
    
    async def post_update(self, stats: Dict, subscription_link: str) -> bool:
        """
        Post update to Telegram channel with smart formatting.
        
        Args:
            stats: Statistics dictionary with test results
            subscription_link: Direct link to subscription file
        
        Returns:
            bool: True if posted successfully
        """
        if not self.notifier.is_enabled:
            self.logger.info("Telegram not configured - skipping post")
            return False
        
        # Extract config URIs for duplicate detection
        configs = stats.get('config_uris', [])
        should_post, reason = self.should_post(configs)
        
        if not should_post:
            self.logger.info(f"Skipping Telegram post: {reason}")
            return False
        
        # Build message
        message = self._build_message(stats, subscription_link)
        
        # Send to Telegram
        success = await self.notifier.send_message(message)
        
        if success:
            # Update state
            self.state['last_post_time'] = datetime.now().isoformat()
            self.state['last_configs_hash'] = self._calculate_configs_hash(configs)
            self.state['post_count_today'] += 1
            self.save_state()
            self.logger.info("✅ Successfully posted to Telegram channel")
        
        return success
    
    def _build_message(self, stats: Dict, subscription_link: str) -> str:
        """Build formatted Telegram message."""
        total_working = stats.get('total_working', 0)
        avg_ping = stats.get('avg_ping', 0)
        avg_download = stats.get('avg_download', 0)
        protocols = stats.get('protocols', {})
        last_updated = stats.get('last_updated', datetime.now().isoformat())
        
        # Format timestamp
        try:
            dt = datetime.fromisoformat(last_updated)
            time_str = dt.strftime('%Y-%m-%d %H:%M')
        except:
            time_str = last_updated[:16]
        
        # Build protocol distribution
        protocol_lines = []
        for proto, count in sorted(protocols.items(), key=lambda x: x[1], reverse=True):
            protocol_lines.append(f"  • {proto.upper()}: {count}")
        protocol_text = '\n'.join(protocol_lines) if protocol_lines else "  • N/A"
        
        # Build message
        message = f"""🚀 **V2Ray Configs - Auto Update**

━━━━━━━━━━━━━━━━━━━

✅ **Working Servers:** {total_working}
📊 **Avg Ping:** {avg_ping:.0f} ms
⚡ **Avg Speed:** {avg_download:.1f} Mbps
🕐 **Updated:** {time_str}

📱 **Protocols:**
{protocol_text}

━━━━━━━━━━━━━━━━━━━

📥 **Import to Your App:**

**v2rayN/NG/Matsuri:**
```
{subscription_link}
```

**Clash/ClashX:**
```
https://raw.githubusercontent.com/Shayanthn/V2ray-Tester-Pro/main/subscriptions/clash.yaml
```

**SingBox:**
```
https://raw.githubusercontent.com/Shayanthn/V2ray-Tester-Pro/main/subscriptions/singbox.json
```

━━━━━━━━━━━━━━━━━━━

⭐ **How to Use:**
1. Copy the link for your app
2. Add subscription in app settings
3. Update to get all configs

🔄 Auto-updates every 30 minutes
🔒 All configs tested & verified

🤖 Powered by V2Ray Tester Pro
"""
        return message

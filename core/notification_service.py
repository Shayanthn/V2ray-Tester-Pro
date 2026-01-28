"""
Notification Service - v5.4.0
Centralized notification handling with rate limiting and batching.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from collections import deque
import time
import os

from utils.telegram_notifier import TelegramNotifier
from core.rate_limiter import RateLimiter


@dataclass
class NotificationMessage:
    """Represents a notification message."""
    content: str
    priority: int = 1  # 1 = normal, 2 = high, 3 = critical
    channel: str = 'telegram'
    created_at: float = field(default_factory=time.time)
    retries: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


class NotificationService:
    """
    Centralized notification service with:
    - Rate limiting to prevent Telegram API bans
    - Batching to reduce message spam
    - Deduplication to avoid repeat notifications
    - Priority queue for important messages
    - Async background processing
    """
    
    # Telegram limits: 30 messages/second to different chats, 1 message/second to same chat
    TELEGRAM_RATE_LIMIT = 1.0  # 1 message per second
    BATCH_WINDOW = 1800.0  # 30 minutes
    MAX_BATCH_SIZE = 5  # Max messages to send per batch (per 30 min)
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        # Telegram notifier
        self.telegram = TelegramNotifier(logger=self.logger)
        # Rate limiter
        self.rate_limiter = RateLimiter(logger=self.logger)
        # Message buffer (all priorities)
        self._batch_buffer: List[NotificationMessage] = []
        # Deduplication
        self._sent_hashes: Set[str] = set()
        self._dedup_window = 3600  # 1 hour deduplication window
        self._hash_timestamps: Dict[str, float] = {}
        # Persistence file for cross-run deduplication
        self._sent_file = os.path.join(os.getcwd(), 'notifications', 'sent_hashes.json')
        try:
            self._load_sent_hashes()
        except Exception:
            # non-fatal
            pass
        # State
        self._running = False
        self._batch_task: Optional[asyncio.Task] = None
        # Statistics
        self.stats = {
            'total_sent': 0,
            'total_failed': 0,
            'total_batched': 0,
            'total_deduplicated': 0,
            'total_rate_limited': 0
        }
    
    @property
    def is_enabled(self) -> bool:
        """Check if notifications are enabled."""
        return self.telegram.is_enabled
    
    def _hash_message(self, content: str) -> str:
        """Create a hash for deduplication."""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _is_duplicate(self, content: str) -> bool:
        """Check if message was recently sent."""
        msg_hash = self._hash_message(content)
        now = time.time()
        
        # Clean old hashes
        expired = [h for h, t in self._hash_timestamps.items() 
                   if now - t > self._dedup_window]
        for h in expired:
            self._sent_hashes.discard(h)
            del self._hash_timestamps[h]
        
        # Check if duplicate
        if msg_hash in self._sent_hashes:
            return True
        
        # Record new hash
        self._sent_hashes.add(msg_hash)
        self._hash_timestamps[msg_hash] = now
        # Persist cross-run record
        try:
            self._persist_sent_hash(msg_hash)
        except Exception:
            self.logger.debug("Failed to persist sent hash")
        return False

    def _load_sent_hashes(self) -> None:
        """Load sent hashes from disk for cross-run deduplication."""
        try:
            os.makedirs(os.path.dirname(self._sent_file), exist_ok=True)
            if os.path.exists(self._sent_file):
                import json
                with open(self._sent_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        now = time.time()
                        for h in data:
                            self._sent_hashes.add(h)
                            self._hash_timestamps[h] = now
        except Exception as e:
            self.logger.debug(f"Could not load sent hashes: {e}")

    def _persist_sent_hash(self, h: str) -> None:
        """Append a sent hash to the persisted file (atomic write)."""
        try:
            import json, tempfile
            os.makedirs(os.path.dirname(self._sent_file), exist_ok=True)
            existing = []
            if os.path.exists(self._sent_file):
                with open(self._sent_file, 'r', encoding='utf-8') as f:
                    try:
                        existing = json.load(f) or []
                    except Exception:
                        existing = []
            if h in existing:
                return
            existing.append(h)
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self._sent_file))
            with os.fdopen(fd, 'w', encoding='utf-8') as tf:
                json.dump(existing, tf)
            os.replace(tmp, self._sent_file)
        except Exception as e:
            self.logger.debug(f"Failed to persist sent hash: {e}")
    
    async def send_config_notification(self, result: Dict[str, Any], 
                                         is_new: bool = True) -> bool:
        """
        Send a notification about a found config.
        
        Args:
            result: Test result dictionary
            is_new: Whether this is a newly discovered config
            
        Returns:
            True if notification was queued/sent successfully
        """
        if not self.is_enabled:
            return False
        
        uri = result.get('uri', '')
        if not uri:
            return False
        
        # Format message
        proto = result.get('protocol', 'unknown').upper()
        ping = result.get('ping', 0)
        dl_speed = result.get('download_speed', 0)
        country = result.get('country', 'Unknown')
        is_fragment = result.get('fragment_mode', False)
        custom_sni = result.get('custom_sni', '')
        
        # Build feature tags
        feature_tags = []
        if is_fragment:
            feature_tags.append("🛡️ **Mode**: Anti-Filter (Fragment)")
        if custom_sni:
            feature_tags.append(f"🎭 **SNI Bypass**: {custom_sni}")
        if dl_speed > 5:
            feature_tags.append("🚀 **High Speed**")
        
        tags_str = "\n".join(feature_tags) + ("\n" if feature_tags else "")
        
        status_emoji = "🆕" if is_new else "🟢"
        
        msg = (
            f"{status_emoji} **{'New ' if is_new else ''}Config Found**\n\n"
            f"🔐 **Protocol**: {proto}\n"
            f"📶 **Ping**: {ping} ms\n"
            f"⚡ **Speed**: {dl_speed} MB/s\n"
            f"🌍 **Location**: {country}\n"
            f"{tags_str}"
            f"📋 **Config** (Tap to copy):\n"
            f"`{uri}`\n\n"
            f"🤝 نشر حداکثری این کانال برای دسترسی هموطنامون به اینترنت بر عهده ماست\n"
            f"🕊️ اینترنت آزاد برای مردم وطنم"
        )
        # اطمینان از اینکه فقط یکبار @vpnbuying در انتهای پیام باشد
        msg = msg.strip()
        if not msg.endswith("@vpnbuying"):
            msg = f"{msg}\n\n📢 @vpnbuying"
        return await self.send(msg, priority=2 if is_new else 1)
    
    async def send_summary(self, found: int, failed: int, 
                            blacklisted: int, duration: float) -> bool:
        """Send a test run summary notification."""
        if not self.is_enabled:
            return False
        
        msg = (
            f"📊 **Test Run Complete**\n\n"
            f"✅ Found: {found}\n"
            f"❌ Failed: {failed}\n"
            f"🚫 Blacklisted: {blacklisted}\n"
            f"⏱️ Duration: {duration:.1f}s\n\n"
            f"🔗 View results: subscriptions/"
        )
        
        return await self.send(msg, priority=1)
    
    async def send_alert(self, title: str, message: str, 
                          severity: str = 'warning') -> bool:
        """Send an alert notification."""
        if not self.is_enabled:
            return False
        
        emoji_map = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌',
            'critical': '🚨'
        }
        emoji = emoji_map.get(severity, '📢')
        priority = {'info': 1, 'warning': 2, 'error': 3, 'critical': 3}.get(severity, 1)
        
        msg = f"{emoji} **{title}**\n\n{message}"
        
        return await self.send(msg, priority=priority)
    
    async def send(self, content: str, priority: int = 1, skip_dedup: bool = False) -> bool:
        """
        Queue a message for sending (all priorities batched, deduped, anti-spam).
        """
        if not self.is_enabled:
            return False
        # همیشه @vpnbuying به انتها اضافه کن (اگر نبود)
        if "@vpnbuying" not in content:
            content = f"{content}\n\n📢 @vpnbuying"
        # Deduplication
        if not skip_dedup and self._is_duplicate(content):
            self.stats['total_deduplicated'] += 1
            self.logger.debug("Skipping duplicate notification")
            return False
        msg = NotificationMessage(
            content=content,
            priority=priority,
            channel='telegram'
        )
        self._batch_buffer.append(msg)
        return True
    
    async def start(self) -> None:
        """Start the notification service background worker."""
        if self._running:
            return
        self._running = True
        self._batch_task = asyncio.create_task(self._batch_loop())
        self.logger.info("Notification service started")
    
    async def stop(self) -> None:
        """Stop the notification service gracefully."""
        self._running = False
        # Flush remaining messages
        await self._flush_batch()
        # Cancel worker task
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
        self.logger.info(f"Notification service stopped. Stats: {self.stats}")
    
    # حذف کامل worker_loop و صف priority
    
    async def _batch_loop(self) -> None:
        """Process batched messages periodically (all priorities)."""
        while self._running:
            try:
                await asyncio.sleep(self.BATCH_WINDOW)
                await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Batch processor error: {e}")
    
    async def _flush_batch(self) -> None:
        """Send up to MAX_BATCH_SIZE new messages per batch window (all priorities, sorted by priority desc)."""
        if not self._batch_buffer:
            return
        # فقط پیام‌های غیرتکراری را ارسال کن (دوباره چک کن)
        unique_msgs = []
        seen_hashes = set()
        for msg in self._batch_buffer:
            h = self._hash_message(msg.content)
            if h not in seen_hashes:
                unique_msgs.append(msg)
                seen_hashes.add(h)
        # اولویت بالا اول
        unique_msgs.sort(key=lambda m: -m.priority)
        to_send = unique_msgs[:self.MAX_BATCH_SIZE]
        # حذف پیام‌های ارسال شده از بافر
        self._batch_buffer = [msg for msg in self._batch_buffer if msg not in to_send]
        # ارسال پیام‌ها
        for msg in to_send:
            await self._send_message(msg)
    
    async def _send_message(self, msg: NotificationMessage) -> bool:
        """Actually send a message with rate limiting."""
        allowed = await self.rate_limiter.acquire('telegram', 'telegram')
        if not allowed:
            self.stats['total_rate_limited'] += 1
            # پیام را دوباره به بافر اضافه کن برای batch بعدی
            if msg.retries < msg.max_retries:
                msg.retries += 1
                self._batch_buffer.append(msg)
            return False
        # Send via Telegram
        try:
            success = await self.telegram.send_message(msg.content)
            if success:
                self.stats['total_sent'] += 1
                self.rate_limiter.record_success('telegram')
                return True
            else:
                self.stats['total_failed'] += 1
                self.rate_limiter.record_failure('telegram')
                return False
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
            self.stats['total_failed'] += 1
            self.rate_limiter.record_failure('telegram')
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get notification service statistics."""
        return {
            **self.stats,
            'pending_batch': len(self._batch_buffer),
            'rate_limiter': self.rate_limiter.get_stats()
        }


# Global notification service instance
_notification_service: Optional[NotificationService] = None

def get_notification_service() -> NotificationService:
    """Get the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service

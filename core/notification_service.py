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
    BATCH_WINDOW = 10.0  # Seconds to batch messages
    MAX_BATCH_SIZE = 5  # Max messages to batch together
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
        # Telegram notifier
        self.telegram = TelegramNotifier(logger=self.logger)
        
        # Rate limiter
        self.rate_limiter = RateLimiter(logger=self.logger)
        
        # Message queues
        self._pending_queue: asyncio.Queue = asyncio.Queue()
        self._priority_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._batch_buffer: List[NotificationMessage] = []
        
        # Deduplication
        self._sent_hashes: Set[str] = set()
        self._dedup_window = 3600  # 1 hour deduplication window
        self._hash_timestamps: Dict[str, float] = {}
        
        # State
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
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
        return False
    
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
            f"{tags_str}\n"
            f"📋 **Config** (Tap to copy):\n"
            f"`{uri}`\n\n"
            f"🤝 نشر حداکثری این کانال برای دسترسی هموطنامون به اینترنت بر عهده ماست\n"
            f"🕊️ اینترنت آزاد برای مردم وطنم"
        )
        
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
    
    async def send(self, content: str, priority: int = 1, 
                    skip_dedup: bool = False) -> bool:
        """
        Queue a message for sending.
        
        Args:
            content: Message content
            priority: 1 = normal, 2 = high, 3 = critical
            skip_dedup: Skip deduplication check
            
        Returns:
            True if message was queued successfully
        """
        if not self.is_enabled:
            return False
        
        # Check for duplicates (unless skipped)
        if not skip_dedup and self._is_duplicate(content):
            self.stats['total_deduplicated'] += 1
            self.logger.debug("Skipping duplicate notification")
            return False
        
        msg = NotificationMessage(
            content=content,
            priority=priority,
            channel='telegram'
        )
        
        # High priority messages go to priority queue
        if priority >= 2:
            await self._priority_queue.put((-priority, time.time(), msg))
        else:
            self._batch_buffer.append(msg)
        
        return True
    
    async def start(self) -> None:
        """Start the notification service background workers."""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        self._batch_task = asyncio.create_task(self._batch_loop())
        self.logger.info("Notification service started")
    
    async def stop(self) -> None:
        """Stop the notification service gracefully."""
        self._running = False
        
        # Flush remaining messages
        await self._flush_batch()
        
        # Cancel worker tasks
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info(f"Notification service stopped. Stats: {self.stats}")
    
    async def _worker_loop(self) -> None:
        """Process priority queue messages."""
        while self._running:
            try:
                # Check priority queue first
                try:
                    _, _, msg = await asyncio.wait_for(
                        self._priority_queue.get(),
                        timeout=1.0
                    )
                    await self._send_message(msg)
                except asyncio.TimeoutError:
                    continue
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Notification worker error: {e}")
                await asyncio.sleep(1)
    
    async def _batch_loop(self) -> None:
        """Process batched messages periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.BATCH_WINDOW)
                await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Batch processor error: {e}")
    
    async def _flush_batch(self) -> None:
        """Send all batched messages."""
        if not self._batch_buffer:
            return
        
        # Take up to MAX_BATCH_SIZE messages
        batch = self._batch_buffer[:self.MAX_BATCH_SIZE]
        self._batch_buffer = self._batch_buffer[self.MAX_BATCH_SIZE:]
        
        if len(batch) == 1:
            # Single message, send directly
            await self._send_message(batch[0])
        else:
            # Multiple messages, combine into batch
            self.stats['total_batched'] += len(batch)
            combined = "📦 **Batch Update** ({} configs)\n\n".format(len(batch))
            combined += "\n---\n".join(msg.content[:500] for msg in batch[:5])
            
            batch_msg = NotificationMessage(content=combined)
            await self._send_message(batch_msg)
    
    async def _send_message(self, msg: NotificationMessage) -> bool:
        """Actually send a message with rate limiting."""
        # Rate limiting
        allowed = await self.rate_limiter.acquire('telegram', 'telegram')
        if not allowed:
            self.stats['total_rate_limited'] += 1
            # Re-queue for retry
            if msg.retries < msg.max_retries:
                msg.retries += 1
                await self._priority_queue.put((-msg.priority, time.time(), msg))
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
            'pending_priority': self._priority_queue.qsize(),
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

import os
import logging
import asyncio
import aiohttp
from typing import Optional

class TelegramNotifier:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        
        raw_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        # Smart handler for Chat ID:
        # If user provides a username like "vpnbuying" without '@', and it's not a number, add '@'
        if raw_chat_id and not raw_chat_id.startswith('@') and not raw_chat_id.lstrip('-').isdigit():
            self.chat_id = f"@{raw_chat_id}"
            self.logger.info(f"Auto-corrected Telegram Chat ID to: {self.chat_id}")
        else:
            self.chat_id = raw_chat_id
            
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None

    @property
    def is_enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send_message(self, text: str) -> bool:
        if not self.is_enabled:
            self.logger.debug("Telegram notification skipped: Credentials not found.")
            return False

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    'chat_id': self.chat_id,
                    'text': text,
                    'parse_mode': 'Markdown'
                }
                async with session.post(f"{self.base_url}/sendMessage", json=payload) as response:
                    if response.status == 200:
                        self.logger.info("Telegram message sent successfully.")
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to send Telegram message. Status: {response.status}, Error: {error_text}")
                        return False
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {str(e)}")
            return False

    async def send_file(self, file_path: str, caption: str = "") -> bool:
        if not self.is_enabled:
            self.logger.debug("Telegram file upload skipped: Credentials not found.")
            return False

        if not os.path.exists(file_path):
            self.logger.error(f"File not found for Telegram upload: {file_path}")
            return False

        try:
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('chat_id', self.chat_id)
                    data.add_field('document', f, filename=os.path.basename(file_path))
                    if caption:
                        data.add_field('caption', caption)
                    
                    async with session.post(f"{self.base_url}/sendDocument", data=data) as response:
                        if response.status == 200:
                            self.logger.info(f"File {os.path.basename(file_path)} sent to Telegram successfully.")
                            return True
                        else:
                            error_text = await response.text()
                            self.logger.error(f"Failed to send file to Telegram. Status: {response.status}, Error: {error_text}")
                            return False
        except Exception as e:
            self.logger.error(f"Error sending file to Telegram: {str(e)}")
            return False

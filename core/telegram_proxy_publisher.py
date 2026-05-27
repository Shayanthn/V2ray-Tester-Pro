import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote


class TelegramProxyPublisher:
    DAILY_POST_LIMIT = 30

    def __init__(
        self,
        telegram_notifier,
        logger: Optional[logging.Logger] = None,
        working_file: str = "working_telegram_proxies.json",
        state_file: str = "telegram_proxy_state.json",
    ):
        self.notifier = telegram_notifier
        self.logger = logger or logging.getLogger(__name__)
        self.working_file = working_file
        self.state_file = state_file
        self.channel_handle = os.getenv("TELEGRAM_CHANNEL_HANDLE", "@vpnbuying") or "@vpnbuying"
        self.state = self._load_state()

    def _empty_state(self) -> Dict[str, Any]:
        return {
            "last_post_time": None,
            "post_count_today": 0,
            "last_reset_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "sent_proxy_hashes": [],
        }

    def _empty_working_data(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "proxies": [],
            "last_updated": now,
            "total_proxies": 0,
            "created_at": now,
        }

    def _load_state(self) -> Dict[str, Any]:
        if not os.path.exists(self.state_file):
            state = self._empty_state()
            self._save_state(state)
            return state

        try:
            with open(self.state_file, "r", encoding="utf-8") as file:
                loaded = json.load(file)
            state = {**self._empty_state(), **loaded}
            return state
        except Exception:
            state = self._empty_state()
            self._save_state(state)
            return state

    def _save_state(self, state: Optional[Dict[str, Any]] = None):
        payload = state if state is not None else self.state
        with open(self.state_file, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

    def _load_working_data(self) -> Dict[str, Any]:
        if not os.path.exists(self.working_file):
            data = self._empty_working_data()
            self._save_working_data(data)
            return data

        try:
            with open(self.working_file, "r", encoding="utf-8") as file:
                loaded = json.load(file)
            data = self._empty_working_data()
            data.update(loaded)
            if not isinstance(data.get("proxies"), list):
                data["proxies"] = []
            return data
        except Exception:
            data = self._empty_working_data()
            self._save_working_data(data)
            return data

    def _save_working_data(self, data: Dict[str, Any]):
        with open(self.working_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

    @staticmethod
    def _proxy_hash(proxy: Dict[str, Any]) -> str:
        raw = "|".join(
            [
                proxy.get("type", ""),
                proxy.get("server", ""),
                str(proxy.get("port", "")),
                proxy.get("secret", ""),
                proxy.get("username", ""),
                proxy.get("password", ""),
            ]
        )
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _reset_daily_counter_if_needed(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.state.get("last_reset_date") != today:
            self.state["post_count_today"] = 0
            self.state["last_reset_date"] = today
            self._save_state()

    def _cap_sent_hashes(self, max_items: int = 10000):
        sent = self.state.get("sent_proxy_hashes", [])
        if len(sent) > max_items:
            self.state["sent_proxy_hashes"] = sent[-max_items:]

    def ingest_working_proxies(self, proxies: List[Dict[str, Any]]) -> int:
        data = self._load_working_data()
        indexed = {item.get("hash"): item for item in data.get("proxies", []) if item.get("hash")}
        added = 0

        now = datetime.now(timezone.utc).isoformat()
        for proxy in proxies:
            proxy_hash = self._proxy_hash(proxy)
            existing = indexed.get(proxy_hash)

            if existing:
                existing.update(
                    {
                        "latency_ms": proxy.get("latency_ms", existing.get("latency_ms")),
                        "source": proxy.get("source", existing.get("source")),
                        "last_seen": now,
                        "is_working": True,
                    }
                )
                continue

            entry = {
                **proxy,
                "hash": proxy_hash,
                "found_at": now,
                "last_seen": now,
                "sent_to_telegram": False,
                "is_working": True,
            }
            indexed[proxy_hash] = entry
            added += 1

        data["proxies"] = list(indexed.values())
        data["proxies"].sort(key=lambda item: item.get("latency_ms", float("inf")))
        data["last_updated"] = now
        data["total_proxies"] = len(data["proxies"])
        if not data.get("created_at"):
            data["created_at"] = now

        self._save_working_data(data)
        self.logger.info(f"Stored working proxy pool: +{added}, total={len(data['proxies'])}")
        return added

    def _next_unsent_proxy(self) -> Optional[Dict[str, Any]]:
        data = self._load_working_data()
        sent_hashes = set(self.state.get("sent_proxy_hashes", []))

        candidates = []
        for proxy in data.get("proxies", []):
            if proxy.get("hash") in sent_hashes:
                continue
            if proxy.get("sent_to_telegram", False):
                continue
            candidates.append(proxy)

        if not candidates:
            return None

        candidates.sort(key=lambda item: item.get("latency_ms", float("inf")))
        return candidates[0]

    def _mark_proxy_sent(self, proxy_hash: str):
        data = self._load_working_data()

        for proxy in data.get("proxies", []):
            if proxy.get("hash") == proxy_hash:
                proxy["sent_to_telegram"] = True
                proxy["sent_at"] = datetime.now(timezone.utc).isoformat()

        self._save_working_data(data)

        sent_hashes = self.state.get("sent_proxy_hashes", [])
        sent_hashes.append(proxy_hash)
        self.state["sent_proxy_hashes"] = sent_hashes
        self._cap_sent_hashes()
        self.state["post_count_today"] = int(self.state.get("post_count_today", 0)) + 1
        self.state["last_post_time"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

    def _build_mtproto_links(self, proxy: Dict[str, Any]) -> Dict[str, str]:
        server = quote(str(proxy.get("server", "")), safe="")
        port = quote(str(proxy.get("port", "")), safe="")
        secret = quote(str(proxy.get("secret", "")), safe="")

        return {
            "tg": f"tg://proxy?server={server}&port={port}&secret={secret}",
            "tme": f"https://t.me/proxy?server={server}&port={port}&secret={secret}",
        }

    def _build_proxy_message(self, proxy: Dict[str, Any]) -> str:
        proxy_type = proxy.get("type", "socks5").upper()
        server = proxy.get("server", "unknown")
        port = proxy.get("port", "?")
        latency = proxy.get("latency_ms")
        source = proxy.get("source", "unknown")

        latency_line = f"{latency:.0f} ms" if isinstance(latency, (int, float)) else "نامشخص"

        if proxy.get("type") == "mtproto":
            links = self._build_mtproto_links(proxy)
            body = f"""🟢 پروکسی تلگرام جدید

🔐 نوع: MTProto
📶 پینگ: {latency_line}
🌐 سرور: `{server}:{port}`

🔗 لینک اصلی:
`{links['tg']}`

🔁 لینک جایگزین:
`{links['tme']}`

📡 منبع:
`{source}`

🧡 *اینترنت بدون فیلتر حق همه ماست* 
📤 *با فوروارد کردنش یه نفر دیگه رو هم خوشحال کن!*
🆔 {self.channel_handle}"""
            return body

        auth = ""
        if proxy.get("username"):
            auth = f"\n👤 یوزرنیم: `{proxy.get('username')}`"
            if proxy.get("password"):
                auth += f"\n🔑 رمز: `{proxy.get('password')}`"

        body = f"""🟢 پروکسی تلگرام جدید

🔐 نوع: SOCKS5
📶 پینگ: {latency_line}
🌐 سرور: `{server}:{port}`{auth}

📱 مسیر اتصال در تلگرام:
`Settings > Data and Storage > Proxy > Add Proxy > SOCKS5`

📡 منبع:
`{source}`

🧡 *اینترنت بدون فیلتر حق همه ماست* 
📤 *با فوروارد کردنش یه نفر دیگه رو هم خوشحال کن!*
🆔 {self.channel_handle}"""
        return body

    async def publish_next_proxy(self) -> bool:
        self._reset_daily_counter_if_needed()

        if int(self.state.get("post_count_today", 0)) >= self.DAILY_POST_LIMIT:
            self.logger.info(f"Daily proxy post limit reached ({self.DAILY_POST_LIMIT}/day)")
            return False

        if not self.notifier.is_enabled:
            self.logger.info("Telegram credentials not configured for proxy publisher")
            return False

        proxy = self._next_unsent_proxy()
        if not proxy:
            self.logger.info("No unsent working proxies available")
            return False

        message = self._build_proxy_message(proxy)
        sent = await self.notifier.send_message(message)

        if sent:
            self._mark_proxy_sent(proxy.get("hash", ""))
            self.logger.info(f"Posted proxy {proxy.get('type')} {proxy.get('server')}:{proxy.get('port')}")
            return True

        self.logger.warning("Telegram send failed for next proxy")
        return False

    def get_stats(self) -> Dict[str, Any]:
        self._reset_daily_counter_if_needed()
        data = self._load_working_data()
        proxies = data.get("proxies", [])
        unsent = [item for item in proxies if not item.get("sent_to_telegram", False)]
        return {
            "total": len(proxies),
            "unsent": len(unsent),
            "post_count_today": int(self.state.get("post_count_today", 0)),
        }

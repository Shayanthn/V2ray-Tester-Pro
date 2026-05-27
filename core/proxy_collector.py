import json
import logging
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp


class ProxyCollector:
    def __init__(
        self,
        sources_file: str = "config/telegram_proxy_sources.json",
        timeout_seconds: int = 15,
        logger: Optional[logging.Logger] = None,
    ):
        self.sources_file = sources_file
        self.timeout_seconds = timeout_seconds
        self.logger = logger or logging.getLogger(__name__)

    def _load_sources(self) -> Dict[str, List[str]]:
        try:
            with open(self.sources_file, "r", encoding="utf-8") as file:
                data = json.load(file)
                return {
                    "mtproto_sources": data.get("mtproto_sources", []),
                    "socks5_sources": data.get("socks5_sources", []),
                }
        except Exception as exc:
            self.logger.error(f"Failed to load proxy sources from {self.sources_file}: {exc}")
            return {"mtproto_sources": [], "socks5_sources": []}

    async def _fetch_source(self, session: aiohttp.ClientSession, source_url: str) -> str:
        try:
            async with session.get(source_url, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    self.logger.warning(f"Skipping source {source_url} - status {response.status}")
                    return ""
                return await response.text()
        except Exception as exc:
            self.logger.warning(f"Skipping source {source_url} - fetch failed: {exc}")
            return ""

    @staticmethod
    def _is_valid_port(value: Any) -> bool:
        try:
            port = int(value)
            return 1 <= port <= 65535
        except Exception:
            return False

    @staticmethod
    def _normalize_host(host: str) -> str:
        if not host:
            return ""
        host = host.strip()
        if host.startswith("[") and host.endswith("]"):
            return host[1:-1]
        return host

    def _build_mtproto_proxy(self, server: str, port: Any, secret: str, source: str) -> Optional[Dict[str, Any]]:
        server = self._normalize_host(server)
        secret = unquote((secret or "").strip())
        if not server or not secret or not self._is_valid_port(port):
            return None

        return {
            "type": "mtproto",
            "server": server,
            "port": int(port),
            "secret": secret,
            "source": source,
        }

    def _build_socks5_proxy(
        self,
        server: str,
        port: Any,
        source: str,
        username: Optional[str] = None,
        pwd: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        server = self._normalize_host(server)
        if not server or not self._is_valid_port(port):
            return None

        proxy: Dict[str, Any] = {
            "type": "socks5",
            "server": server,
            "port": int(port),
            "source": source,
        }

        if username:
            proxy["username"] = username
        if pwd:
            proxy["password"] = pwd

        return proxy

    def _parse_mtproto_content(self, text: str, source: str) -> List[Dict[str, Any]]:
        proxies: List[Dict[str, Any]] = []

        link_pattern = re.compile(r'(?:tg://proxy\?|https?://t\.me/proxy\?)[^\s\'"<>()]+', re.IGNORECASE)
        for match in link_pattern.findall(text):
            parsed = urlparse(match)
            query = parse_qs(parsed.query)
            proxy = self._build_mtproto_proxy(
                server=query.get("server", [""])[0],
                port=query.get("port", [0])[0],
                secret=query.get("secret", [""])[0],
                source=source,
            )
            if proxy:
                proxies.append(proxy)

        for line in text.splitlines():
            raw = line.strip().strip("`")
            if not raw or raw.startswith("#"):
                continue

            if raw.startswith("tg://proxy?") or "t.me/proxy?" in raw:
                continue

            parts = raw.split(":")
            if len(parts) == 3:
                proxy = self._build_mtproto_proxy(parts[0], parts[1], parts[2], source)
                if proxy:
                    proxies.append(proxy)

        return proxies

    def _extract_socks5_from_json(self, node: Any, source: str, output: List[Dict[str, Any]]):
        if isinstance(node, dict):
            host = node.get("host") or node.get("ip") or node.get("server")
            port = node.get("port")
            protocol = (node.get("protocol") or node.get("type") or "").lower()
            username = node.get("username")
            pwd = node.get("password")

            if host and port and (not protocol or protocol == "socks5"):
                proxy = self._build_socks5_proxy(host, port, source, username, pwd)
                if proxy:
                    output.append(proxy)

            for value in node.values():
                self._extract_socks5_from_json(value, source, output)

        elif isinstance(node, list):
            for item in node:
                self._extract_socks5_from_json(item, source, output)

        elif isinstance(node, str):
            output.extend(self._parse_socks5_content(node, source, allow_json=False))

    def _parse_socks5_content(self, text: str, source: str, allow_json: bool = True) -> List[Dict[str, Any]]:
        proxies: List[Dict[str, Any]] = []

        if allow_json:
            try:
                payload = json.loads(text)
                self._extract_socks5_from_json(payload, source, proxies)
                return proxies
            except Exception:
                pass

        uri_pattern = re.compile(
            r"socks5://(?:(?P<user>[^:@/\s]+):(?P<pwd>[^@/\s]*)@)?(?P<host>\[[^\]]+\]|[^:/\s]+):(?P<port>\d{2,5})",
            re.IGNORECASE,
        )
        for match in uri_pattern.finditer(text):
            proxy = self._build_socks5_proxy(
                match.group("host"),
                match.group("port"),
                source,
                match.group("user"),
                match.group("pwd"),
            )
            if proxy:
                proxies.append(proxy)

        for line in text.splitlines():
            raw = line.strip().strip("`")
            if not raw or raw.startswith("#"):
                continue

            if raw.lower().startswith("socks5://"):
                continue

            if ":" not in raw or "proxy?" in raw:
                continue

            parts = [part.strip() for part in raw.split(":")]
            if len(parts) == 2:
                proxy = self._build_socks5_proxy(parts[0], parts[1], source)
                if proxy:
                    proxies.append(proxy)
            elif len(parts) >= 4:
                proxy = self._build_socks5_proxy(
                    parts[0],
                    parts[1],
                    source,
                    parts[2],
                    ":".join(parts[3:]),
                )
                if proxy:
                    proxies.append(proxy)

        return proxies

    @staticmethod
    def _proxy_key(proxy: Dict[str, Any]) -> str:
        return "|".join(
            [
                proxy.get("type", ""),
                proxy.get("server", ""),
                str(proxy.get("port", "")),
                proxy.get("secret", ""),
                proxy.get("username", ""),
                proxy.get("password", ""),
            ]
        )

    async def collect_proxies(self) -> List[Dict[str, Any]]:
        sources = self._load_sources()
        collected: List[Dict[str, Any]] = []

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        connector = aiohttp.TCPConnector(limit=20, ssl=False)

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            for source in sources.get("mtproto_sources", []):
                content = await self._fetch_source(session, source)
                if not content:
                    continue
                collected.extend(self._parse_mtproto_content(content, source))

            for source in sources.get("socks5_sources", []):
                content = await self._fetch_source(session, source)
                if not content:
                    continue
                collected.extend(self._parse_socks5_content(content, source))

        unique: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        for proxy in collected:
            key = self._proxy_key(proxy)
            if key in seen:
                continue
            seen.add(key)
            unique.append(proxy)

        self.logger.info(f"Collected {len(unique)} unique proxies from configured sources")
        return unique

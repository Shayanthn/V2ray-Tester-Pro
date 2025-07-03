# -----------------------------------------------------------------------------
# Developed by: Shayan Taherkhani
# Website: https://shayantaherkhani.ir
# -----------------------------------------------------------------------------
import asyncio
import base64
import binascii
import json
import logging
import os
import platform
import re
import socket
import subprocess
import sys
import time
import uuid
import webbrowser
from collections import defaultdict, deque
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import parse_qs, quote, unquote, urlparse
import statistics
import concurrent.futures

# --- Third-Party Imports ---
import aiohttp
import psutil
import requests
from dotenv import load_dotenv
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QMetaObject
from PyQt6.QtGui import QAction, QColor, QIcon, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton, QStatusBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QCheckBox,
    QComboBox, QInputDialog, QPlainTextEdit, QHeaderView, QGroupBox, QSystemTrayIcon
)
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.console import Group

# --- Application Configuration & State ---
load_dotenv()

class EnterpriseConfig:
    """
    Enhanced configuration management with persistence and validation.
    """
    def __init__(self):
        # Application Metadata
        self.APP_NAME = "V2Ray/Xray Enterprise"
        self.APP_VERSION = "5.1.0"
        self.AUTHOR_NAME = "Shayan Taherkhani"
        self.AUTHOR_WEBSITE = "https://shayantaherkhani.ir"
        
        # Path Configuration
        self._set_paths()
        
        # Network Configuration
        self.TEST_URL_PING = os.getenv('TEST_URL_PING', "https://www.google.com/generate_204")
        self.TEST_URL_DOWNLOAD = os.getenv('TEST_URL_DOWNLOAD', "https://speed.cloudflare.com/__down?bytes=5000000")
        self.TEST_URL_UPLOAD = os.getenv('TEST_URL_UPLOAD', "https://speed.cloudflare.com/__up")
        self.CENSORSHIP_CHECK_URL = os.getenv('CENSORSHIP_CHECK_URL', "https://www.youtube.com")
        self.TEST_TIMEOUT = int(os.getenv('TEST_TIMEOUT', 10))
        self.MAX_CONCURRENT_TESTS = int(os.getenv('MAX_CONCURRENT_TESTS', 50))
        self.NETWORK_RETRY_COUNT = int(os.getenv('NETWORK_RETRY_COUNT', 5))
        self.DOH_RESOLVER_URL = os.getenv('DOH_RESOLVER_URL', "https://cloudflare-dns.com/dns-query")
        
        # Security Configuration
        self.IP_BLACKLIST = set(json.loads(os.getenv('IP_BLACKLIST', '[]')))
        self.DOMAIN_BLACKLIST = set(json.loads(os.getenv('DOMAIN_BLACKLIST', '[]')))
        self.PROTOCOL_WHITELIST = {'vmess', 'vless', 'trojan', 'shadowsocks', 'tuic', 'hysteria2'}
        self.BANNED_PAYLOADS = {'exec', 'system', 'eval', 'shutdown', 'rm ', 'del ', 'format'}
        self.MAX_URI_LENGTH = int(os.getenv('MAX_URI_LENGTH', 4096))
        
        # Source Configuration
        self.AGGREGATOR_LINKS = json.loads(os.getenv('AGGREGATOR_LINKS', json.dumps([
            "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/subscription%20links.json",
            "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/sub/sub_merge.txt",
            "https://raw.githubusercontent.com/vpei/Free-Node-Merge/main/o/node.txt",
            "https://raw.githubusercontent.com/NodeFree.org/nodefree/main/nodefree.txt",
            "https://raw.githubusercontent.com/FMHY/FMHYedit/main/single%20links"
        ])))
        self.DIRECT_CONFIG_SOURCES = json.loads(os.getenv('DIRECT_CONFIG_SOURCES', json.dumps([
            "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
            "https://raw.githubusercontent.com/Bardiafa/Free-V2ray-Config/main/All_Configs_Sub.txt",
            "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sublists/sublists.txt",
            "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
            "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list_raw.txt"
        ])))
        
        # Telegram Configuration
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.TELEGRAM_ADMIN_ID = os.getenv('TELEGRAM_ADMIN_ID', '')
        self.TELEGRAM_TARGET_IDS = os.getenv('TELEGRAM_TARGET_IDS', '').split(',')
        
        # Adaptive Testing
        self.ADAPTIVE_TESTING = os.getenv('ADAPTIVE_TESTING', 'true').lower() == 'true'
        self.ADAPTIVE_BATCH_MIN = int(os.getenv('ADAPTIVE_BATCH_MIN', 20))
        self.ADAPTIVE_BATCH_MAX = int(os.getenv('ADAPTIVE_BATCH_MAX', 200))
        self.ADAPTIVE_SLEEP_MIN = float(os.getenv('ADAPTIVE_SLEEP_MIN', 0.05))
        self.ADAPTIVE_SLEEP_MAX = float(os.getenv('ADAPTIVE_SLEEP_MAX', 1.0))
        
        # Performance Monitoring
        self.PERF_HISTORY_SIZE = int(os.getenv('PERF_HISTORY_SIZE', 5000))
        
        # Load additional settings from config file
        self.load_settings()

    def _set_paths(self):
        """Sets platform-specific paths."""
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        
        # Executable Paths
        if platform.system() == 'Windows':
            self.XRAY_PATH = os.path.join(base_dir, "xray.exe")
            self.ICON_PATH = os.path.join(base_dir, "icon.ico")
        else:
            self.XRAY_PATH = os.path.join(base_dir, "xray")
            self.ICON_PATH = os.path.join(base_dir, "icon.png")
        
        # Config and Log Paths
        self.CONFIG_FILE = os.path.join(base_dir, "config.json")
        self.LOG_FILE = os.path.join(base_dir, "tester.log")
        self.RESULTS_FILE = os.path.join(base_dir, "results.json")

    def load_settings(self):
        """Loads settings from config file."""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    for key, value in settings.items():
                        if hasattr(self, key):
                            setattr(self, key, value)
        except Exception as e:
            logging.warning(f"Failed to load settings from {self.CONFIG_FILE}: {e}")

    def save_settings(self):
        """Saves current settings to config file."""
        try:
            settings = {
                'TEST_URL_PING': self.TEST_URL_PING,
                'TEST_URL_DOWNLOAD': self.TEST_URL_DOWNLOAD,
                'TEST_URL_UPLOAD': self.TEST_URL_UPLOAD,
                'CENSORSHIP_CHECK_URL': self.CENSORSHIP_CHECK_URL,
                'TEST_TIMEOUT': self.TEST_TIMEOUT,
                'MAX_CONCURRENT_TESTS': self.MAX_CONCURRENT_TESTS,
                'NETWORK_RETRY_COUNT': self.NETWORK_RETRY_COUNT,
                'DOH_RESOLVER_URL': self.DOH_RESOLVER_URL,
                'AGGREGATOR_LINKS': self.AGGREGATOR_LINKS,
                'DIRECT_CONFIG_SOURCES': self.DIRECT_CONFIG_SOURCES,
                'TELEGRAM_BOT_TOKEN': self.TELEGRAM_BOT_TOKEN,
                'TELEGRAM_ADMIN_ID': self.TELEGRAM_ADMIN_ID,
                'TELEGRAM_TARGET_IDS': self.TELEGRAM_TARGET_IDS,
                'ADAPTIVE_TESTING': self.ADAPTIVE_TESTING,
                'ADAPTIVE_BATCH_MIN': self.ADAPTIVE_BATCH_MIN,
                'ADAPTIVE_BATCH_MAX': self.ADAPTIVE_BATCH_MAX,
                'ADAPTIVE_SLEEP_MIN': self.ADAPTIVE_SLEEP_MIN,
                'ADAPTIVE_SLEEP_MAX': self.ADAPTIVE_SLEEP_MAX
            }
            
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save settings to {self.CONFIG_FILE}: {e}")

class AppState:
    """Centralized application state management with enhanced monitoring."""
    def __init__(self):
        self.is_running = False
        self.current_phase = "Idle"
        self.progress = 0
        self.total = 0
        self.found = 0
        self.failed = 0
        self.results = []
        self.stop_signal = asyncio.Event()
        self.ip_cache = {}
        self.uri_cache = set()
        self.start_time = None
        self.api_rate_limited = False
        self.adaptive_batch_size = config.ADAPTIVE_BATCH_MIN
        self.adaptive_sleep = config.ADAPTIVE_SLEEP_MAX
        self.success_rate = 0.0
        self.currently_testing = ""
        self.stats = {
            "total_tested": 0,
            "total_success": 0,
            "total_failed": 0,
            "avg_ping": 0,
            "avg_download": 0,
            "top_performer": None
        }
        
    def reset(self):
        """Resets the application state for a new test run."""
        self.is_running = False
        self.current_phase = "Idle"
        self.progress = 0
        self.total = 0
        self.found = 0
        self.failed = 0
        self.results = []
        self.stop_signal.clear()
        self.uri_cache.clear()
        self.start_time = None
        self.api_rate_limited = False
        self.adaptive_batch_size = config.ADAPTIVE_BATCH_MIN
        self.adaptive_sleep = config.ADAPTIVE_SLEEP_MAX
        self.success_rate = 0.0
        self.currently_testing = ""
        self.stats = {
            "total_tested": 0,
            "total_success": 0,
            "total_failed": 0,
            "avg_ping": 0,
            "avg_download": 0,
            "top_performer": None
        }

    def update_adaptive_params(self, success_count, total_count):
        """Updates adaptive testing parameters based on success rate."""
        if total_count == 0:
            return
            
        self.success_rate = success_count / total_count
        
        # Adjust batch size based on success rate
        if self.success_rate > 0.8:  # High success rate
            self.adaptive_batch_size = min(
                self.adaptive_batch_size + 10, config.ADAPTIVE_BATCH_MAX
            )
            self.adaptive_sleep = max(
                self.adaptive_sleep - 0.05, config.ADAPTIVE_SLEEP_MIN
            )
        elif self.success_rate < 0.2:  # Low success rate
            self.adaptive_batch_size = max(
                self.adaptive_batch_size - 10, config.ADAPTIVE_BATCH_MIN
            )
            self.adaptive_sleep = min(
                self.adaptive_sleep + 0.1, config.ADAPTIVE_SLEEP_MAX
            )

    def update_stats(self, result: Optional[Dict]):
        """Updates application statistics with a new test result."""
        self.stats["total_tested"] += 1
        if result:
            self.stats["total_success"] += 1
            
            # Update averages using incremental averaging
            total_s = self.stats["total_success"]
            self.stats["avg_ping"] = (self.stats["avg_ping"] * (total_s - 1) + result['ping']) / total_s
            self.stats["avg_download"] = (self.stats["avg_download"] * (total_s - 1) + result['download_speed']) / total_s
            
            # Update top performer
            current_top = self.stats["top_performer"]
            if not current_top or result['download_speed'] > current_top["download_speed"]:
                self.stats["top_performer"] = {
                    "protocol": result['protocol'],
                    "address": result['address'],
                    "ping": result['ping'],
                    "download_speed": result['download_speed']
                }
        else:
            self.stats["total_failed"] += 1

# --- Global Instances ---
config = EnterpriseConfig()
app_state = AppState()
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('EnterpriseApp')

# --- Network & Security Utilities ---
class NetworkManager:
    """Handles all network operations with retry logic and DoH support."""
    
    @staticmethod
    async def resolve_doh(hostname: str) -> Optional[str]:
        """Resolves a hostname using DNS-over-HTTPS."""
        if not hostname or hostname in app_state.ip_cache:
            return app_state.ip_cache.get(hostname)
            
        try:
            params = {'name': hostname, 'type': 'A'}
            headers = {'accept': 'application/dns-json'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    config.DOH_RESOLVER_URL, params=params, headers=headers, timeout=3
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'Answer' in data and data['Answer']:
                            ip = data['Answer'][0]['data']
                            app_state.ip_cache[hostname] = ip
                            return ip
        except Exception as e:
            logger.debug(f"Failed to resolve {hostname} via DoH: {e}")
        return None
    
    @staticmethod
    async def safe_get(url: str, retry_count: int = None, headers: dict = None) -> Optional[str]:
        """Performs a GET request with retry logic and exponential backoff."""
        retry_count = retry_count or config.NETWORK_RETRY_COUNT
        headers = headers or {
            'User-Agent': f'V2RayTester/{config.APP_VERSION}',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        for attempt in range(retry_count):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=8) as response:
                        if response.status == 200:
                            return await response.text()
                        elif response.status == 403 and 'github.com' in url:
                            app_state.api_rate_limited = True
                            logger.warning(f"GitHub API rate limit reached for {url}")
                            return None
                        elif response.status == 429:
                            logger.warning(f"Rate limited for {url}, retrying...")
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.debug(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(0.5 + attempt * 1.5)  # Exponential backoff
        return None

class SecurityValidator:
    """Validates configurations and URIs for security compliance."""
    
    @staticmethod
    def validate_uri(uri: str) -> bool:
        """Performs comprehensive security validation on a URI."""
        if not uri or not isinstance(uri, str):
            return False
            
        # Length check
        if len(uri) > config.MAX_URI_LENGTH:
            logger.debug(f"URI too long ({len(uri)} chars)")
            return False
            
        # Protocol check
        protocol = uri.split("://")[0].lower()
        if protocol not in config.PROTOCOL_WHITELIST:
            logger.debug(f"Protocol not allowed: {protocol}")
            return False
            
        # Blacklist checks
        for banned in config.BANNED_PAYLOADS:
            if banned in uri.lower():
                logger.warning(f"Banned payload detected: {banned}")
                return False
                
        # Suspicious pattern detection
        suspicious_patterns = [
            r"eval\s*\(", r"exec\s*\(", r"fromCharCode", r"base64_decode",
            r"[\x00-\x1F\x7F-\xFF]"  # Non-printable characters
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, uri):
                logger.warning(f"Suspicious pattern detected in URI: {pattern}")
                return False
                
        return True
    
    @staticmethod
    def validate_config(config_json: dict) -> bool:
        """Validates a configuration JSON for security compliance."""
        if not config_json or not isinstance(config_json, dict):
            return False
            
        # Check for banned payloads in the entire config
        config_str = json.dumps(config_json).lower()
        for banned in config.BANNED_PAYLOADS:
            if banned in config_str:
                logger.warning(f"Banned payload in config: {banned}")
                return False
                
        # Validate outbound settings
        outbounds = config_json.get("outbounds", [])
        for outbound in outbounds:
            if outbound.get("protocol") == "freedom":
                continue
                
            settings = outbound.get("settings", {})
            servers = settings.get("servers", [])
            vnext = settings.get("vnext", [])
            
            all_servers = servers + vnext
            for server in all_servers:
                address = server.get("address", "")
                if SecurityValidator.is_blacklisted(address):
                    logger.warning(f"Blacklisted server in config: {address}")
                    return False
        return True
    
    @staticmethod
    def is_blacklisted(address: str) -> bool:
        """Checks if an address (IP or domain) is blacklisted."""
        if not address:
            return False
            
        # Check IP blacklist
        if address in config.IP_BLACKLIST:
            return True
            
        # Check domain blacklist (including subdomains)
        for domain in config.DOMAIN_BLACKLIST:
            if address.endswith(domain):
                return True
                
        # Check for Iranian government/infra domains to avoid self-testing loops
        iran_blocked = [
            ".ir", "arvancloud.com", "parsonline.com", "asiatech.ir", "shatel.ir"
        ]
        
        for domain in iran_blocked:
            if address.endswith(domain):
                return True
                
        return False

# --- Advanced Config Processing ---
class ConfigProcessor:
    """Handles parsing all supported URI schemes and generating Xray JSON configurations."""
    
    @staticmethod
    def build_config_from_uri(uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Master parser that routes URIs to protocol-specific handlers."""
        if not uri or not SecurityValidator.validate_uri(uri):
            return None
            
        try:
            protocol = uri.split("://")[0].lower()
            parser_method = getattr(ConfigProcessor, f"_parse_{protocol}", None)
            
            if parser_method:
                config_json = parser_method(uri, port)
                if config_json and SecurityValidator.validate_config(config_json):
                    return config_json
            else:
                logger.warning(f"Unsupported protocol: {protocol}")
        except Exception as e:
            logger.warning(f"Failed to parse URI '{uri[:30]}...': {e}")
        return None
    
    @staticmethod
    def _create_base_config(port: int) -> Dict[str, Any]:
        """Creates the base Xray JSON structure with a SOCKS inbound."""
        return {
            "log": {"loglevel": "warning"},
            "inbounds": [{
                "listen": "127.0.0.1",
                "port": port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True, "ip": "127.0.0.1"},
                "tag": "socks-in"
            }],
            "outbounds": [{
                "protocol": "freedom",
                "tag": "direct"
            }],
            "routing": {
                "domainStrategy": "IPIfNonMatch",
                "rules": [{
                    "type": "field",
                    "ip": ["geoip:private"],
                    "outboundTag": "direct"
                }]
            }
        }
    
    @staticmethod
    def _parse_vmess(uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Comprehensive VMess URI parser."""
        try:
            # Extract base64 part
            base64_part = uri.split('://')[1].split('?')[0].split('#')[0]
            # Add padding if necessary (more robustly)
            padding = '=' * (-len(base64_part) % 4)
            decoded_bytes = base64.b64decode(base64_part + padding)
            vmess_params = json.loads(decoded_bytes.decode('utf-8'))

            if not all(k in vmess_params for k in ['add', 'port', 'id']):
                logger.warning("VMess JSON missing required keys (add, port, id).")
                return None

            config_json = ConfigProcessor._create_base_config(port)
            stream_settings = ConfigProcessor._build_stream_settings(
                net=vmess_params.get("net", "tcp"),
                security=vmess_params.get("tls", "none"),
                path=vmess_params.get("path", "/"),
                host=vmess_params.get("host", ""),
                sni=vmess_params.get("sni", ""),
                service_name=vmess_params.get("path", ""),
                alpn=vmess_params.get("alpn", ""),
                fingerprint=vmess_params.get("fp", "")
            )

            outbound = {
                "protocol": "vmess",
                "settings": {
                    "vnext": [{
                        "address": vmess_params["add"],
                        "port": int(vmess_params["port"]),
                        "users": [{
                            "id": vmess_params["id"],
                            "alterId": int(vmess_params.get("aid", 0)),
                            "security": vmess_params.get("scy", "auto"),
                        }]
                    }]
                },
                "streamSettings": stream_settings,
                "tag": "proxy"
            }
            config_json["outbounds"].insert(0, outbound)
            return config_json
        except (json.JSONDecodeError, binascii.Error, UnicodeDecodeError) as e:
            logger.warning(f"Could not decode/parse VMess URI body: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing VMess URI: {e}")
        return None

    @staticmethod
    def _parse_vless(uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Comprehensive VLESS, REALITY, XTLS URI parser."""
        try:
            parsed_uri = urlparse(uri)
            params = parse_qs(parsed_uri.query)

            address = parsed_uri.hostname
            uuid_val = parsed_uri.username

            if not all([address, uuid_val]):
                logger.warning("VLESS URI missing address or UUID.")
                return None

            config_json = ConfigProcessor._create_base_config(port)
            security = params.get('security', ['none'])[0]
            network = params.get('type', ['tcp'])[0]

            stream_settings = ConfigProcessor._build_stream_settings(
                net=network,
                security=security,
                path=params.get('path', ['/'])[0],
                host=params.get('host', [address])[0],
                sni=params.get('sni', [address])[0],
                alpn=params.get('alpn', ['h2,http/1.1'])[0],
                fingerprint=params.get('fp', ['chrome'])[0],
                service_name=params.get('serviceName', [''])[0],
                reality_pbk=params.get('pbk', [''])[0],
                reality_sid=params.get('sid', [''])[0],
                reality_spiderx=params.get('spiderX', ['/'])[0]
            )
            
            flow = params.get('flow', [''])[0]
            if security == 'xtls' and not flow:
                flow = 'xtls-rprx-direct'

            outbound = {
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": address,
                        "port": parsed_uri.port,
                        "users": [{
                            "id": uuid_val,
                            "encryption": "none",
                            "flow": flow,
                        }]
                    }]
                },
                "streamSettings": stream_settings,
                "tag": "proxy"
            }
            config_json["outbounds"].insert(0, outbound)
            return config_json
        except Exception as e:
            logger.warning(f"Could not parse VLESS/Reality URI: {e}")
            return None

    @staticmethod
    def _parse_trojan(uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Comprehensive Trojan URI parser."""
        try:
            parsed_uri = urlparse(uri)
            params = parse_qs(parsed_uri.query)

            address = parsed_uri.hostname
            password = parsed_uri.username

            if not all([address, password]):
                logger.warning("Trojan URI missing address or password.")
                return None

            config_json = ConfigProcessor._create_base_config(port)
            stream_settings = ConfigProcessor._build_stream_settings(
                net=params.get('type', ['tcp'])[0],
                security=params.get('security', ['tls'])[0],
                path=params.get('path', ['/'])[0],
                host=params.get('host', [address])[0],
                sni=params.get('sni', [address])[0],
                alpn=params.get('alpn', ['h2,http/1.1'])[0],
                fingerprint=params.get('fp', ['chrome'])[0],
                service_name=params.get('serviceName', [''])[0]
            )

            outbound = {
                "protocol": "trojan",
                "settings": {
                    "servers": [{
                        "address": address,
                        "port": parsed_uri.port,
                        "password": password,
                    }]
                },
                "streamSettings": stream_settings,
                "tag": "proxy"
            }
            config_json["outbounds"].insert(0, outbound)
            return config_json
        except Exception as e:
            logger.warning(f"Could not parse Trojan URI: {e}")
            return None

    @staticmethod
    def _parse_shadowsocks(uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Robust Shadowsocks (SS) URI parser for standard and base64 formats."""
        try:
            main_part = uri.split('://', 1)[1]
            remark = unquote(main_part.split('#', 1)[1]) if '#' in main_part else None
            main_part = main_part.split('#', 1)[0]
            
            address, server_port, method, password = None, None, None, None

            # Standard format: ss://method:pass@host:port
            if '@' in main_part:
                user_info, host_info = main_part.rsplit('@', 1)
                user_info_decoded = unquote(user_info)
                method, password = user_info_decoded.split(':', 1)
                
                # Handle IPv6 address in host
                if host_info.startswith('[') and ']' in host_info:
                    end_bracket_index = host_info.rfind(']')
                    address = host_info[1:end_bracket_index]
                    server_port_str = host_info[end_bracket_index+2:]
                else:
                    address, server_port_str = host_info.rsplit(':', 1)
                server_port = int(server_port_str)
            # Base64 format: ss://BASE64(method:pass@host:port)
            else:
                padding = '=' * (-len(main_part) % 4)
                decoded_str = base64.b64decode(main_part + padding).decode('utf-8')
                
                user_info, host_info = decoded_str.rsplit('@', 1)
                method, password = user_info.split(':', 1)
                address, server_port_str = host_info.rsplit(':', 1)
                server_port = int(server_port_str)
            
            if not all([address, server_port, method, password]):
                raise ValueError("Parsed Shadowsocks URI is incomplete.")
            
            config_json = ConfigProcessor._create_base_config(port)
            outbound = {
                "protocol": "shadowsocks",
                "settings": {
                    "servers": [{
                        "address": address,
                        "port": server_port,
                        "method": method,
                        "password": password,
                    }]
                },
                "tag": remark or "proxy"
            }
            config_json["outbounds"].insert(0, outbound)
            return config_json
        except Exception as e:
            logger.warning(f"Could not parse Shadowsocks URI '{uri[:30]}...': {e}")
            return None
    
    @staticmethod
    def _parse_tuic(uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Comprehensive TUIC URI parser."""
        try:
            parsed = urlparse(uri)
            params = parse_qs(parsed.query)

            config_json = ConfigProcessor._create_base_config(port)
            # TUIC is handled as a stream setting in Xray
            stream_settings = {
                "network": "tuic", # Changed from vless to tuic
                "security": "none",
                "tuicSettings": {
                    "server": f"{parsed.hostname}:{parsed.port}",
                    "uuid": parsed.username,
                    "password": parsed.password,
                    "congestion_control": params.get("congestion_control", ["bbr"])[0],
                    "udp_relay_mode": params.get("udp_relay_mode", ["native"])[0],
                    "sni": params.get("sni", [parsed.hostname])[0],
                    "alpn": [p.strip() for p in params.get("alpn", ["h3"])[0].split(',')],
                    "disable_sni": str(params.get("disable_sni", ["false"])[0]).lower() == "true",
                }
            }
            
            # A dummy vless outbound is needed to host the tuic stream settings
            outbound = {
                "protocol": "vless", 
                "settings": {
                    "vnext": [{
                        "address": "127.0.0.1", # Dummy address
                        "port": 1080, # Dummy port
                        "users": [{"id": str(uuid.uuid4()), "encryption": "none"}]
                    }]
                },
                "streamSettings": stream_settings,
                "tag": "proxy"
            }
            config_json["outbounds"].insert(0, outbound)
            return config_json
        except Exception as e:
            logger.warning(f"Could not parse TUIC URI: {e}")
            return None

    @staticmethod
    def _parse_hysteria2(uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Comprehensive Hysteria2 URI parser."""
        try:
            parsed = urlparse(uri)
            params = parse_qs(parsed.query)

            config_json = ConfigProcessor._create_base_config(port)
            # Hysteria2 is also a stream setting
            stream_settings = {
                "network": "hysteria2",
                "security": "none",
                "hysteriaSettings": {
                    "server": f"{parsed.hostname}:{parsed.port}",
                    "auth": parsed.password,
                    "sni": params.get("sni", [parsed.hostname])[0],
                }
            }
            
            outbound = {
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": "127.0.0.1",
                        "port": 1080,
                        "users": [{"id": str(uuid.uuid4()), "encryption": "none"}]
                    }]
                },
                "streamSettings": stream_settings,
                "tag": "proxy"
            }
            config_json["outbounds"].insert(0, outbound)
            return config_json
        except Exception as e:
            logger.warning(f"Could not parse Hysteria2 URI: {e}")
            return None

    @staticmethod
    def _build_stream_settings(**kwargs) -> Dict[str, Any]:
        """Dynamically builds the streamSettings object for various protocols."""
        net = kwargs.get('net', 'tcp')
        security = kwargs.get('security', 'none')

        stream = {"network": net, "security": security}
        
        if security in ["tls", "xtls"]:
            stream["tlsSettings"] = {
                "serverName": kwargs.get('sni'),
                "allowInsecure": False,
                "alpn": [p.strip() for p in kwargs.get('alpn', '').split(',')] if kwargs.get('alpn') else [],
                "fingerprint": kwargs.get('fingerprint', 'chrome')
            }
            if security == 'xtls':
                stream["xtlsSettings"] = {"serverName": kwargs.get('sni')}

        if security == "reality":
            stream["realitySettings"] = {
                "show": False,
                "serverName": kwargs.get('sni'),
                "fingerprint": kwargs.get('fingerprint', 'chrome'),
                "publicKey": kwargs.get('reality_pbk'),
                "shortId": kwargs.get('reality_sid'),
                "spiderX": kwargs.get('reality_spiderx'),
            }
        
        if net == "ws":
            stream["wsSettings"] = {
                "path": kwargs.get('path'),
                "headers": {"Host": kwargs.get('host')}
            }
        elif net == "grpc":
            stream["grpcSettings"] = {
                "serviceName": kwargs.get('service_name'),
                "multiMode": True
            }
        return stream

# --- Performance Testing & Analysis ---
class TestRunner:
    """Manages the execution of advanced tests against configurations."""
    
    @staticmethod
    def run_full_test(config_json: Dict[str, Any], port: int) -> Optional[Dict[str, Any]]:
        """
        Executes a comprehensive test suite on a given Xray configuration.
        Returns None if the test fails or the config is invalid.
        """
        config_path = os.path.join(os.path.dirname(config.XRAY_PATH), f"temp_config_{port}.json")
        process = None
        
        try:
            # Write config to temp file
            with open(config_path, "w", encoding='utf-8') as f:
                json.dump(config_json, f)

            # Start Xray process
            cmd = [config.XRAY_PATH, "run", "-c", config_path]
            startup_info = None
            if platform.system() == 'Windows':
                startup_info = subprocess.STARTUPINFO()
                startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup_info.wShowWindow = subprocess.SW_HIDE

            process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, startupinfo=startup_info
            )
            
            # Wait for Xray to start
            time.sleep(1.0)
            
            # Check if process is still running
            if process.poll() is not None:
                error_output = process.stderr.read().decode('utf-8', errors='ignore') if process.stderr else ""
                logger.error(f"Xray process failed to start for port {port}: {error_output}")
                return None
                
            proxies = {
                'http': f'socks5://127.0.0.1:{port}',
                'https': f'socks5://127.0.0.1:{port}'
            }
            
            # 1. Latency and Jitter Test
            latencies = []
            for _ in range(3):
                try:
                    start_time = time.monotonic()
                    response = requests.get(
                        config.TEST_URL_PING, proxies=proxies, timeout=config.TEST_TIMEOUT
                    )
                    if response.status_code == 204:
                        latency = (time.monotonic() - start_time) * 1000
                        if latency < 5000:  # Filter out extremely high latencies
                            latencies.append(latency)
                except requests.RequestException:
                    latencies.append(float('inf'))
            
            valid_latencies = [l for l in latencies if l != float('inf')]
            if not valid_latencies:
                return None  # Failed basic connectivity

            avg_ping = int(statistics.mean(valid_latencies))
            jitter = int(statistics.stdev(valid_latencies) if len(valid_latencies) > 1 else 0)

            # 2. Speed Test
            dl_speed = TestRunner._download_speed_test(proxies)
            ul_speed = TestRunner._upload_speed_test(proxies)

            # 3. Bypass Test
            is_bypassing = TestRunner._check_bypass(proxies)

            # 4. Get Server Info
            outbound = config_json['outbounds'][0]
            # This is complex due to TUIC/Hysteria wrappers. We need to find the real server.
            address, protocol = "N/A", "N/A"
            if 'streamSettings' in outbound and 'network' in outbound['streamSettings']:
                net = outbound['streamSettings']['network']
                if net == 'tuic':
                    protocol = 'tuic'
                    address = outbound['streamSettings']['tuicSettings']['server'].split(':')[0]
                elif net == 'hysteria2':
                    protocol = 'hysteria2'
                    address = outbound['streamSettings']['hysteriaSettings']['server'].split(':')[0]

            if protocol == "N/A": # Not a wrapped protocol
                protocol = outbound['protocol']
                if protocol in ["vmess", "vless"]:
                    server_info = outbound['settings'].get('vnext', [{}])[0]
                    address = server_info.get('address', 'N/A')
                elif protocol in ["trojan", "shadowsocks"]:
                    server_info = outbound['settings'].get('servers', [{}])[0]
                    address = server_info.get('address', 'N/A')

            # 5. Check blacklist again on final address
            if SecurityValidator.is_blacklisted(address):
                logger.warning(f"Blacklisted server detected: {address}")
                return None

            return {
                'protocol': protocol,
                'address': address,
                'ping': avg_ping,
                'jitter': jitter,
                'download_speed': dl_speed,
                'upload_speed': ul_speed,
                'is_bypassing': is_bypassing,
                'ip': address, # 'ip' field should be consistent
                'config_json': config_json,
                'uri': None  # Will be set by the orchestrator
            }

        except Exception as e:
            logger.error(f"Error in full test for port {port}: {e}", exc_info=True)
            return None
        finally:
            if process:
                try:
                    # Cleanly terminate the process and its children
                    parent = psutil.Process(process.pid)
                    for child in parent.children(recursive=True):
                        child.terminate()
                    parent.terminate()
                    process.wait(timeout=2)
                except (subprocess.TimeoutExpired, psutil.NoSuchProcess):
                    try:
                        process.kill()
                    except Exception:
                        pass # Process might have already died
                except Exception as e:
                    logger.warning(f"Error terminating process {process.pid}: {e}")
            
            if os.path.exists(config_path):
                try:
                    os.remove(config_path)
                except Exception as e:
                    logger.warning(f"Error removing temp config '{config_path}': {e}")

    @staticmethod
    def _download_speed_test(proxies: dict) -> float:
        """Measures download speed in Mbps."""
        try:
            start_time = time.monotonic()
            response = requests.get(
                config.TEST_URL_DOWNLOAD, proxies=proxies, timeout=config.TEST_TIMEOUT, stream=True
            )
            total_downloaded = 0
            
            for chunk in response.iter_content(chunk_size=65536):
                if time.monotonic() - start_time > config.TEST_TIMEOUT:
                    break
                total_downloaded += len(chunk)
                if total_downloaded >= 3_000_000:  # 3MB is enough for a good estimate
                    break
            
            duration = time.monotonic() - start_time
            if duration > 0:
                # Mbps = (Bytes * 8) / duration / 1,000,000
                return round((total_downloaded * 8) / duration / 1_000_000, 2)
        except requests.RequestException:
            return 0.0
        return 0.0

    @staticmethod
    def _upload_speed_test(proxies: dict) -> float:
        """Measures upload speed in Mbps."""
        try:
            test_data = os.urandom(2_000_000) # 2MB of random data
            
            start_time = time.monotonic()
            response = requests.post(
                config.TEST_URL_UPLOAD, data=test_data, proxies=proxies, timeout=config.TEST_TIMEOUT
            )
            
            duration = time.monotonic() - start_time
            if duration > 0 and response.status_code == 200:
                return round((len(test_data) * 8) / duration / 1_000_000, 2)
        except requests.RequestException:
            return 0.0
        return 0.0

    @staticmethod
    def _check_bypass(proxies: dict) -> bool:
        """Checks if a known blocked site is accessible."""
        try:
            response = requests.head(
                config.CENSORSHIP_CHECK_URL, proxies=proxies, timeout=5, allow_redirects=True
            )
            return response.status_code < 400  # Success is any 2xx or 3xx
        except requests.RequestException:
            return False

# --- Config Discovery & Management ---
class ConfigDiscoverer:
    """Discovers and manages configuration sources."""
    
    @staticmethod
    async def discover_sources() -> Set[str]:
        """Discovers all available configuration sources."""
        all_sources = set(config.DIRECT_CONFIG_SOURCES)
        
        # Only use aggregators if not rate limited
        if not app_state.api_rate_limited:
            tasks = [ConfigDiscoverer._fetch_aggregator(url) for url in config.AGGREGATOR_LINKS]
            results = await asyncio.gather(*tasks)
            for res_set in results:
                all_sources.update(res_set)
        
        return all_sources
    
    @staticmethod
    async def _fetch_aggregator(url: str) -> Set[str]:
        """Fetches a list of subscription links from an aggregator."""
        try:
            content = await NetworkManager.safe_get(url)
            if not content:
                return set()
                
            try:  # Handle JSON list of links
                return set(json.loads(content))
            except json.JSONDecodeError:  # Handle plain text list of links
                return {
                    line.strip() for line in content.splitlines()
                    if line.strip().startswith("http")
                }
        except Exception as e:
            logger.warning(f"Failed to fetch aggregator {url}: {e}")
            return set()
    
    @staticmethod
    async def fetch_configs_from_source(url: str) -> List[str]:
        """Fetches and decodes configurations from a single source."""
        try:
            content = await NetworkManager.safe_get(url)
            if not content:
                return []
                
            decoded = None
            # Attempt to decode base64, if fails, assume plain text
            try:
                # Add padding just in case
                decoded = base64.b64decode(content.encode('ascii')).decode('utf-8') 
            except (binascii.Error, UnicodeDecodeError):
                decoded = content # Fallback to plain text
            
            return [
                line.strip() for line in decoded.splitlines()
                if line.strip() and "://" in line
            ]
        except Exception as e:
            logger.warning(f"Failed to process source {url}: {e}")
            return []

# --- Test Orchestration ---
class TestOrchestrator:
    """Manages the entire testing lifecycle."""
    
    def __init__(self, worker_class):
        self.worker_class = worker_class
        self.config_queue = asyncio.Queue()
        self.results_list = []
        self.unique_uris = set()
        self.lock = asyncio.Lock()
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=config.MAX_CONCURRENT_TESTS
        )
    
    async def run_test_pipeline(self):
        """Main pipeline for the entire test process."""
        app_state.reset()
        app_state.is_running = True
        app_state.start_time = datetime.now()
        
        try:
            # Phase 1: Discovery
            self.worker_class.update_status.emit("Phase 1: Discovering config sources...")
            sources = await ConfigDiscoverer.discover_sources()
            
            # Phase 2: Fetching
            self.worker_class.update_status.emit(f"Phase 2: Fetching from {len(sources)} sources...")
            await self._fetch_and_queue_configs(sources)
            
            if self.config_queue.empty():
                self.worker_class.update_status.emit("No configs found. Stopping.")
                self.worker_class.finished.emit()
                return
                
            app_state.total = self.config_queue.qsize()
            self.worker_class.update_status.emit(f"Phase 3: Testing {app_state.total} configs...")
            self.worker_class.set_progress_max.emit(app_state.total)
            
            # Phase 3: Testing
            await self._run_workers()
            
            # Phase 4: Completion
            final_msg = (f"Test complete! Found {len(self.results_list)} working configs "
                         f"({app_state.failed} failed).")
            self.worker_class.update_status.emit(final_msg)
            
        except Exception as e:
            logger.critical(f"Test pipeline failed: {e}", exc_info=True)
            self.worker_class.update_status.emit(f"Error: {str(e)}")
        finally:
            app_state.is_running = False
            self.thread_pool.shutdown()
            self.worker_class.finished.emit()
    
    async def _fetch_and_queue_configs(self, sources: Set[str]):
        """Fetches configs from all sources and puts them in the queue."""
        tasks = [self._process_source(url) for url in sources]
        await asyncio.gather(*tasks)
    
    async def _process_source(self, url: str):
        """Processes a single source URL and adds valid URIs to the queue."""
        try:
            configs = await ConfigDiscoverer.fetch_configs_from_source(url)
            for uri in configs:
                if uri not in self.unique_uris and SecurityValidator.validate_uri(uri):
                    self.unique_uris.add(uri)
                    await self.config_queue.put(uri)
        except Exception as e:
            logger.warning(f"Failed to process source {url}: {e}")
    
    async def _run_workers(self):
        """Creates and manages a pool of worker tasks."""
        num_workers = min(config.MAX_CONCURRENT_TESTS, self.config_queue.qsize())
        workers = [
            asyncio.create_task(self._worker(i))
            for i in range(num_workers)
        ]
        
        await self.config_queue.join()
        
        for worker in workers:
            worker.cancel()
        
        await asyncio.gather(*workers, return_exceptions=True)
    
    async def _worker(self, worker_id: int):
        """Worker task that processes URIs from the queue."""
        port = 10800 + worker_id
        success_count = 0
        total_count = 0
        
        while True:
            try:
                if app_state.stop_signal.is_set():
                    break
                    
                uri = await self.config_queue.get()
                
                # Update currently testing URI
                app_state.currently_testing = uri
                self.worker_class.current_test.emit(uri)
                
                # Process the URI
                config_json = ConfigProcessor.build_config_from_uri(uri, port)
                if config_json:
                    # Run blocking test in thread pool
                    loop = asyncio.get_event_loop()
                    test_result = await loop.run_in_executor(
                        self.thread_pool, TestRunner.run_full_test, config_json, port
                    )
                    
                    total_count += 1
                    
                    if test_result:
                        test_result['uri'] = uri
                        
                        # Get GeoIP info
                        country = await self._get_country_from_ip(test_result['ip'])
                        test_result['country'] = country
                        
                        async with self.lock:
                            self.results_list.append(test_result)
                            app_state.found += 1
                            success_count += 1
                            app_state.results.append(test_result)
                            app_state.update_stats(test_result)
                            
                        self.worker_class.result_ready.emit(test_result)
                    else:
                        async with self.lock:
                            app_state.failed += 1
                            app_state.update_stats(None)
                
                # Update progress
                async with self.lock:
                    app_state.progress += 1
                self.worker_class.update_progress.emit(app_state.progress)
                
                # Update adaptive parameters
                if config.ADAPTIVE_TESTING and total_count % 10 == 0:
                    app_state.update_adaptive_params(success_count, total_count)
                    if app_state.adaptive_sleep > 0:
                        await asyncio.sleep(app_state.adaptive_sleep)
                
                self.config_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in worker {worker_id}: {e}", exc_info=True)
                self.config_queue.task_done() # Ensure task is marked done even on error

    async def _get_country_from_ip(self, ip: str) -> str:
        """Gets country information for an IP address using an online API."""
        if not ip or ip in app_state.ip_cache:
            return app_state.ip_cache.get(ip, "N/A")
        
        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,country,countryCode"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "success":
                            country_code = data.get("countryCode", "??")
                            flag = ''.join(
                                chr(0x1F1E6 + ord(c.upper()) - ord('A'))
                                for c in country_code
                            )
                            result = f"{flag} {data.get('country', 'Unknown')}"
                            app_state.ip_cache[ip] = result
                            return result
        except Exception:
            pass # Ignore errors, just return N/A
        return "N/A"

# --- Telegram Integration ---
class TelegramManager:
    """Handles all Telegram bot interactions. (Requires python-telegram-bot)"""
    
    def __init__(self, main_window=None):
        self.bot = None
        self.app = None
        self.loop = None
        self.main_window = main_window # Reference to MainWindow for thread-safe calls
        
    def initialize(self):
        """Initializes the Telegram bot if configured."""
        if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_ADMIN_ID:
            return False
            
        try:
            from telegram import Update, Bot
            from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

            self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            self.loop = asyncio.new_event_loop()

            def run_bot():
                asyncio.set_event_loop(self.loop)
                app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
                
                # Register handlers
                app.add_handler(CommandHandler("start", self._handle_start))
                app.add_handler(CommandHandler("start_test", self._handle_start_test))
                app.add_handler(CommandHandler("stop_test", self._handle_stop_test))
                app.add_handler(CommandHandler("status", self._handle_status))
                app.add_handler(CommandHandler("results", self._handle_results))
                app.add_handler(CommandHandler("stats", self._handle_stats))
                
                self.loop.run_until_complete(app.initialize())
                self.loop.run_until_complete(app.start())
                self.loop.run_until_complete(app.updater.start_polling())
                self.loop.run_forever()

            # Run the bot's event loop in a separate daemon thread
            import threading
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            return True

        except ImportError:
            logger.warning("python-telegram-bot not installed. Telegram features disabled.")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            return False

    def _is_admin(self, update: 'Update') -> bool:
        """Checks if the message sender is the admin."""
        return str(update.effective_user.id) == config.TELEGRAM_ADMIN_ID

    async def log_to_admin(self, message: str):
        """Sends a log message to the admin."""
        if not self.bot or not config.TELEGRAM_ADMIN_ID: return
        try:
            await self.bot.send_message(chat_id=config.TELEGRAM_ADMIN_ID, text=f"📢 {message}")
        except Exception as e:
            logger.warning(f"Failed to send Telegram message to admin: {e}")

    async def send_to_targets(self, message: str, parse_mode: str = None):
        """Sends a message to all target channels/users."""
        if not self.bot or not config.TELEGRAM_TARGET_IDS: return
        
        for target_id in config.TELEGRAM_TARGET_IDS:
            if not target_id.strip(): continue
            try:
                await self.bot.send_message(
                    chat_id=target_id.strip(), text=message, parse_mode=parse_mode
                )
            except Exception as e:
                logger.warning(f"Failed to send Telegram message to {target_id}: {e}")

    async def _handle_start(self, update: 'Update', context: 'ContextTypes.DEFAULT_TYPE'):
        if not self._is_admin(update):
            await update.message.reply_text("❌ Unauthorized.")
            return
            
        welcome_msg = (
            f"🚀 *{config.APP_NAME} v{config.APP_VERSION}* - Bot Control\n\n"
            "Available commands:\n"
            "/start_test - Begin configuration testing\n"
            "/stop_test - Stop current test\n"
            "/status - Show current status\n"
            "/results - Show top 5 results\n"
            "/stats - Show performance statistics"
        )
        await update.message.reply_text(welcome_msg, parse_mode="Markdown")
    
    async def _handle_start_test(self, update: 'Update', context: 'ContextTypes.DEFAULT_TYPE'):
        if not self._is_admin(update): return
        
        if app_state.is_running:
            await update.message.reply_text("⚠️ Test is already running.")
            return
        
        if self.main_window:
            await update.message.reply_text("✅ Test start command sent to GUI.")
            QMetaObject.invokeMethod(self.main_window, "start_test", Qt.ConnectionType.QueuedConnection)
        else:
            await update.message.reply_text("❌ Cannot start test: GUI not available.")

    async def _handle_stop_test(self, update: 'Update', context: 'ContextTypes.DEFAULT_TYPE'):
        if not self._is_admin(update): return

        if not app_state.is_running:
            await update.message.reply_text("⚠️ No test is currently running.")
            return
            
        if self.main_window:
            await update.message.reply_text("✅ Stop signal sent to GUI.")
            QMetaObject.invokeMethod(self.main_window, "stop_test", Qt.ConnectionType.QueuedConnection)
        else:
            await update.message.reply_text("❌ Cannot stop test: GUI not available.")

    async def _handle_status(self, update: 'Update', context: 'ContextTypes.DEFAULT_TYPE'):
        status_msg = (
            f"*Current Status:* {app_state.current_phase}\n"
            f"*Progress:* {app_state.progress}/{app_state.total}\n"
            f"*Working Configs:* {app_state.found} | *Failed:* {app_state.failed}\n"
            f"*Success Rate:* {app_state.success_rate:.1%}\n"
            f"*API Rate Limited:* {'Yes' if app_state.api_rate_limited else 'No'}"
        )
        await update.message.reply_text(status_msg, parse_mode="Markdown")

    async def _handle_results(self, update: 'Update', context: 'ContextTypes.DEFAULT_TYPE'):
        if not app_state.results:
            await update.message.reply_text("No results available yet.")
            return
            
        sorted_results = sorted(
            app_state.results, key=lambda x: (-x['download_speed'], x['ping'])
        )[:5]
        
        results_msg = "🚀 *Top 5 Configurations:*\n\n"
        for i, res in enumerate(sorted_results, 1):
            results_msg += (
                f"{i}. *{res['protocol'].upper()}* - `{res['address']}`\n"
                f"  ⏱️ {res['ping']}ms | 📶 {res['download_speed']}Mbps | "
                f" {res.get('country', 'N/A')}\n"
            )
        await update.message.reply_text(results_msg, parse_mode="Markdown")

    async def _handle_stats(self, update: 'Update', context: 'ContextTypes.DEFAULT_TYPE'):
        stats = app_state.stats
        if stats['total_tested'] == 0:
            await update.message.reply_text("No statistics available yet.")
            return
        
        stats_msg = (
            "*Performance Statistics*\n\n"
            f"📊 Total Tested: {stats['total_tested']}\n"
            f"✅ Success Rate: {(stats['total_success'] / stats['total_tested']):.1%}\n"
            f"⏱️ Avg Ping: {stats['avg_ping']:.0f}ms\n"
            f"📶 Avg Download: {stats['avg_download']:.2f}Mbps\n\n"
        )
        if stats['top_performer']:
            top = stats['top_performer']
            stats_msg += (
                f"🏆 Top Performer:\n"
                f"  *{top['protocol'].upper()}* - `{top['address']}`\n"
                f"  ⏱️ {top['ping']}ms | 📶 {top['download_speed']:.2f}Mbps"
            )
        await update.message.reply_text(stats_msg, parse_mode="Markdown")

# --- GUI Components ---
class BackendWorker(QThread):
    """
    Runs the asyncio event loop in a separate thread to keep the GUI responsive.
    """
    update_status = pyqtSignal(str)
    update_progress = pyqtSignal(int)
    set_progress_max = pyqtSignal(int)
    result_ready = pyqtSignal(dict)
    finished = pyqtSignal()
    current_test = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.orchestrator = TestOrchestrator(self)

    def run(self):
        try:
            asyncio.run(self.orchestrator.run_test_pipeline())
        except Exception as e:
            logger.critical(f"Backend worker crashed: {e}", exc_info=True)

    def stop(self):
        app_state.stop_signal.set()
        logger.info("Stop signal sent to backend worker.")

class SettingsDialog(QDialog):
    """Comprehensive settings dialog for managing application parameters."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enterprise Settings")
        self.setMinimumWidth(700)
        
        self.layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # Create tabs
        self.tabs.addTab(self._create_testing_tab(), "Testing")
        self.tabs.addTab(self._create_sources_tab(), "Sources")
        self.tabs.addTab(self._create_telegram_tab(), "Telegram")
        self.tabs.addTab(self._create_adaptive_tab(), "Adaptive")
        
        # Dialog buttons
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        
        self.layout.addWidget(self.tabs)
        self.layout.addWidget(self.buttonBox)
    
    def _create_testing_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        
        self.test_url_ping = QLineEdit(config.TEST_URL_PING)
        self.test_url_dl = QLineEdit(config.TEST_URL_DOWNLOAD)
        self.test_url_ul = QLineEdit(config.TEST_URL_UPLOAD)
        self.censorship_url = QLineEdit(config.CENSORSHIP_CHECK_URL)
        self.max_concurrent = QLineEdit(str(config.MAX_CONCURRENT_TESTS))
        self.timeout = QLineEdit(str(config.TEST_TIMEOUT))
        self.retry_count = QLineEdit(str(config.NETWORK_RETRY_COUNT))
        self.doh_resolver = QLineEdit(config.DOH_RESOLVER_URL)
        
        layout.addRow("Ping Test URL:", self.test_url_ping)
        layout.addRow("Download Test URL:", self.test_url_dl)
        layout.addRow("Upload Test URL:", self.test_url_ul)
        layout.addRow("Censorship Check URL:", self.censorship_url)
        layout.addRow("Max Concurrent Tests:", self.max_concurrent)
        layout.addRow("Test Timeout (s):", self.timeout)
        layout.addRow("Network Retry Count:", self.retry_count)
        layout.addRow("DNS-over-HTTPS URL:", self.doh_resolver)
        
        return widget
    
    def _create_sources_tab(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # Aggregators
        agg_group = QGroupBox("Aggregator Links")
        agg_layout = QVBoxLayout(agg_group)
        self.agg_list = QListWidget()
        self.agg_list.addItems(config.AGGREGATOR_LINKS)
        self.agg_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        
        agg_btn_layout = QHBoxLayout()
        btn_add_agg = QPushButton("Add")
        btn_remove_agg = QPushButton("Remove")
        btn_add_agg.clicked.connect(self._add_aggregator)
        btn_remove_agg.clicked.connect(lambda: self._remove_selected(self.agg_list))
        agg_btn_layout.addWidget(btn_add_agg)
        agg_btn_layout.addWidget(btn_remove_agg)
        agg_layout.addWidget(self.agg_list)
        agg_layout.addLayout(agg_btn_layout)
        
        # Direct Sources
        direct_group = QGroupBox("Direct Subscription Links")
        direct_layout = QVBoxLayout(direct_group)
        self.direct_list = QListWidget()
        self.direct_list.addItems(config.DIRECT_CONFIG_SOURCES)
        self.direct_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        
        direct_btn_layout = QHBoxLayout()
        btn_add_direct = QPushButton("Add")
        btn_remove_direct = QPushButton("Remove")
        btn_add_direct.clicked.connect(self._add_direct_source)
        btn_remove_direct.clicked.connect(lambda: self._remove_selected(self.direct_list))
        direct_btn_layout.addWidget(btn_add_direct)
        direct_btn_layout.addWidget(btn_remove_direct)
        direct_layout.addWidget(self.direct_list)
        direct_layout.addLayout(direct_btn_layout)
        
        layout.addWidget(agg_group)
        layout.addWidget(direct_group)
        return widget

    def _create_telegram_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        self.bot_token = QLineEdit(config.TELEGRAM_BOT_TOKEN)
        self.admin_id = QLineEdit(config.TELEGRAM_ADMIN_ID)
        self.target_ids = QLineEdit(','.join(config.TELEGRAM_TARGET_IDS))
        
        layout.addRow("Bot Token:", self.bot_token)
        layout.addRow("Admin User ID:", self.admin_id)
        layout.addRow("Target IDs (comma-separated):", self.target_ids)
        return widget
    
    def _create_adaptive_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        self.adaptive_enabled = QCheckBox("Enable Adaptive Testing")
        self.adaptive_enabled.setChecked(config.ADAPTIVE_TESTING)
        self.batch_min = QLineEdit(str(config.ADAPTIVE_BATCH_MIN))
        self.batch_max = QLineEdit(str(config.ADAPTIVE_BATCH_MAX))
        self.sleep_min = QLineEdit(str(config.ADAPTIVE_SLEEP_MIN))
        self.sleep_max = QLineEdit(str(config.ADAPTIVE_SLEEP_MAX))
        
        layout.addRow(self.adaptive_enabled)
        layout.addRow("Minimum Batch Size:", self.batch_min)
        layout.addRow("Maximum Batch Size:", self.batch_max)
        layout.addRow("Minimum Sleep Time (s):", self.sleep_min)
        layout.addRow("Maximum Sleep Time (s):", self.sleep_max)
        return widget
    
    def _add_item_to_list(self, list_widget, title, label):
        text, ok = QInputDialog.getText(self, title, label)
        if ok and text.strip():
            list_widget.addItem(text.strip())

    def _add_aggregator(self):
        self._add_item_to_list(self.agg_list, "Add Aggregator", "Enter aggregator URL:")
    
    def _add_direct_source(self):
        self._add_item_to_list(self.direct_list, "Add Direct Source", "Enter direct source URL:")
        
    def _remove_selected(self, list_widget: QListWidget):
        if list_widget.currentItem():
            list_widget.takeItem(list_widget.currentRow())

    def accept(self):
        """Saves all settings when OK is clicked."""
        try:
            # Testing Settings
            config.TEST_URL_PING = self.test_url_ping.text()
            config.TEST_URL_DOWNLOAD = self.test_url_dl.text()
            config.TEST_URL_UPLOAD = self.test_url_ul.text()
            config.CENSORSHIP_CHECK_URL = self.censorship_url.text()
            config.MAX_CONCURRENT_TESTS = int(self.max_concurrent.text())
            config.TEST_TIMEOUT = int(self.timeout.text())
            config.NETWORK_RETRY_COUNT = int(self.retry_count.text())
            config.DOH_RESOLVER_URL = self.doh_resolver.text()
            
            # Source Lists
            config.AGGREGATOR_LINKS = [self.agg_list.item(i).text() for i in range(self.agg_list.count())]
            config.DIRECT_CONFIG_SOURCES = [self.direct_list.item(i).text() for i in range(self.direct_list.count())]
            
            # Telegram Settings
            config.TELEGRAM_BOT_TOKEN = self.bot_token.text()
            config.TELEGRAM_ADMIN_ID = self.admin_id.text()
            config.TELEGRAM_TARGET_IDS = [tid.strip() for tid in self.target_ids.text().split(',') if tid.strip()]
            
            # Adaptive Settings
            config.ADAPTIVE_TESTING = self.adaptive_enabled.isChecked()
            config.ADAPTIVE_BATCH_MIN = int(self.batch_min.text())
            config.ADAPTIVE_BATCH_MAX = int(self.batch_max.text())
            config.ADAPTIVE_SLEEP_MIN = float(self.sleep_min.text())
            config.ADAPTIVE_SLEEP_MAX = float(self.sleep_max.text())
            
            config.save_settings()
            super().accept()
        except ValueError as e:
            QMessageBox.critical(self, "Invalid Input", f"Please check your settings. A numeric value is incorrect.\n\nError: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving", f"Could not save settings.\n\nError: {e}")

class MainWindow(QMainWindow):
    """The main application window with enhanced UI features."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.setMinimumSize(1200, 800)
        
        if os.path.exists(config.ICON_PATH):
            self.setWindowIcon(QIcon(config.ICON_PATH))
        
        self.worker = None
        self.telegram_manager = TelegramManager(self) # Pass self reference
        self.telegram_initialized = self.telegram_manager.initialize()
        
        self._init_ui()
        self._load_previous_results()
    
    def _init_ui(self):
        """Initializes the user interface."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        self._init_top_controls()
        self._init_filter_controls()
        self._init_results_table()
        self._init_status_bar()
        self._init_menu_bar()
        self._init_system_tray()
    
    def _init_top_controls(self):
        top_layout = QHBoxLayout()
        self.btn_start = QPushButton("🚀 Start Test")
        self.btn_stop = QPushButton("🛑 Stop Test")
        self.btn_export = QPushButton("📄 Export Results")
        self.btn_settings = QPushButton("⚙️ Settings")
        self.btn_stats = QPushButton("📊 Statistics")
        
        self.btn_stop.setEnabled(False)
        
        self.btn_start.clicked.connect(self.start_test)
        self.btn_stop.clicked.connect(self.stop_test)
        self.btn_export.clicked.connect(self.export_results)
        self.btn_settings.clicked.connect(self.open_settings)
        self.btn_stats.clicked.connect(self.show_stats)
        
        top_layout.addWidget(self.btn_start)
        top_layout.addWidget(self.btn_stop)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_export)
        top_layout.addWidget(self.btn_stats)
        top_layout.addWidget(self.btn_settings)
        self.layout.addLayout(top_layout)

    def _init_filter_controls(self):
        filter_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter results by any column (address, country, etc.)...")
        self.filter_input.textChanged.connect(self.filter_table)
        
        self.protocol_filter = QComboBox()
        self.protocol_filter.addItem("All Protocols")
        self.protocol_filter.addItems(sorted(config.PROTOCOL_WHITELIST))
        self.protocol_filter.currentIndexChanged.connect(self.filter_table)
        
        self.country_filter = QComboBox()
        self.country_filter.addItem("All Countries")
        self.country_filter.currentIndexChanged.connect(self.filter_table)
        
        filter_layout.addWidget(QLabel("Filter:"))
        filter_layout.addWidget(self.filter_input, 4)
        filter_layout.addWidget(QLabel("Protocol:"))
        filter_layout.addWidget(self.protocol_filter, 2)
        filter_layout.addWidget(QLabel("Country:"))
        filter_layout.addWidget(self.country_filter, 2)
        self.layout.addLayout(filter_layout)

    def _init_results_table(self):
        self.table = QTableWidget()
        self.columns = [
            "Protocol", "Address", "Country", "Ping (ms)", "Jitter (ms)",
            "DL (Mbps)", "UL (Mbps)", "Bypassing"
        ]
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        self.layout.addWidget(self.table, 1)

    def _init_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedWidth(200)
        
        self.status_label = QLabel("Ready")
        self.current_test_label = QLabel("Current: None")
        self.current_test_label.setMinimumWidth(300)
        
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.addWidget(self.current_test_label, 2)
        
        self.update_status(f"Ready. Developed by {config.AUTHOR_NAME}")

    def _init_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        export_action = QAction("Export Results", self)
        export_action.triggered.connect(self.export_results)
        file_menu.addAction(export_action)
        import_action = QAction("Import Results", self)
        import_action.triggered.connect(self.import_results)
        file_menu.addAction(import_action)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        tools_menu = menubar.addMenu("Tools")
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        tools_menu.addAction(settings_action)
        
        help_menu = menubar.addMenu("Help")
        docs_action = QAction("Documentation (GitHub)", self)
        docs_action.triggered.connect(self.open_documentation)
        help_menu.addAction(docs_action)
        update_action = QAction("Check for Updates", self)
        update_action.triggered.connect(self.check_for_updates)
        help_menu.addAction(update_action)
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _init_system_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
            
        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists(config.ICON_PATH):
            self.tray_icon.setIcon(QIcon(config.ICON_PATH))
        
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)
        
        start_action = tray_menu.addAction("Start Test")
        start_action.triggered.connect(self.start_test)
        
        stop_action = tray_menu.addAction("Stop Test")
        stop_action.triggered.connect(self.stop_test)
        
        tray_menu.addSeparator()
        exit_action = tray_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def _load_previous_results(self):
        """Loads previous results from file."""
        if not os.path.exists(config.RESULTS_FILE): return
        try:
            with open(config.RESULTS_FILE, 'r', encoding='utf-8') as f:
                results = json.load(f)
                for result in results:
                    self.add_result_to_table(result)
                    app_state.results.append(result)
                    app_state.update_stats(result)
            self.update_status(f"Loaded {len(results)} previous results.")
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to load previous results: {e}")
            os.remove(config.RESULTS_FILE) # Remove corrupted file
            
    def start_test(self):
        """Starts the configuration testing process."""
        if app_state.is_running:
            QMessageBox.warning(self, "Test Running", "A test is already in progress.")
            return

        self.table.setRowCount(0)
        app_state.reset()
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        
        self.worker = BackendWorker()
        self.worker.update_status.connect(self.update_status)
        self.worker.update_progress.connect(self.update_progress)
        self.worker.set_progress_max.connect(self.set_progress_max)
        self.worker.result_ready.connect(self.add_result_to_table)
        self.worker.current_test.connect(self.update_current_test)
        self.worker.finished.connect(self.on_test_finished)
        self.worker.start()
        
        if self.telegram_initialized and self.telegram_manager.loop:
            asyncio.run_coroutine_threadsafe(
                self.telegram_manager.log_to_admin("Test started from GUI."),
                self.telegram_manager.loop
            )

    def stop_test(self):
        """Stops the ongoing test."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.update_status("Stop signal sent. Finishing current tasks...")

            if self.telegram_initialized and self.telegram_manager.loop:
                asyncio.run_coroutine_threadsafe(
                    self.telegram_manager.log_to_admin("Test stopped from GUI."),
                    self.telegram_manager.loop
                )

    def on_test_finished(self):
        """Called when the backend worker finishes."""
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        
        final_msg = f"Test complete. Found {self.table.rowCount()} working configurations."
        self.update_status(final_msg)
        self.progress_bar.setValue(0)
        self.current_test_label.setText("Current: None")
        
        try:
            with open(config.RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(app_state.results, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
        
        if self.telegram_initialized and self.telegram_manager.loop and self.table.rowCount() > 0:
            self._share_top_results_telegram()

    def _share_top_results_telegram(self):
        """Sends top results to Telegram targets."""
        sorted_results = sorted(
            app_state.results, key=lambda x: (-x['download_speed'], x['ping'])
        )[:3]
        
        message = f"🚀 *{config.APP_NAME} Test Finished*\n"
        message += f"Found *{len(app_state.results)}* working configs.\n\n"
        message += "*Top 3 Results:*\n"
        for i, res in enumerate(sorted_results, 1):
            message += (
                f"\n*{i}. {res['protocol'].upper()}* - `{res['address']}`\n"
                f"  `{res['uri']}`"
            )
        
        asyncio.run_coroutine_threadsafe(
            self.telegram_manager.send_to_targets(message, parse_mode="Markdown"),
            self.telegram_manager.loop
        )
        
    def update_status(self, message: str):
        self.status_label.setText(message)
    
    def update_progress(self, value: int):
        self.progress_bar.setValue(value)
    
    def set_progress_max(self, max_value: int):
        self.progress_bar.setMaximum(max_value)
    
    def update_current_test(self, uri: str):
        display_uri = uri[:30] + "..." + uri[-30:] if len(uri) > 60 else uri
        self.current_test_label.setText(f"Current: {display_uri}")
    
    def add_result_to_table(self, result: dict):
        """Adds a test result to the results table."""
        self.table.setSortingEnabled(False)
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Store full result data in the first item
        protocol_item = QTableWidgetItem(result['protocol'].upper())
        protocol_item.setData(Qt.ItemDataRole.UserRole, result)
        self.table.setItem(row, 0, protocol_item)
        
        self.table.setItem(row, 1, QTableWidgetItem(result['address']))
        
        # Country and update filter
        country = result.get('country', 'N/A')
        self.table.setItem(row, 2, QTableWidgetItem(country))
        current_countries = [self.country_filter.itemText(i) for i in range(self.country_filter.count())]
        if country not in current_countries and country != "N/A":
            self.country_filter.addItem(country)
            self.country_filter.model().sort(0)

        # Numerical items for correct sorting
        for col, key, default_val in [(3, 'ping', 9999), (4, 'jitter', 9999), (5, 'download_speed', 0.0), (6, 'upload_speed', 0.0)]:
             item = QTableWidgetItem()
             item.setData(Qt.ItemDataRole.EditRole, result.get(key, default_val))
             self.table.setItem(row, col, item)
        
        bypass_text = "✅ Yes" if result.get('is_bypassing') else "❌ No"
        bypass_item = QTableWidgetItem(bypass_text)
        bypass_item.setForeground(QColor('green') if result.get('is_bypassing') else QColor('red'))
        bypass_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 7, bypass_item)
        
        self.table.setSortingEnabled(True)

    def filter_table(self):
        """Filters the table based on the current filter criteria."""
        filter_text = self.filter_input.text().lower()
        protocol_filter = self.protocol_filter.currentText()
        country_filter = self.country_filter.currentText()
        
        for row in range(self.table.rowCount()):
            protocol_item = self.table.item(row, 0)
            country_item = self.table.item(row, 2)
            
            protocol_match = (protocol_filter == "All Protocols" or 
                              (protocol_item and protocol_item.text().lower() == protocol_filter.lower()))
            
            country_match = (country_filter == "All Countries" or
                             (country_item and country_item.text() == country_filter))
            
            text_match = not filter_text or any(
                filter_text in (self.table.item(row, col).text() or "").lower()
                for col in range(self.table.columnCount())
                if self.table.item(row, col)
            )

            self.table.setRowHidden(row, not (protocol_match and country_match and text_match))

    def show_context_menu(self, pos):
        """Shows a context menu for table rows."""
        item = self.table.itemAt(pos)
        if not item: return
        
        row = item.row()
        result_data = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not result_data: return
            
        menu = QMenu()
        copy_uri = menu.addAction("Copy URI")
        copy_address = menu.addAction("Copy Address")
        view_config = menu.addAction("View Config JSON")
        share_action = menu.addAction("Share via Telegram")
        share_action.setEnabled(self.telegram_initialized)
        open_location = menu.addAction("Open Location Info (ipinfo.io)")
        
        action = menu.exec(self.table.mapToGlobal(pos))
        
        if action == copy_uri and result_data.get('uri'):
            QApplication.clipboard().setText(result_data['uri'])
            self.update_status("Copied URI to clipboard.")
        elif action == copy_address:
            QApplication.clipboard().setText(result_data['address'])
            self.update_status("Copied address to clipboard.")
        elif action == view_config:
            self._view_config_json(result_data['config_json'])
        elif action == share_action and result_data.get('uri'):
            self._share_via_telegram(result_data)
        elif action == open_location:
            self._open_location_info(result_data['ip'])

    def _view_config_json(self, config_json: dict):
        dialog = QDialog(self)
        dialog.setWindowTitle("Configuration JSON")
        dialog.setMinimumSize(600, 400)
        layout = QVBoxLayout(dialog)
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(json.dumps(config_json, indent=2))
        text_edit.setFont(QFont("Courier New", 10))
        layout.addWidget(text_edit)
        dialog.exec()

    def _share_via_telegram(self, result: dict):
        if not self.telegram_initialized or not self.telegram_manager.loop: return
        
        message = f"`{result['uri']}`"
        asyncio.run_coroutine_threadsafe(
            self.telegram_manager.send_to_targets(message, parse_mode="Markdown"),
            self.telegram_manager.loop
        )
        self.update_status("Configuration shared via Telegram.")

    def _open_location_info(self, ip: str):
        if ip: webbrowser.open(f"https://ipinfo.io/{ip}")

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            QMessageBox.information(self, "Settings Saved", "Your settings have been updated.")
            # Re-check Telegram status
            self.telegram_initialized = self.telegram_manager.initialize()

    def export_results(self):
        """Exports the current visible results to a file."""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Results", "There are no results to export.")
            return
            
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Visible Results", "", "Subscription File (*.txt);;Base64 Subscription (*.txt);;JSON (*.json)"
        )
        if not file_path: return
            
        results = []
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                result = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                if result and result.get('uri'):
                    results.append(result)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                uris = [r['uri'] for r in results]
                if "Base64" in selected_filter:
                    f.write(base64.b64encode("\n".join(uris).encode('utf-8')).decode('utf-8'))
                elif "JSON" in selected_filter:
                    json.dump(results, f, indent=2) # Export full data for JSON
                else: # Plain text
                    f.write("\n".join(uris))
            
            self.update_status(f"Exported {len(results)} results to {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export results: {e}")

    def import_results(self):
        """Imports results from a file (URIs or full JSON)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Results", "", "JSON (*.json);;Text File (*.txt)"
        )
        if not file_path: return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                imported_count = 0
                if file_path.endswith('.json'):
                    data = json.load(f)
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        # It's a full result file
                        for result in data:
                            self.add_result_to_table(result)
                            app_state.results.append(result)
                            imported_count += 1
                else: # Plain text or base64
                    try: # Try base64 first
                        uris_text = base64.b64decode(content).decode('utf-8')
                    except: # Fallback to plain text
                        uris_text = content
                    
                    uris = [line.strip() for line in uris_text.splitlines() if line.strip()]
                    for uri in uris:
                        result = {
                            'uri': uri, 'protocol': uri.split('://')[0],
                            'address': 'Imported', 'country': 'N/A', 'ping': 0, 'jitter': 0,
                            'download_speed': 0, 'upload_speed': 0, 'is_bypassing': False,
                            'config_json': {}
                        }
                        self.add_result_to_table(result)
                        app_state.results.append(result)
                        imported_count += 1
            
            self.update_status(f"Imported {imported_count} configurations.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import results: {e}")

    def show_stats(self):
        stats = app_state.stats
        if stats['total_tested'] == 0:
            QMessageBox.information(self, "Statistics", "No test data available yet.")
            return
            
        msg = QMessageBox(self)
        msg.setWindowTitle("Performance Statistics")
        msg.setIcon(QMessageBox.Icon.Information)
        
        message = (
            f"<b>Total Tested:</b> {stats['total_tested']}<br>"
            f"<b>Success Rate:</b> {(stats['total_success'] / stats['total_tested']):.1%}<br>"
            f"<b>Average Ping:</b> {stats['avg_ping']:.0f}ms<br>"
            f"<b>Average Download Speed:</b> {stats['avg_download']:.2f}Mbps<br><br>"
        )
        if stats['top_performer']:
            top = stats['top_performer']
            message += (
                f"<b>🏆 Top Performer:</b><br>"
                f"  <b>Protocol:</b> {top['protocol'].upper()}<br>"
                f"  <b>Address:</b> {top['address']}<br>"
                f"  <b>Speed:</b> {top['download_speed']:.2f}Mbps"
            )
        msg.setText(message)
        msg.exec()
    
    def open_documentation(self):
        webbrowser.open("https://github.com/shayantaherkhani/v2ray-tester")
    
    def check_for_updates(self):
        self.update_status("Checking for updates...")
        try:
            response = requests.get("https://api.github.com/repos/shayantaherkhani/v2ray-tester/releases/latest", timeout=5)
            response.raise_for_status()
            release = response.json()
            latest_version = release['tag_name'].lstrip('v')
            
            if latest_version > config.APP_VERSION:
                if QMessageBox.question(self, "Update Available", 
                    f"Version {latest_version} is available! Would you like to go to the download page?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                ) == QMessageBox.StandardButton.Yes:
                    webbrowser.open(release['html_url'])
            else:
                QMessageBox.information(self, "No Updates", "You are using the latest version.")
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Error checking for updates: {e}")
        self.update_status("Ready")
    
    def show_about(self):
        about_text = (
            f"<b>{config.APP_NAME} v{config.APP_VERSION}</b><br><br>"
            "Advanced tool for discovering and testing V2Ray/Xray configurations.<br><br>"
            f"Developed by: <b>{config.AUTHOR_NAME}</b><br>"
            f"Website: <a href='{config.AUTHOR_WEBSITE}'>{config.AUTHOR_WEBSITE}</a>"
        )
        QMessageBox.about(self, "About", about_text)
    
    def closeEvent(self, event):
        """Handles the window close event."""
        if app_state.is_running:
            if QMessageBox.question(self, "Test Running", 
                "A test is running. Are you sure you want to quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.No:
                event.ignore()
                return
            
            if self.worker: self.worker.stop()
        
        # Save results
        try:
            with open(config.RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(app_state.results, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save results on exit: {e}")
            
        event.accept()

# --- CLI Interface ---
class CLIDashboard:
    """Provides a rich command-line interface for the application."""
    def __init__(self):
        self.console = Console()
        self.live = None
        self.layout = self._make_layout()
        self.worker_thread = None

    def _make_layout(self) -> Layout:
        """Defines the CLI layout."""
        layout = Layout(name="root")
        layout.split(
            Layout(name="header", size=3),
            Layout(ratio=1, name="main"),
            Layout(size=5, name="footer"),
        )
        layout["main"].split_row(Layout(name="results"), Layout(name="status"))
        return layout

    def run(self):
        """Runs the CLI interface."""
        self.worker_app = QApplication([]) # A dummy Qt app is needed for QThread signals
        
        self._init_display()
        self.worker = BackendWorker()
        self.worker.update_status.connect(self._update_status)
        self.worker.update_progress.connect(self._update_progress)
        self.worker.set_progress_max.connect(self._set_progress_max)
        self.worker.result_ready.connect(self._add_result)
        self.worker.current_test.connect(self._update_current_test)
        self.worker.finished.connect(self._on_finished)

        try:
            with Live(self.layout, screen=True, redirect_stderr=False, transient=True) as self.live:
                self.worker.start()
                while self.worker.isRunning():
                    self.worker_app.processEvents()
                    time.sleep(0.1)
                self.worker_app.processEvents() # Process any final signals
        except KeyboardInterrupt:
            if self.worker.isRunning():
                self.worker.stop()
            self.console.print("\n[red]Test stopped by user.[/red]")
        except Exception as e:
            self.console.print(f"\n[bold red]An unexpected error occurred: {e}[/bold red]")
        finally:
            self.worker_app.quit()
    
    def _init_display(self):
        self.layout["header"].update(Panel(f"[bold white]{config.APP_NAME} v{config.APP_VERSION}[/bold white]\nby [cyan]{config.AUTHOR_NAME}[/cyan]", border_style="blue"))
        
        self.progress = Progress("{task.description}", "{task.percentage:>3.0f}%", console=self.console)
        self.progress_task = self.progress.add_task("[green]Starting...", total=100)
        
        self.results_table = Table(title="Top 5 Configurations", header_style="bold magenta", box=None)
        self.results_table.add_column("Proto", style="cyan", width=8)
        self.results_table.add_column("Address", style="green", width=30)
        self.results_table.add_column("Ping", justify="right", width=6)
        self.results_table.add_column("Speed", justify="right", width=12)
        self.results_table.add_column("Bypass", justify="center", width=6)
        
        self.layout["results"].update(Panel(self.results_table, title="Results", border_style="green"))
        status_panel = Panel(self.progress, title="Status", border_style="yellow")
        self.layout["status"].update(status_panel)
        self.layout["footer"].update(Panel("Press Ctrl+C to stop the test.", title="Info", border_style="red"))

    def _update_status(self, message: str):
        self.progress.update(self.progress_task, description=f"[bold green]{message}[/bold green]")
    
    def _update_progress(self, value: int):
        self.progress.update(self.progress_task, completed=value)

    def _set_progress_max(self, max_value: int):
        self.progress.update(self.progress_task, total=max_value)
    
    def _update_current_test(self, uri: str):
        pass # Status is updated via update_status

    def _add_result(self, result: dict):
        if len(self.results_table.rows) >= 5:
            self.results_table.rows.pop(0)
            
        self.results_table.add_row(
            result['protocol'].upper(),
            result['address'],
            f"{result['ping']}ms",
            f"{result['download_speed']}Mbps",
            "[green]✅[/green]" if result['is_bypassing'] else "[red]❌[/red]"
        )

    def _on_finished(self):
        self.progress.update(self.progress_task, description="[bold blue]Test complete![/bold blue]")
        self.layout["footer"].update(Panel("Test finished. You can close this window.", border_style="green"))
        
# --- Application Entry Point ---
def ensure_xray_core():
    """Checks for the Xray core and provides guidance if not found."""
    if not os.path.exists(config.XRAY_PATH):
        error_msg = (
            f"FATAL ERROR: Xray core not found at '{config.XRAY_PATH}'\n\n"
            "Please download the Xray core for your OS, place it in the same directory "
            "as this application, and rename it to 'xray' (or 'xray.exe' on Windows).\n\n"
            "Download from: https://github.com/XTLS/Xray-core/releases"
        )
        try:
            # Try to show a GUI message box first
            app = QApplication(sys.argv)
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("Xray Core Not Found")
            msg.setInformativeText(error_msg)
            msg.setWindowTitle("Error")
            msg.exec()
        except Exception:
            # Fallback to console if GUI fails
            console.print(f"[bold red]{error_msg}[/bold red]")
        sys.exit(1)

def main():
    """Main entry point to run either GUI or CLI."""
    ensure_xray_core()
    
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("--cli", "-c"):
        main_cli()
    else:
        main_gui()

def main_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

def main_cli():
    dashboard = CLIDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()
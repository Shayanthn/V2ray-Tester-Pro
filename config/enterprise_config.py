import os
import json
import sys
import platform
from typing import Set, List
from dotenv import load_dotenv

class EnterpriseConfig:
    """
    Enhanced configuration management with persistence and validation.
    """
    def __init__(self):
        # Application Metadata
        self.APP_NAME = "V2Ray/Xray Enterprise"
        self.APP_VERSION = "5.1.2"
        self.AUTHOR_NAME = "Shayan Taherkhani"
        self.AUTHOR_WEBSITE = "https://shayantaherkhani.ir"
        
        # Path Configuration
        self._set_paths()
        
        # Load environment variables
        load_dotenv()
        
        # Network Configuration
        self.TEST_URL_PING = os.getenv('TEST_URL_PING', "https://www.google.com/generate_204")
        self.TEST_URL_DOWNLOAD = os.getenv('TEST_URL_DOWNLOAD', "https://speed.cloudflare.com/__down?bytes=5000000")
        self.TEST_URL_UPLOAD = os.getenv('TEST_URL_UPLOAD', "https://speed.cloudflare.com/__up")
        self.CENSORSHIP_CHECK_URL = os.getenv('CENSORSHIP_CHECK_URL', "https://www.youtube.com")
        
        # Real-World Connection Test Targets
        self.TEST_URL_TELEGRAM = os.getenv('TEST_URL_TELEGRAM', "https://api.telegram.org")
        self.TEST_URL_INSTAGRAM = os.getenv('TEST_URL_INSTAGRAM', "https://www.instagram.com")
        self.TEST_URL_YOUTUBE = os.getenv('TEST_URL_YOUTUBE', "https://www.youtube.com")
        
        self.TEST_TIMEOUT = int(os.getenv('TEST_TIMEOUT', 10))
        self.MAX_CONCURRENT_TESTS = int(os.getenv('MAX_CONCURRENT_TESTS', 20))
        self.NETWORK_RETRY_COUNT = int(os.getenv('NETWORK_RETRY_COUNT', 5))
        self.DOH_RESOLVER_URL = os.getenv('DOH_RESOLVER_URL', "https://cloudflare-dns.com/dns-query")
        
        # GeoIP Configuration
        self.GEOIP_DB_PATH = os.getenv('GEOIP_DB_PATH', os.path.join(self.DATA_DIR, "GeoLite2-City.mmdb"))
        
        # Security Configuration
        self.IP_BLACKLIST: Set[str] = set(json.loads(os.getenv('IP_BLACKLIST', '[]')))
        self.DOMAIN_BLACKLIST: Set[str] = set(json.loads(os.getenv('DOMAIN_BLACKLIST', '[]')))
        self.PROTOCOL_WHITELIST: Set[str] = {'vmess', 'vless', 'trojan', 'shadowsocks', 'ss', 'tuic', 'hysteria2'}
        self.BANNED_PAYLOADS: Set[str] = {'exec', 'system', 'eval', 'shutdown', 'rm ', 'del ', 'format'}
        self.MAX_URI_LENGTH = int(os.getenv('MAX_URI_LENGTH', 4096))
        
        # Source Configuration
        self.AGGREGATOR_LINKS: List[str] = json.loads(os.getenv('AGGREGATOR_LINKS', json.dumps([])))
        self.DIRECT_CONFIG_SOURCES: List[str] = json.loads(os.getenv('DIRECT_CONFIG_SOURCES', json.dumps([
            # --- M-Mashreghi/Free-V2ray-Collector ---
            "https://raw.githubusercontent.com/M-Mashreghi/Free-V2ray-Collector/main/All_Configs_Sub.txt",
            "https://raw.githubusercontent.com/M-Mashreghi/Free-V2ray-Collector/main/All_shuffled_config.txt",
            "https://raw.githubusercontent.com/M-Mashreghi/Free-V2ray-Collector/main/Files/shuffle/Sub1_shuffled.conf",
            "https://raw.githubusercontent.com/M-Mashreghi/Free-V2ray-Collector/main/Splitted-By-Protocol/vmess.txt",
            "https://raw.githubusercontent.com/M-Mashreghi/Free-V2ray-Collector/main/Splitted-By-Protocol/vless.txt",
            "https://raw.githubusercontent.com/M-Mashreghi/Free-V2ray-Collector/main/Splitted-By-Protocol/trojan.txt",
            "https://raw.githubusercontent.com/M-Mashreghi/Free-V2ray-Collector/main/Splitted-By-Protocol/ss.txt",
            "https://raw.githubusercontent.com/M-Mashreghi/Free-V2ray-Collector/main/Splitted-By-Protocol/ssr.txt",

            # --- ebrasha/free-v2ray-public-list ---
            "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/all_extracted_configs.txt",
            "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/V2Ray-Config-By-EbraSha-All-Type.txt",
            "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vmess_configs.txt",
            "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vless_configs.txt",

            # --- ALIILAPRO/v2rayNG-Config ---
            "https://raw.githubusercontent.com/ALIILAPRO/v2rayNG-Config/main/sub.txt",
            "https://raw.githubusercontent.com/ALIILAPRO/v2rayNG-Config/main/server.txt",
            "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
            "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt",

            # --- barry-far/V2ray-Config ---
            "https://raw.githubusercontent.com/barry-far/V2ray-config/main/All_Configs_Sub.txt",
            "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Splitted-By-Protocol/vmess.txt",
            "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Splitted-By-Protocol/vless.txt",
            "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Splitted-By-Protocol/trojan.txt",
            "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Sub1.txt",
            "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Sub2.txt",
            "https://raw.githubusercontent.com/barry-far/V2ray-config/main/Sub3.txt",

            # --- Firmfox/Proxify ---
            "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/mixed/subscription-1.txt",
            "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/mixed/subscription-2.txt",
            "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/seperated_by_protocol/vmess.txt",
            "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/seperated_by_protocol/vless.txt",

            # --- miladtahanian/V2RayCFGDumper ---
            "https://raw.githubusercontent.com/miladtahanian/V2RayCFGDumper/main/config.txt",

            # --- MhdiTaheri/V2rayCollector ---
            "https://raw.githubusercontent.com/MhdiTaheri/V2rayCollector/main/sub/mix",
            "https://raw.githubusercontent.com/MhdiTaheri/V2rayCollector/main/sub/vless",
            "https://raw.githubusercontent.com/MhdiTaheri/V2rayCollector/main/sub/vmess",
            "https://raw.githubusercontent.com/MhdiTaheri/V2rayCollector/main/sub/trojan",

            # --- Pawdroid/Free-servers ---
            "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",

            # --- nyeinkokoaung404/V2ray-Configs ---
            "https://raw.githubusercontent.com/nyeinkokoaung404/V2ray-Configs/main/All_Configs_Sub.txt",
            "https://raw.githubusercontent.com/nyeinkokoaung404/V2ray-Configs/main/All_Configs_base64_Sub.txt",

            # --- sevcator/5ubscrpt10n ---
            "https://raw.githubusercontent.com/sevcator/5ubscrpt10n/main/protocols/vl.txt",
            "https://raw.githubusercontent.com/sevcator/5ubscrpt10n/main/protocols/vm.txt",
            "https://raw.githubusercontent.com/sevcator/5ubscrpt10n/main/protocols/tr.txt",

            # --- xiaoji235/airport-free ---
            "https://raw.githubusercontent.com/xiaoji235/airport-free/main/v2ray.txt",

            # --- HuangYurong123/p-configs ---
            "https://raw.githubusercontent.com/HuangYurong123/p-configs/main/Clash-Profiles/clash-profiles.yaml",

            # --- Hamid-gh/xray-subscription ---
            "https://raw.githubusercontent.com/Hamid-gh/xray-subscription/main/all.txt",

            # --- yebekhe/TelegramV2rayCollector ---
            "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/mix",
            "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/vless",

            # --- mahdibland/V2RayAggregator ---
            "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/Eternity",
            "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt"
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
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.DATA_DIR = base_dir
        
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
            print(f"Warning: Failed to load settings from {self.CONFIG_FILE}: {e}")

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
            print(f"Error: Failed to save settings to {self.CONFIG_FILE}: {e}")

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
        self.APP_VERSION = "5.4.0"
        self.AUTHOR_NAME = "Shayan Taherkhani"
        self.AUTHOR_WEBSITE = "https://shayantaherkhani.ir"
        
        # Path Configuration
        self._set_paths()
        
        # Load environment variables
        load_dotenv()
        
        # Network Configuration
        self.TEST_URL_PING = os.getenv('TEST_URL_PING', "https://www.google.com/generate_204")
        self.TEST_URL_PING_FALLBACK = os.getenv('TEST_URL_PING_FALLBACK', "https://1.1.1.1")
        self.TEST_URL_DOWNLOAD = os.getenv('TEST_URL_DOWNLOAD', "https://speed.cloudflare.com/__down?bytes=5000000")
        self.TEST_URL_UPLOAD = os.getenv('TEST_URL_UPLOAD', "https://speed.cloudflare.com/__up")
        self.CENSORSHIP_CHECK_URL = os.getenv('CENSORSHIP_CHECK_URL', "https://www.youtube.com")
        self.DOMESTIC_CHECK_URL = os.getenv('DOMESTIC_CHECK_URL', "https://www.aparat.com")
        
        # Real-World Connection Test Targets
        self.TEST_URL_TELEGRAM = os.getenv('TEST_URL_TELEGRAM', "https://api.telegram.org")
        self.TEST_URL_INSTAGRAM = os.getenv('TEST_URL_INSTAGRAM', "https://www.instagram.com")
        self.TEST_URL_YOUTUBE = os.getenv('TEST_URL_YOUTUBE', "https://www.youtube.com")
        
        self.TEST_TIMEOUT = int(os.getenv('TEST_TIMEOUT', 10))
        self.MAX_CONCURRENT_TESTS = int(os.getenv('MAX_CONCURRENT_TESTS', 50))
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
        self.SOURCES_FILE = os.path.join(self.DATA_DIR, "config", "sources.json")
        self.SOURCES_UPDATE_URL = os.getenv('SOURCES_UPDATE_URL', "")
        
        # Load sources from JSON file if exists, otherwise use defaults
        self._load_sources()

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

    def _load_sources(self):
        """Loads sources from JSON file or uses defaults."""
        self.AGGREGATOR_LINKS = []
        self.DIRECT_CONFIG_SOURCES = []
        
        # Default lists (Hardcoded fallback)
        default_direct = [
             "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/mix",
             "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt"
        ]
        
        if os.path.exists(self.SOURCES_FILE):
            try:
                with open(self.SOURCES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.AGGREGATOR_LINKS = data.get('aggregator_links', [])
                    self.DIRECT_CONFIG_SOURCES = data.get('direct_config_sources', default_direct)
            except Exception as e:
                print(f"Warning: Failed to load sources from {self.SOURCES_FILE}: {e}")
                self.DIRECT_CONFIG_SOURCES = default_direct
        else:
             # Create default file if not exists
             self.DIRECT_CONFIG_SOURCES = default_direct
             self._save_sources()

    def _save_sources(self):
        """Saves current sources to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.SOURCES_FILE), exist_ok=True)
            data = {
                'aggregator_links': self.AGGREGATOR_LINKS,
                'direct_config_sources': self.DIRECT_CONFIG_SOURCES
            }
            with open(self.SOURCES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error: Failed to save sources to {self.SOURCES_FILE}: {e}")

    def update_sources_from_remote(self):
        """Updates source list from a remote JSON file."""
        if not self.SOURCES_UPDATE_URL:
            # print("No SOURCES_UPDATE_URL configured. Skipping source update.")
            return
            
        import urllib.request
        import urllib.error
        
        print(f"Checking for source updates from {self.SOURCES_UPDATE_URL}...")
        try:
            with urllib.request.urlopen(self.SOURCES_UPDATE_URL, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    
                    new_direct = data.get('direct_config_sources', [])
                    new_agg = data.get('aggregator_links', [])
                    
                    if new_direct or new_agg:
                        # Merge strictly: union of sets
                        current_direct = set(self.DIRECT_CONFIG_SOURCES)
                        current_agg = set(self.AGGREGATOR_LINKS)
                        
                        for url in new_direct:
                            current_direct.add(url)
                        for url in new_agg:
                            current_agg.add(url)
                            
                        self.DIRECT_CONFIG_SOURCES = list(current_direct)
                        self.AGGREGATOR_LINKS = list(current_agg)
                        
                        self._save_sources()
                        print(f"Sources updated successfully. Total direct: {len(self.DIRECT_CONFIG_SOURCES)}")
        except Exception as e:
            print(f"Warning: Failed to update sources from remote: {e}")

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

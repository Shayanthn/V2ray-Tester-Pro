"""
Real-time Config Saver - Saves configs immediately as they are found
This module implements a producer pattern for the modular architecture
"""
import json
import os
import hashlib
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional
import logging


class RealtimeConfigSaver:
    """
    Saves working configs immediately to a shared JSON file.
    Uses file locking to prevent race conditions.
    
    This is the PRODUCER in the producer-consumer pattern.
    The TelegramPublisher is the CONSUMER.
    """
    
    def __init__(self, output_file: str = "working_configs.json", logger: logging.Logger = None):
        self.output_file = output_file
        self.logger = logger or logging.getLogger(__name__)
        self._lock = Lock()
        self._seen_hashes = set()
        
        # Load existing hashes to avoid duplicates
        self._load_existing_hashes()
    
    def _load_existing_hashes(self):
        """Load hashes of existing configs to avoid duplicates."""
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    configs = data.get('configs', [])
                    for cfg in configs:
                        uri = cfg.get('uri', '')
                        if uri:
                            self._seen_hashes.add(self._hash_uri(uri))
                self.logger.info(f"Loaded {len(self._seen_hashes)} existing config hashes")
            except Exception as e:
                self.logger.warning(f"Failed to load existing configs: {e}")
    
    def _hash_uri(self, uri: str) -> str:
        """Generate MD5 hash of a config URI."""
        return hashlib.md5(uri.encode()).hexdigest()
    
    def save_config(self, config: Dict) -> bool:
        """
        Save a single working config immediately.
        Returns True if saved (new config), False if duplicate.
        """
        uri = config.get('uri', '')
        if not uri:
            return False
        
        config_hash = self._hash_uri(uri)
        
        # Check for duplicate
        if config_hash in self._seen_hashes:
            return False
        
        with self._lock:
            # Double-check after acquiring lock
            if config_hash in self._seen_hashes:
                return False
            
            # Add to seen
            self._seen_hashes.add(config_hash)
            
            # Load current file
            data = self._load_data()
            
            # Add new config with timestamp
            config_entry = {
                **config,
                'found_at': datetime.now().isoformat(),
                'hash': config_hash,
                'sent_to_telegram': False
            }
            data['configs'].append(config_entry)
            data['last_updated'] = datetime.now().isoformat()
            data['total_configs'] = len(data['configs'])
            
            # Save immediately
            self._save_data(data)
            
            self.logger.info(f"💾 Saved new config: {config.get('protocol', 'unknown')} - {config.get('ping', 0)}ms")
            return True
    
    def save_configs_batch(self, configs: List[Dict]) -> int:
        """Save multiple configs. Returns count of new configs saved."""
        saved = 0
        for config in configs:
            if self.save_config(config):
                saved += 1
        return saved
    
    def _load_data(self) -> Dict:
        """Load current data from file."""
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            'configs': [],
            'last_updated': None,
            'total_configs': 0,
            'created_at': datetime.now().isoformat()
        }
    
    def _save_data(self, data: Dict):
        """Save data to file."""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_unsent_configs(self, limit: int = 10) -> List[Dict]:
        """Get configs that haven't been sent to Telegram yet."""
        data = self._load_data()
        unsent = [c for c in data['configs'] if not c.get('sent_to_telegram', False)]
        
        # Sort by download speed (best first)
        unsent.sort(key=lambda x: x.get('download_speed', 0), reverse=True)
        
        return unsent[:limit]
    
    def mark_as_sent(self, config_hashes: List[str]):
        """Mark configs as sent to Telegram."""
        with self._lock:
            data = self._load_data()
            
            for config in data['configs']:
                if config.get('hash') in config_hashes:
                    config['sent_to_telegram'] = True
                    config['sent_at'] = datetime.now().isoformat()
            
            self._save_data(data)
    
    def cleanup_old_configs(self, max_age_hours: int = 24):
        """Remove configs older than max_age_hours."""
        with self._lock:
            data = self._load_data()
            cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
            
            original_count = len(data['configs'])
            data['configs'] = [
                c for c in data['configs']
                if datetime.fromisoformat(c.get('found_at', datetime.now().isoformat())).timestamp() > cutoff
            ]
            
            removed = original_count - len(data['configs'])
            if removed > 0:
                data['total_configs'] = len(data['configs'])
                self._save_data(data)
                self.logger.info(f"🧹 Cleaned up {removed} old configs")
            
            return removed
    
    def get_stats(self) -> Dict:
        """Get statistics about saved configs."""
        data = self._load_data()
        configs = data.get('configs', [])
        
        sent_count = len([c for c in configs if c.get('sent_to_telegram', False)])
        unsent_count = len(configs) - sent_count
        
        protocols = {}
        for c in configs:
            proto = c.get('protocol', 'unknown')
            protocols[proto] = protocols.get(proto, 0) + 1
        
        return {
            'total': len(configs),
            'sent': sent_count,
            'unsent': unsent_count,
            'protocols': protocols,
            'last_updated': data.get('last_updated')
        }

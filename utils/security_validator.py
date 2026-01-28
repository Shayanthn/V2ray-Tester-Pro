import re
import json
import logging
import unicodedata
from typing import Set, Dict, Any

class SecurityValidator:
    """Validates configurations and URIs for security compliance."""
    
    def __init__(self, 
                 max_uri_length: int, 
                 protocol_whitelist: Set[str], 
                 banned_payloads: Set[str], 
                 ip_blacklist: Set[str], 
                 domain_blacklist: Set[str],
                 logger: logging.Logger):
        self.max_uri_length = max_uri_length
        self.protocol_whitelist = protocol_whitelist
        self.banned_payloads = banned_payloads
        self.ip_blacklist = ip_blacklist
        self.domain_blacklist = domain_blacklist
        self.logger = logger

    def _normalize_unicode(self, text: str) -> str:
        """Normalize unicode to prevent bypass attacks using confusable characters."""
        # NFKC normalization converts confusable characters to their canonical form
        # e.g., ｅｖａｌ -> eval, ℯval -> eval
        return unicodedata.normalize('NFKC', text)

    def validate_uri(self, uri: str) -> bool:
        """Performs comprehensive security validation on a URI."""
        if not uri or not isinstance(uri, str):
            return False
        
        # Normalize unicode to prevent bypass attacks
        normalized_uri = self._normalize_unicode(uri)
            
        # Length check
        if len(uri) > self.max_uri_length:
            self.logger.debug(f"URI too long ({len(uri)} chars)")
            return False
            
        # Protocol check
        protocol = uri.split("://")[0].lower()
        if protocol not in self.protocol_whitelist:
            self.logger.debug(f"Protocol not allowed: {protocol}")
            return False
            
        # Blacklist checks (on normalized string)
        for banned in self.banned_payloads:
            if banned in normalized_uri.lower():
                self.logger.warning(f"Banned payload detected: {banned}")
                return False
                
        # Enhanced suspicious pattern detection (works on normalized string)
        suspicious_patterns = [
            r"eval\s*\(", r"exec\s*\(", r"fromCharCode", r"base64_decode",
            r"[\x00-\x1F\x7F]",  # Control characters (excluding extended ASCII for valid UTF-8)
            r"javascript:", r"data:", r"vbscript:",  # Dangerous URI schemes
            r"<script", r"</script", r"onerror", r"onload",  # XSS patterns
            r"\\u00", r"\\x",  # Escaped unicode/hex that might hide payloads
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, normalized_uri, re.IGNORECASE):
                self.logger.warning(f"Suspicious pattern detected in URI: {pattern}")
                return False
                
        return True
    
    def validate_config(self, config_json: dict) -> bool:
        """Validates a configuration JSON for security compliance."""
        if not config_json or not isinstance(config_json, dict):
            return False
            
        # Check for banned payloads in the entire config
        config_str = json.dumps(config_json).lower()
        for banned in self.banned_payloads:
            if banned in config_str:
                self.logger.warning(f"Banned payload in config: {banned}")
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
                if self.is_blacklisted(address):
                    self.logger.warning(f"Blacklisted server in config: {address}")
                    return False
        return True
    
    def is_blacklisted(self, address: str) -> bool:
        """Checks if an address (IP or domain) is blacklisted."""
        if not address:
            return False
            
        # Check IP blacklist
        if address in self.ip_blacklist:
            return True
            
        # Check domain blacklist (including subdomains)
        for domain in self.domain_blacklist:
            if address.endswith(domain):
                return True
                
        # Check for infrastructure domains to avoid self-testing loops
        # Note: Only block CDN/ISP infrastructure, NOT all .ir domains
        # (Valid proxy servers may have .ir TLD but be hosted abroad)
        infra_blocked = [
            "arvancloud.ir", "arvancloud.com",  # Iranian CDN
            "parsonline.com", "parsonline.ir",  # Iranian ISP
            "asiatech.ir",  # Iranian ISP
            "shatel.ir",  # Iranian ISP
            "mci.ir",  # Mobile operator
            "irancell.ir",  # Mobile operator
            "rightel.ir",  # Mobile operator
        ]
        
        for domain in infra_blocked:
            if address.endswith(domain) or address == domain.lstrip('.'):
                return True
                
        return False

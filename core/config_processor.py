import base64
import json
import binascii
import logging
import copy
from typing import Optional, Dict, Any
from urllib.parse import parse_qs, quote, unquote, urlparse
from utils.security_validator import SecurityValidator
from utils.errors import ConfigError, ProtocolError, ValidationError, log_error, ErrorCategory

class ConfigProcessor:
    """Handles parsing all supported URI schemes and generating Xray JSON configurations."""
    
    def __init__(self, security_validator: SecurityValidator, logger: logging.Logger):
        self.security_validator = security_validator
        self.logger = logger

    def build_config_from_uri(self, uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Master parser that routes URIs to protocol-specific handlers."""
        if not uri:
            return None
            
        if not self.security_validator.validate_uri(uri):
            log_error(self.logger, ValidationError(f"Invalid URI format: {uri[:30]}..."), "URI Validation Failed")
            return None
            
        try:
            protocol = uri.split("://")[0].lower()
            parser_method = getattr(self, f"_parse_{protocol}", None)
            
            if parser_method:
                config_json = parser_method(uri, port)
                if config_json:
                    if self.security_validator.validate_config(config_json):
                        return config_json
                    else:
                        log_error(self.logger, ConfigError("Generated config failed security validation"), "Config Validation Failed")
            else:
                self.logger.warning(f"Unsupported protocol: {protocol}")
                
        except (ProtocolError, ValidationError, ConfigError) as e:
            log_error(self.logger, e, f"Failed to parse URI")
        except Exception as e:
            log_error(self.logger, ConfigError(f"Unexpected error parsing URI: {e}", original_exception=e), "Unexpected Parsing Error")
        
        return None
    
    def _create_base_config(self, port: int) -> Dict[str, Any]:
        """Creates the base Xray JSON structure with an HTTP inbound for aiohttp compatibility."""
        return {
            "log": {"loglevel": "warning"},
            "inbounds": [{
                "listen": "127.0.0.1",
                "port": port,
                "protocol": "http",
                "settings": {"timeout": 0, "allowTransparent": False, "userLevel": 0},
                "tag": "http-in"
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
    
    def _build_stream_settings(self, net, security, path, host, sni, alpn=None, fingerprint=None, service_name=None, reality_pbk=None, reality_sid=None, reality_spiderx=None):
        """Helper to build streamSettings."""
        stream = {
            "network": net,
            "security": security,
        }
        
        # TLS/Reality Settings
        if security in ['tls', 'reality', 'xtls']:
            tls_settings = {
                "serverName": sni or host,
                "allowInsecure": True,
                "fingerprint": fingerprint or "chrome"
            }
            if alpn:
                tls_settings["alpn"] = alpn.split(',')
            
            if security == 'reality':
                tls_settings.update({
                    "show": False,
                    "publicKey": reality_pbk,
                    "shortId": reality_sid,
                    "spiderX": reality_spiderx
                })
                stream['realitySettings'] = tls_settings
            elif security == 'xtls':
                stream['xtlsSettings'] = tls_settings
            else:
                stream['tlsSettings'] = tls_settings
        
        return stream

    def inject_fragment(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Injects Xray fragment outbound and routes traffic through it."""
        try:
            new_config = copy.deepcopy(config)
            
            # Find the first outbound (usually the proxy)
            # We look for common proxy protocols
            proxy_outbound = next((o for o in new_config.get('outbounds', []) 
                                  if o.get('protocol') in ['vless', 'vmess', 'trojan', 'shadowsocks']), None)
            
            if not proxy_outbound:
                return config # Cannot inject if no proxy outbound found

            # Check if it has streamSettings
            if 'streamSettings' not in proxy_outbound:
                # If it doesn't have streamSettings (e.g. standard Shadowsocks), we might create it
                # But typically only TCP/WS/GRPC/QUIC configs have it. 
                # For safety, we only inject if streamSettings exists or protocol is vless/vmess
                if proxy_outbound['protocol'] in ['shadowsocks']:
                     proxy_outbound['streamSettings'] = {"network": "tcp"} # Default
                else:
                     return config 
            
            # Add dialerProxy to sockopt
            if 'sockopt' not in proxy_outbound['streamSettings']:
                proxy_outbound['streamSettings']['sockopt'] = {}
            
            proxy_outbound['streamSettings']['sockopt']['dialerProxy'] = "fragment"
            proxy_outbound['streamSettings']['sockopt']['tcpKeepAliveIdle'] = 100
            
            # Add the fragment outbound
            fragment_outbound = {
                "tag": "fragment",
                "protocol": "freedom",
                "settings": {
                    "fragment": {
                        "packets": "tlshello",
                        "length": "100-200",
                        "interval": "10-20"
                    }
                },
                "streamSettings": {
                    "sockopt": {
                        "tcpKeepAliveIdle": 100
                    }
                }
            }
            
            # Ensure outbounds exists (it should)
            if 'outbounds' not in new_config:
                new_config['outbounds'] = []
                
            new_config['outbounds'].append(fragment_outbound)
            return new_config
            
        except Exception as e:
            self.logger.warning(f"Failed to inject fragment: {e}")
            return config

        # Transport Settings
        if net == 'ws':
            stream['wsSettings'] = {
                "path": path,
                "headers": {"Host": host} if host else {}
            }
        elif net == 'grpc':
            stream['grpcSettings'] = {
                "serviceName": service_name,
                "multiMode": True
            }
        elif net == 'http':
            stream['httpSettings'] = {
                "path": path,
                "host": [host] if host else []
            }
        elif net == 'quic':
            stream['quicSettings'] = {
                "security": host, # QUIC security type is often passed in host/header
                "key": path,
                "header": {"type": "none"}
            }
        
        return stream

    def _parse_vmess(self, uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Comprehensive VMess URI parser."""
        try:
            # Extract base64 part
            base64_part = uri.split('://')[1].split('?')[0].split('#')[0]
            # Add padding if necessary (more robustly)
            padding = '=' * (-len(base64_part) % 4)
            decoded_bytes = base64.b64decode(base64_part + padding)
            vmess_params = json.loads(decoded_bytes.decode('utf-8'))

            if not all(k in vmess_params for k in ['add', 'port', 'id']):
                raise ProtocolError("VMess JSON missing required keys (add, port, id)")

            config_json = self._create_base_config(port)
            stream_settings = self._build_stream_settings(
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
            raise ProtocolError(f"Could not decode/parse VMess URI body: {e}", original_exception=e)
        except Exception as e:
            if isinstance(e, (ProtocolError, ValidationError, ConfigError)):
                raise e
            raise ProtocolError(f"Unexpected error parsing VMess URI: {e}", original_exception=e)

    def _parse_vless(self, uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Comprehensive VLESS, REALITY, XTLS URI parser."""
        try:
            parsed_uri = urlparse(uri)
            params = parse_qs(parsed_uri.query)

            address = parsed_uri.hostname
            uuid_val = parsed_uri.username

            if not all([address, uuid_val]):
                raise ProtocolError("VLESS URI missing address or UUID")

            config_json = self._create_base_config(port)
            security = params.get('security', ['none'])[0]
            network = params.get('type', ['tcp'])[0]

            stream_settings = self._build_stream_settings(
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
            if isinstance(e, (ProtocolError, ValidationError, ConfigError)):
                raise e
            raise ProtocolError(f"Could not parse VLESS/Reality URI: {e}", original_exception=e)

    def _parse_trojan(self, uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Comprehensive Trojan URI parser."""
        try:
            parsed_uri = urlparse(uri)
            params = parse_qs(parsed_uri.query)

            address = parsed_uri.hostname
            password = parsed_uri.username

            if not all([address, password]):
                raise ProtocolError("Trojan URI missing address or password")

            config_json = self._create_base_config(port)
            stream_settings = self._build_stream_settings(
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
            if isinstance(e, (ProtocolError, ValidationError, ConfigError)):
                raise e
            raise ProtocolError(f"Could not parse Trojan URI: {e}", original_exception=e)

    def _parse_shadowsocks(self, uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Robust Shadowsocks (SS) URI parser for standard and base64 formats."""
        try:
            main_part = uri.split('://', 1)[1]
            remark = unquote(main_part.split('#', 1)[1]) if '#' in main_part else None
            main_part = main_part.split('#', 1)[0]
            
            address, server_port, method, password = None, None, None, None

            # Standard format: ss://method:pass@host:port
            if '@' in main_part:
                user_info, host_info = main_part.rsplit('@', 1)
                
                # Attempt to decode user_info (SIP002: user_info is base64(method:password))
                try:
                    # First, try treating it as plain text
                    user_info_decoded = unquote(user_info)
                    if ':' in user_info_decoded:
                        method, password = user_info_decoded.split(':', 1)
                    else:
                        # If no colon, it might be base64 encoded
                        padding = '=' * (-len(user_info) % 4)
                        user_info_decoded = base64.b64decode(user_info + padding).decode('utf-8')
                        method, password = user_info_decoded.split(':', 1)
                except Exception:
                    # If decoding fails, assume it's malformed or try raw split
                    if ':' in user_info:
                        method, password = user_info.split(':', 1)
                    else:
                        raise ValueError("Invalid user info format in Shadowsocks URI")

                # Handle IPv6 address in host
                if host_info.startswith('[') and ']' in host_info:
                    end_bracket_index = host_info.rfind(']')
                    address = host_info[1:end_bracket_index]
                    server_port_str = host_info[end_bracket_index+2:]
                else:
                    address, server_port_str = host_info.rsplit(':', 1)
                server_port = int(server_port_str)
            else:
                # Legacy format: ss://base64(method:password@host:port)
                padding = '=' * (-len(main_part) % 4)
                decoded_str = base64.b64decode(main_part + padding).decode('utf-8')
                
                user_info, host_info = decoded_str.rsplit('@', 1)
                method, password = user_info.split(':', 1)
                address, server_port_str = host_info.rsplit(':', 1)
                server_port = int(server_port_str)
            
            if not all([address, server_port, method, password]):
                raise ProtocolError("Parsed Shadowsocks URI is incomplete")
            
            config_json = self._create_base_config(port)
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
            if isinstance(e, (ProtocolError, ValidationError, ConfigError)):
                raise e
            # Log the error but don't crash the whole batch
            # raise ProtocolError(f"Could not parse Shadowsocks URI: {e}", original_exception=e)
            return None
    
    # Alias for 'ss' protocol
    def _parse_ss(self, uri: str, port: int) -> Optional[Dict[str, Any]]:
        return self._parse_shadowsocks(uri, port)

    def _parse_ssr(self, uri: str, port: int) -> Optional[Dict[str, Any]]:
        """
        ShadowsocksR (SSR) parser.
        Note: Xray Core does not natively support SSR. This method is a placeholder
        to prevent 'Unsupported protocol' warnings and gracefully skip SSR configs.
        """
        # logger.debug("SSR protocol is not supported by Xray Core. Skipping.")
        return None
    
    def _parse_tuic(self, uri: str, port: int) -> Optional[Dict[str, Any]]:
        """Comprehensive TUIC URI parser."""
        try:
            parsed = urlparse(uri)
            params = parse_qs(parsed.query)

            config_json = self._create_base_config(port)
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
                    "zero_rtt_handshake": params.get("zero_rtt_handshake", ["false"])[0] == "true",
                    "heartbeat": params.get("heartbeat", ["10s"])[0]
                }
            }
            
            # TUIC usually uses VLESS as the protocol wrapper in Xray config structure
            # But for sing-box or specific Xray forks, it might differ.
            # Assuming standard Xray with TUIC support via external module or native if available.
            # Note: Standard Xray might not support TUIC natively without a plugin.
            # This implementation assumes the user has a compatible core.
            
            outbound = {
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": parsed.hostname,
                        "port": parsed.port,
                        "users": [{"id": parsed.username}]
                    }]
                },
                "streamSettings": stream_settings,
                "tag": "proxy"
            }
            config_json["outbounds"].insert(0, outbound)
            return config_json
        except Exception as e:
            if isinstance(e, (ProtocolError, ValidationError, ConfigError)):
                raise e
            raise ProtocolError(f"Could not parse TUIC URI: {e}", original_exception=e)

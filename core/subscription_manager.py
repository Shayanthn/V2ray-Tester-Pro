# -----------------------------------------------------------------------------
# Subscription Manager - Generate subscription links for tested configs
# Developed for V2Ray Tester Pro v6.0
# -----------------------------------------------------------------------------
import base64
import json
import yaml
from typing import List, Dict
from datetime import datetime
import os


class SubscriptionManager:
    """Manages creation and export of subscription files in multiple formats."""
    
    def __init__(self, output_dir: str = "./subscriptions"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_all_formats(self, results: List[Dict], max_nodes: int = 200):
        """Generates subscription files in all supported formats."""
        # Sort by download speed
        sorted_results = sorted(
            results, 
            key=lambda x: x.get('download_speed', 0), 
            reverse=True
        )[:max_nodes]
        
        outputs = {
            'base64': self._generate_base64(sorted_results),
            'clash': self._generate_clash(sorted_results),
            'v2ray_json': self._generate_v2ray_json(sorted_results),
            'singbox': self._generate_singbox(sorted_results),
            'hiddify': self._generate_hiddify(sorted_results),
            'nekobox': self._generate_nekobox(sorted_results)
        }
        
        # Save to files
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        with open(os.path.join(self.output_dir, "subscription.txt"), "w", encoding="utf-8") as f:
            f.write(outputs['base64'])
        
        with open(os.path.join(self.output_dir, "clash.yaml"), "w", encoding="utf-8") as f:
            yaml.dump(outputs['clash'], f, allow_unicode=True, sort_keys=False)
        
        with open(os.path.join(self.output_dir, "configs.json"), "w", encoding="utf-8") as f:
            json.dump(outputs['v2ray_json'], f, indent=2, ensure_ascii=False)
        
        with open(os.path.join(self.output_dir, "singbox.json"), "w", encoding="utf-8") as f:
            json.dump(outputs['singbox'], f, indent=2, ensure_ascii=False)

        with open(os.path.join(self.output_dir, "hiddify.json"), "w", encoding="utf-8") as f:
            json.dump(outputs['hiddify'], f, indent=2, ensure_ascii=False)

        with open(os.path.join(self.output_dir, "nekobox.json"), "w", encoding="utf-8") as f:
            json.dump(outputs['nekobox'], f, indent=2, ensure_ascii=False)
        
        # Generate README
        self._generate_readme(len(sorted_results), timestamp)
        
        return outputs
    
    def _generate_base64(self, results: List[Dict]) -> str:
        """Generates Base64-encoded subscription (v2rayN/v2rayNG format)."""
        uri_list = []
        
        for result in results:
            uri = self._config_to_uri(result)
            if uri:
                uri_list.append(uri)
        
        # Join with newlines and encode to base64
        combined = '\n'.join(uri_list)
        encoded = base64.b64encode(combined.encode('utf-8')).decode('utf-8')
        return encoded
    
    def _config_to_uri(self, result: Dict) -> str:
        """Converts a config result back to URI format."""
        config_json = result.get('config_json', {})
        outbound = config_json.get('outbounds', [{}])[0]
        protocol = result.get('protocol', 'unknown')
        
        if protocol == 'vmess':
            return self._vmess_to_uri(outbound, result)
        elif protocol == 'vless':
            return self._vless_to_uri(outbound, result)
        elif protocol == 'trojan':
            return self._trojan_to_uri(outbound, result)
        elif protocol == 'shadowsocks':
            return self._ss_to_uri(outbound, result)
        
        return ""
    
    def _vmess_to_uri(self, outbound: Dict, result: Dict) -> str:
        """Generates VMess URI."""
        vnext = outbound.get('settings', {}).get('vnext', [{}])[0]
        user = vnext.get('users', [{}])[0]
        stream = outbound.get('streamSettings', {})
        
        vmess_obj = {
            "v": "2",
            "ps": f"🚀 {result['address']} | {result['ping']}ms | {result['download_speed']}Mbps",
            "add": vnext.get('address'),
            "port": vnext.get('port'),
            "id": user.get('id'),
            "aid": user.get('alterId', 0),
            "net": stream.get('network', 'tcp'),
            "type": "none",
            "host": "",
            "path": "",
            "tls": stream.get('security', 'none')
        }
        
        if stream.get('network') == 'ws':
            ws_settings = stream.get('wsSettings', {})
            vmess_obj['path'] = ws_settings.get('path', '/')
            vmess_obj['host'] = ws_settings.get('headers', {}).get('Host', '')
        
        json_str = json.dumps(vmess_obj, ensure_ascii=False)
        encoded = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        return f"vmess://{encoded}"
    
    def _vless_to_uri(self, outbound: Dict, result: Dict) -> str:
        """Generates VLESS URI."""
        vnext = outbound.get('settings', {}).get('vnext', [{}])[0]
        user = vnext.get('users', [{}])[0]
        stream = outbound.get('streamSettings', {})
        
        address = vnext.get('address')
        port = vnext.get('port')
        uuid = user.get('id')
        
        params = []
        params.append(f"type={stream.get('network', 'tcp')}")
        params.append(f"security={stream.get('security', 'none')}")
        
        if stream.get('security') == 'tls':
            tls = stream.get('tlsSettings', {})
            params.append(f"sni={tls.get('serverName', '')}")
            params.append(f"fp={tls.get('fingerprint', 'chrome')}")
        
        remark = f"🚀 {result['address']} | {result['ping']}ms | {result['download_speed']}Mbps"
        query_string = '&'.join(params)
        
        return f"vless://{uuid}@{address}:{port}?{query_string}#{remark}"
    
    def _trojan_to_uri(self, outbound: Dict, result: Dict) -> str:
        """Generates Trojan URI."""
        server = outbound.get('settings', {}).get('servers', [{}])[0]
        stream = outbound.get('streamSettings', {})
        
        password = server.get('password')
        address = server.get('address')
        port = server.get('port')
        
        params = []
        params.append(f"type={stream.get('network', 'tcp')}")
        params.append(f"security={stream.get('security', 'tls')}")
        
        if stream.get('security') == 'tls':
            tls = stream.get('tlsSettings', {})
            params.append(f"sni={tls.get('serverName', '')}")
        
        remark = f"🚀 {result['address']} | {result['ping']}ms | {result['download_speed']}Mbps"
        query_string = '&'.join(params)
        
        return f"trojan://{password}@{address}:{port}?{query_string}#{remark}"
    
    def _ss_to_uri(self, outbound: Dict, result: Dict) -> str:
        """Generates Shadowsocks URI."""
        server = outbound.get('settings', {}).get('servers', [{}])[0]
        
        method = server.get('method')
        password = server.get('password')
        address = server.get('address')
        port = server.get('port')
        
        user_info = f"{method}:{password}"
        encoded = base64.b64encode(user_info.encode('utf-8')).decode('utf-8')
        
        remark = f"🚀 {result['address']} | {result['ping']}ms | {result['download_speed']}Mbps"
        
        return f"ss://{encoded}@{address}:{port}#{remark}"
    
    def _generate_clash(self, results: List[Dict]) -> Dict:
        """Generates Clash-compatible YAML configuration."""
        proxies = []
        proxy_names = []
        
        for idx, result in enumerate(results):
            config_json = result.get('config_json', {})
            outbound = config_json.get('outbounds', [{}])[0]
            protocol = result.get('protocol', 'unknown')
            
            name = f"{protocol.upper()}-{idx+1} | {result['ping']}ms"
            proxy_names.append(name)
            
            if protocol == 'vmess':
                proxy = self._vmess_to_clash(outbound, name)
            elif protocol == 'vless':
                proxy = self._vless_to_clash(outbound, name)
            elif protocol == 'trojan':
                proxy = self._trojan_to_clash(outbound, name)
            elif protocol == 'shadowsocks':
                proxy = self._ss_to_clash(outbound, name)
            else:
                continue
            
            if proxy:
                proxies.append(proxy)
        
        clash_config = {
            'port': 7890,
            'socks-port': 7891,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'info',
            'external-controller': '127.0.0.1:9090',
            'proxies': proxies,
            'proxy-groups': [
                {
                    'name': 'PROXY',
                    'type': 'select',
                    'proxies': ['Auto-Select'] + proxy_names
                },
                {
                    'name': 'Auto-Select',
                    'type': 'url-test',
                    'proxies': proxy_names,
                    'url': 'https://www.google.com/generate_204',
                    'interval': 300
                }
            ],
            'rules': [
                'DOMAIN-SUFFIX,google.com,PROXY',
                'DOMAIN-SUFFIX,youtube.com,PROXY',
                'GEOIP,IR,DIRECT',
                'MATCH,PROXY'
            ]
        }
        
        return clash_config
    
    def _vmess_to_clash(self, outbound: Dict, name: str) -> Dict:
        """Converts VMess config to Clash format."""
        vnext = outbound.get('settings', {}).get('vnext', [{}])[0]
        user = vnext.get('users', [{}])[0]
        stream = outbound.get('streamSettings', {})
        
        proxy = {
            'name': name,
            'type': 'vmess',
            'server': vnext.get('address'),
            'port': vnext.get('port'),
            'uuid': user.get('id'),
            'alterId': user.get('alterId', 0),
            'cipher': user.get('security', 'auto'),
            'network': stream.get('network', 'tcp')
        }
        
        if stream.get('security') == 'tls':
            proxy['tls'] = True
            tls = stream.get('tlsSettings', {})
            proxy['servername'] = tls.get('serverName', '')
        
        if stream.get('network') == 'ws':
            ws = stream.get('wsSettings', {})
            proxy['ws-opts'] = {
                'path': ws.get('path', '/'),
                'headers': ws.get('headers', {})
            }
        
        return proxy
    
    def _vless_to_clash(self, outbound: Dict, name: str) -> Dict:
        """Converts VLESS config to Clash format."""
        vnext = outbound.get('settings', {}).get('vnext', [{}])[0]
        user = vnext.get('users', [{}])[0]
        stream = outbound.get('streamSettings', {})
        
        proxy = {
            'name': name,
            'type': 'vless',
            'server': vnext.get('address'),
            'port': vnext.get('port'),
            'uuid': user.get('id'),
            'network': stream.get('network', 'tcp')
        }
        
        if stream.get('security') == 'tls':
            proxy['tls'] = True
            tls = stream.get('tlsSettings', {})
            proxy['servername'] = tls.get('serverName', '')
        
        return proxy
    
    def _trojan_to_clash(self, outbound: Dict, name: str) -> Dict:
        """Converts Trojan config to Clash format."""
        server = outbound.get('settings', {}).get('servers', [{}])[0]
        stream = outbound.get('streamSettings', {})
        
        proxy = {
            'name': name,
            'type': 'trojan',
            'server': server.get('address'),
            'port': server.get('port'),
            'password': server.get('password')
        }
        
        if stream.get('security') == 'tls':
            tls = stream.get('tlsSettings', {})
            proxy['sni'] = tls.get('serverName', '')
        
        return proxy
    
    def _ss_to_clash(self, outbound: Dict, name: str) -> Dict:
        """Converts Shadowsocks config to Clash format."""
        server = outbound.get('settings', {}).get('servers', [{}])[0]
        
        return {
            'name': name,
            'type': 'ss',
            'server': server.get('address'),
            'port': server.get('port'),
            'cipher': server.get('method'),
            'password': server.get('password')
        }
    
    def _generate_v2ray_json(self, results: List[Dict]) -> List[Dict]:
        """Generates V2Ray JSON format."""
        return [result.get('config_json', {}) for result in results if result.get('config_json')]
    
    def _generate_singbox(self, results: List[Dict]) -> Dict:
        """Generates SingBox-compatible configuration."""
        outbounds = []
        
        for result in results:
            # SingBox format conversion (simplified)
            # You can expand this based on SingBox's actual schema
            outbounds.append({
                'type': result.get('protocol'),
                'tag': f"{result['protocol']}-{result['address']}",
                'server': result['address']
            })
        
        return {
            'outbounds': outbounds
        }

    def _generate_hiddify(self, results: List[Dict]) -> Dict:
        """Generates Hiddify-compatible configuration (SingBox variant)."""
        # Hiddify supports SingBox format natively.
        # We can reuse the SingBox generator or customize it if needed.
        return self._generate_singbox(results)

    def _generate_nekobox(self, results: List[Dict]) -> Dict:
        """Generates NekoBox-compatible configuration (SingBox variant)."""
        # NekoBox supports SingBox format natively.
        return self._generate_singbox(results)
    
    def _generate_readme(self, node_count: int, timestamp: str):
        """Generates README file with usage instructions."""
        readme_content = f"""# V2Ray Tester Pro - Subscription Files

**Last Updated:** {timestamp}
**Total Nodes:** {node_count}

## 📥 Quick Import

### For v2rayN / v2rayNG / Matsuri
```
https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/subscriptions/subscription.txt
```

### For Clash / ClashX / Clash for Android
```
https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/subscriptions/clash.yaml
```

## 📊 Files Description

- `subscription.txt` - Base64 encoded subscription (v2rayN/NG compatible)
- `clash.yaml` - Clash configuration with auto-select
- `configs.json` - Raw V2Ray/Xray JSON configs
- `singbox.json` - SingBox compatible configuration
- `hiddify.json` - Hiddify compatible configuration
- `nekobox.json` - NekoBox compatible configuration

## 🔄 Auto-Update

These files are automatically updated every 2 hours by GitHub Actions.

## ⚠️ Disclaimer

These configurations are collected from public sources and tested automatically.
Use at your own risk. No guarantees for availability or performance.

## 📈 Statistics

All nodes are tested for:
- ✅ Ping latency
- ✅ Download speed
- ✅ Upload speed
- ✅ Bypass capability

---
Generated by [V2Ray Tester Pro](https://github.com/YOUR_USERNAME/V2ray-Tester-Pro)
"""
        
        with open(os.path.join(self.output_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme_content)

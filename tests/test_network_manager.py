import json
import logging
import unittest
from unittest.mock import AsyncMock

from core.app_state import AppState
from core.network_manager import NetworkManager

# Saved answer of GET https://api.internetdata.io/8.8.8.8 (no key), 2026-11-27.
INTERNETDATA_8_8_8_8 = json.loads("""
{
  "ip": "8.8.8.8",
  "is_bogon": false,
  "is_tor": false,
  "is_relay": false,
  "is_anycast": true,
  "location": {
    "continent": "NA",
    "continent_name": "North America",
    "country": "US",
    "country_name": "United States",
    "timezone": "America/Los_Angeles",
    "currency_code": "USD",
    "currency_name": "Dollar",
    "currency_symbol": "$",
    "flag_emoji": "🇺🇸",
    "flag_unicode": "U+1F1FA U+1F1F8"
  },
  "tor": {},
  "relay": {},
  "asn": {
    "asn": 15169,
    "name": "Google LLC",
    "domain": "google.com",
    "type": "hosting",
    "prefix": "8.8.8.0/24",
    "country": "US",
    "rpki_status": "valid"
  },
  "company": {
    "name": "Google LLC",
    "domain": "google.com"
  },
  "hostname": "dns.google",
  "abuse": {
    "email": "network-abuse@google.com"
  }
}
""")


class GeoIPFallbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.manager = NetworkManager(
            app_state=AppState(adaptive_batch_min=1, adaptive_sleep_max=1.0),
            doh_resolver_url="https://example.invalid/dns-query",
            network_retry_count=1,
            app_version="test",
            logger=logging.getLogger("test"),
        )

    async def test_internetdata_answers_after_the_first_two_fail(self):
        self.manager.safe_get = AsyncMock(
            side_effect=[None, None, json.dumps(INTERNETDATA_8_8_8_8)]
        )

        info = await self.manager.fetch_geoip_online("8.8.8.8")

        self.assertEqual(
            info,
            {
                "country": "United States",
                "country_code": "US",
                "city": "Unknown",
                "isp": "Google LLC",
            },
        )
        urls = [call.args[0] for call in self.manager.safe_get.call_args_list]
        self.assertEqual(
            urls,
            [
                "https://ipwho.is/8.8.8.8",
                "http://ip-api.com/json/8.8.8.8",
                "https://api.internetdata.io/8.8.8.8",
            ],
        )

    async def test_internetdata_is_not_asked_when_ipwho_answers(self):
        ipwho = {"country": "United States", "country_code": "US", "city": "Mountain View",
                 "connection": {"isp": "Google LLC"}}
        self.manager.safe_get = AsyncMock(return_value=json.dumps(ipwho))

        info = await self.manager.fetch_geoip_online("8.8.8.8")

        self.assertEqual(info["city"], "Mountain View")
        self.manager.safe_get.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()

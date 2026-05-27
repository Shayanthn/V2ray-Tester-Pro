import tempfile
import unittest
from pathlib import Path

from core.proxy_collector import ProxyCollector
from core.telegram_proxy_publisher import TelegramProxyPublisher


class DummyNotifier:
    is_enabled = True


class ProxyPipelineTests(unittest.TestCase):
    def test_collect_mtproto_and_socks5_formats(self):
        collector = ProxyCollector(sources_file="does-not-matter.json")

        mtproto_text = """
        tg://proxy?server=1.2.3.4&port=443&secret=abcdef
        https://t.me/proxy?server=2.2.2.2&port=8443&secret=123456
        9.9.9.9:443:eeeeee
        """
        socks_text = """
        3.3.3.3:1080
        4.4.4.4:1081
        5.5.5.5:1082:usr:pwd
        """

        mtproxies = collector._parse_mtproto_content(mtproto_text, "source-m")
        sproxies = collector._parse_socks5_content(socks_text, "source-s", allow_json=False)

        self.assertGreaterEqual(len(mtproxies), 3)
        self.assertGreaterEqual(len(sproxies), 3)
        self.assertEqual(mtproxies[0]["type"], "mtproto")
        self.assertEqual(sproxies[0]["type"], "socks5")

    def test_mtproto_message_contains_both_links(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            working = str(Path(temp_dir) / "working.json")
            state = str(Path(temp_dir) / "state.json")
            publisher = TelegramProxyPublisher(DummyNotifier(), working_file=working, state_file=state)

            proxy = {
                "type": "mtproto",
                "server": "1.2.3.4",
                "port": 443,
                "secret": "abcdef123456",
                "source": "raw",
                "latency_ms": 120,
            }
            message = publisher._build_proxy_message(proxy)

            self.assertIn("tg://proxy?server=1.2.3.4&port=443&secret=abcdef123456", message)
            self.assertIn("https://t.me/proxy?server=1.2.3.4&port=443&secret=abcdef123456", message)
            self.assertIn("اینترنت بدون فیلتر حق همه ماست", message)


if __name__ == "__main__":
    unittest.main()

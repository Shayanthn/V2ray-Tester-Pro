import asyncio
import sys

sys.path.insert(0, ".")

from core.proxy_collector import ProxyCollector
from core.proxy_tester import ProxyTester
from core.telegram_proxy_publisher import TelegramProxyPublisher
from utils.logger import setup_logger
from utils.telegram_notifier import TelegramNotifier


async def main():
    logger = setup_logger("TelegramProxyPublisher", "telegram_proxy.log")

    collector = ProxyCollector(logger=logger)
    tester = ProxyTester(logger=logger)
    notifier = TelegramNotifier(logger)
    publisher = TelegramProxyPublisher(notifier, logger)

    collected = await collector.collect_proxies()
    if collected:
        tested_working = await tester.test_proxies(collected, limit=300)
        publisher.ingest_working_proxies(tested_working)

    stats = publisher.get_stats()
    logger.info(
        f"Proxy pool stats: total={stats['total']}, unsent={stats['unsent']}, posted_today={stats['post_count_today']}"
    )

    if stats["unsent"] == 0:
        print("ℹ️ No unsent working proxies to publish")
        return

    sent = await publisher.publish_next_proxy()
    if sent:
        print("✅ Published 1 proxy to Telegram")
    else:
        print("ℹ️ Proxy publish skipped or failed")


if __name__ == "__main__":
    asyncio.run(main())

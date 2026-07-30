import httpx
import pytest

from techgrowth_api.integrations.radar_collector import DEFAULT_FEEDS, RadarCollector, RadarFeed
from techgrowth_api.integrations.radar_sources import FeedSource
from techgrowth_api.services.radar import RadarService

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>AI Engineering</title>
  <item><guid>release-1</guid><title>Agent Runtime 2.0</title>
    <link>https://example.com/release?utm_source=rss</link>
    <description>Durable agent execution.</description>
    <pubDate>Wed, 29 Jul 2026 10:00:00 GMT</pubDate>
  </item>
</channel></rss>"""


def test_feed_source_parses_canonical_candidate() -> None:
    items = FeedSource("official", "Official AI", "Agent engineering").parse(RSS)

    assert len(items) == 1
    assert items[0].source_key == "official:release-1"
    assert items[0].source_url == "https://example.com/release"
    assert items[0].published_at.tzinfo is not None


def test_radar_upsert_is_idempotent(client) -> None:
    service: RadarService = client.app.state.services.radar
    candidate = FeedSource("official", "Official AI", "Agent engineering").parse(RSS)[0]

    assert service.upsert([candidate]) == 1
    assert service.upsert([candidate]) == 0


def test_radar_upsert_persists_embedding(client) -> None:
    service: RadarService = client.app.state.services.radar
    candidate = FeedSource("embedded", "Official AI", "Agent engineering").parse(RSS)[0]

    assert service.upsert([candidate], {candidate.source_key: [0.1, 0.2]}) == 1
    item = next(item for item in service.list_items() if item.source_key == candidate.source_key)
    assert item.embedding == [0.1, 0.2]


@pytest.mark.asyncio
async def test_radar_collector_retries_primary_then_uses_fallback() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.host == "blocked.example":
            raise httpx.ConnectTimeout("blocked", request=request)
        return httpx.Response(200, text=RSS)

    feed = RadarFeed(
        source_id="resilient",
        source_name="Resilient Source",
        topic="Agent engineering",
        urls=("https://blocked.example/feed", "https://fallback.example/feed"),
        credibility=0.9,
    )
    collector = RadarCollector(
        transport=httpx.MockTransport(handler), feeds=(feed,), attempts_per_url=2
    )

    results = await collector.collect()

    assert results[0].error == ""
    assert len(results[0].candidates) == 1
    assert requested_urls == [
        "https://blocked.example/feed",
        "https://blocked.example/feed",
        "https://fallback.example/feed",
    ]


def test_radar_collector_keeps_optional_proxy_configuration() -> None:
    collector = RadarCollector(proxy_url="http://proxy.internal:8080")

    assert collector.proxy_url == "http://proxy.internal:8080"


def test_default_registry_contains_domestic_technology_sources() -> None:
    domestic = {feed.source_id for feed in DEFAULT_FEEDS if feed.region == "domestic"}

    assert {
        "oschina-news",
        "infoq-cn",
        "segmentfault",
        "v2ex-tech",
        "ruanyifeng",
        "jiqizhixin",
    } <= domestic


def test_outbound_proxy_is_used_only_for_international_feeds() -> None:
    collector = RadarCollector(proxy_url="http://proxy.internal:8080")
    domestic = RadarFeed("cn", "China", "Technology", ("https://cn.example/feed",), 0.8, "domestic")
    international = RadarFeed(
        "global",
        "Global",
        "Technology",
        ("https://global.example/feed",),
        0.8,
        "international",
    )

    assert collector.proxy_for(domestic) == ""
    assert collector.proxy_for(international) == "http://proxy.internal:8080"


@pytest.mark.asyncio
async def test_radar_collector_caps_items_per_source() -> None:
    repeated = RSS.replace(
        "</channel>",
        """
        <item><guid>release-2</guid><title>Agent Runtime 2.1</title>
          <link>https://example.com/release-2</link><description>Second.</description>
        </item>
        </channel>
        """,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=repeated)

    collector = RadarCollector(
        transport=httpx.MockTransport(handler),
        feeds=(
            RadarFeed(
                "bounded",
                "Bounded Source",
                "Agent engineering",
                ("https://example.com/feed",),
                0.9,
            ),
        ),
        max_items_per_source=1,
    )

    results = await collector.collect()

    assert len(results[0].candidates) == 1

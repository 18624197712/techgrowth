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

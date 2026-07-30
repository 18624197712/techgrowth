import asyncio
from dataclasses import dataclass, replace

import httpx

from .radar_sources import FeedSource, IngestCandidate


@dataclass(frozen=True, slots=True)
class RadarFeed:
    source_id: str
    source_name: str
    topic: str
    urls: tuple[str, ...]
    credibility: float


DEFAULT_FEEDS = (
    RadarFeed(
        "openai-news",
        "OpenAI News",
        "AI platforms",
        ("https://openai.com/news/rss.xml",),
        0.95,
    ),
    RadarFeed(
        "huggingface-blog",
        "Hugging Face Blog",
        "Open source AI",
        (
            "https://huggingface.co/blog/feed.xml",
            "https://github.com/huggingface/transformers/releases.atom",
        ),
        0.9,
    ),
    RadarFeed(
        "langgraph-releases",
        "LangGraph Releases",
        "Agent engineering",
        ("https://github.com/langchain-ai/langgraph/releases.atom",),
        0.95,
    ),
    RadarFeed(
        "openai-agents-releases",
        "OpenAI Agents SDK Releases",
        "Agent engineering",
        ("https://github.com/openai/openai-agents-python/releases.atom",),
        0.95,
    ),
    RadarFeed(
        "arxiv-ai",
        "arXiv cs.AI/cs.CL",
        "AI research",
        (
            "https://export.arxiv.org/api/query?search_query=cat:cs.AI%20OR%20cat:cs.CL&sortBy=submittedDate&sortOrder=descending&max_results=20",
            "https://rss.arxiv.org/rss/cs.AI",
        ),
        0.85,
    ),
    RadarFeed(
        "hacker-news-ai",
        "Hacker News",
        "AI engineering community",
        (
            "https://hnrss.org/newest?q=AI%20agent",
            "https://news.ycombinator.com/rss",
        ),
        0.7,
    ),
    RadarFeed(
        "oschina-news",
        "OSCHINA News",
        "Chinese developer ecosystem",
        ("https://www.oschina.net/news/rss",),
        0.75,
    ),
)


@dataclass(frozen=True, slots=True)
class RadarSourceResult:
    source_id: str
    candidates: list[IngestCandidate]
    error: str = ""


def safe_source_error(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"HTTP {error.response.status_code}"
    if isinstance(error, httpx.TimeoutException):
        return "request timed out"
    return type(error).__name__


class RadarCollector:
    def __init__(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        feeds: tuple[RadarFeed, ...] = DEFAULT_FEEDS,
        proxy_url: str = "",
        attempts_per_url: int = 2,
        timeout_seconds: float = 30,
        max_items_per_source: int = 10,
    ) -> None:
        self.transport = transport
        self.feeds = feeds
        self.proxy_url = proxy_url
        self.attempts_per_url = max(1, attempts_per_url)
        self.timeout_seconds = timeout_seconds
        self.max_items_per_source = max(1, max_items_per_source)

    async def collect(self) -> list[RadarSourceResult]:
        client_options = {
            "timeout": self.timeout_seconds,
            "follow_redirects": True,
            "transport": self.transport,
        }
        if self.proxy_url:
            client_options["proxy"] = self.proxy_url
        async with httpx.AsyncClient(**client_options) as client:
            return list(
                await asyncio.gather(
                    *(self._collect_one(client, feed) for feed in self.feeds)
                )
            )

    async def _collect_one(
        self, client: httpx.AsyncClient, feed: RadarFeed
    ) -> RadarSourceResult:
        last_error: Exception | None = None
        for url in feed.urls:
            for _ in range(self.attempts_per_url):
                try:
                    candidates = await self._fetch(client, feed, url)
                    return RadarSourceResult(feed.source_id, candidates)
                except Exception as exc:
                    last_error = exc
        error = safe_source_error(last_error) if last_error else "no source URL configured"
        return RadarSourceResult(feed.source_id, [], error)

    async def _fetch(
        self,
        client: httpx.AsyncClient,
        feed: RadarFeed,
        url: str,
    ) -> list[IngestCandidate]:
        response = await client.get(url, headers={"User-Agent": "TechGrowth/0.1"})
        response.raise_for_status()
        items = FeedSource(feed.source_id, feed.source_name, feed.topic).parse(response.content)
        return [
            replace(item, credibility=feed.credibility)
            for item in items[: self.max_items_per_source]
        ]

import asyncio
from dataclasses import replace

import httpx

from .radar_sources import FeedSource, IngestCandidate

DEFAULT_FEEDS = (
    (
        "openai-news",
        "OpenAI News",
        "AI platforms",
        "https://openai.com/news/rss.xml",
        0.95,
    ),
    (
        "huggingface-blog",
        "Hugging Face Blog",
        "Open source AI",
        "https://huggingface.co/blog/feed.xml",
        0.9,
    ),
    (
        "langgraph-releases",
        "LangGraph Releases",
        "Agent engineering",
        "https://github.com/langchain-ai/langgraph/releases.atom",
        0.95,
    ),
    (
        "openai-agents-releases",
        "OpenAI Agents SDK Releases",
        "Agent engineering",
        "https://github.com/openai/openai-agents-python/releases.atom",
        0.95,
    ),
    (
        "arxiv-ai",
        "arXiv cs.AI/cs.CL",
        "AI research",
        "https://export.arxiv.org/api/query?search_query=cat:cs.AI%20OR%20cat:cs.CL&sortBy=submittedDate&sortOrder=descending&max_results=20",
        0.85,
    ),
    (
        "hacker-news-ai",
        "Hacker News",
        "AI engineering community",
        "https://hnrss.org/newest?q=AI%20agent",
        0.7,
    ),
)


class RadarCollector:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    async def collect(self) -> list[IngestCandidate]:
        async with httpx.AsyncClient(
            timeout=30, follow_redirects=True, transport=self.transport
        ) as client:
            results = await asyncio.gather(
                *(self._fetch(client, *definition) for definition in DEFAULT_FEEDS),
                return_exceptions=True,
            )
        candidates: list[IngestCandidate] = []
        for result in results:
            if not isinstance(result, Exception):
                candidates.extend(result)
        return candidates

    async def _fetch(
        self,
        client: httpx.AsyncClient,
        source_id: str,
        source_name: str,
        topic: str,
        url: str,
        credibility: float,
    ) -> list[IngestCandidate]:
        response = await client.get(url, headers={"User-Agent": "TechGrowth/0.1"})
        response.raise_for_status()
        items = FeedSource(source_id, source_name, topic).parse(response.content)
        return [replace(item, credibility=credibility) for item in items]

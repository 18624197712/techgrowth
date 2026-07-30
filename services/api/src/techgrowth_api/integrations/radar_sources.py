import calendar
import io
from dataclasses import dataclass
from datetime import UTC, datetime

import feedparser

from ..domain.radar import canonical_url


@dataclass(frozen=True, slots=True)
class IngestCandidate:
    source_key: str
    title: str
    summary: str
    source_url: str
    source_name: str
    topic: str
    published_at: datetime
    credibility: float = 0.85
    relevance: float = 0.75
    relevance_reason: str = "来自已配置的可信技术来源。"


class FeedSource:
    def __init__(self, source_id: str, source_name: str, topic: str) -> None:
        self.source_id = source_id
        self.source_name = source_name
        self.topic = topic

    def parse(self, content: str | bytes) -> list[IngestCandidate]:
        raw = content.encode() if isinstance(content, str) else content
        feed = feedparser.parse(io.BytesIO(raw))
        result: list[IngestCandidate] = []
        for entry in feed.entries:
            source_identity = entry.get("id") or entry.get("guid") or entry.get("link")
            if not source_identity or not entry.get("link"):
                continue
            parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
            published_at = (
                datetime.fromtimestamp(calendar.timegm(parsed_time), UTC)
                if parsed_time
                else datetime.now(UTC)
            )
            result.append(
                IngestCandidate(
                    source_key=f"{self.source_id}:{source_identity}",
                    title=entry.get("title", "Untitled")[:300],
                    summary=entry.get("summary", "")[:5000],
                    source_url=canonical_url(entry.link),
                    source_name=self.source_name,
                    topic=self.topic,
                    published_at=published_at,
                )
            )
        return result

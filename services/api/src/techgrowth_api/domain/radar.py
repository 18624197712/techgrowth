from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


@dataclass(frozen=True, slots=True)
class RadarCandidate:
    source_id: str
    title: str
    url: str
    published_at: int


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), "")
    )


def deduplicate(items: list[RadarCandidate]) -> list[RadarCandidate]:
    selected: dict[str, RadarCandidate] = {}
    for item in items:
        key = canonical_url(item.url)
        if key not in selected or item.published_at > selected[key].published_at:
            selected[key] = item
    return list(selected.values())

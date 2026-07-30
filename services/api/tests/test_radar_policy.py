from techgrowth_api.domain.radar import RadarCandidate, canonical_url, deduplicate


def test_canonical_url_removes_tracking_and_fragment() -> None:
    value = canonical_url("https://example.com/post?utm_source=x&id=7#comments")
    assert value == "https://example.com/post?id=7"


def test_deduplicate_prefers_newer_candidate_for_same_canonical_url() -> None:
    older = RadarCandidate("a", "Old", "https://example.com/post?utm_source=x", 1)
    newer = RadarCandidate("b", "New", "https://example.com/post", 2)

    assert deduplicate([older, newer]) == [newer]

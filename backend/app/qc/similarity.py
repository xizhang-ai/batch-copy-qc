from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from rapidfuzz.fuzz import ratio


@dataclass(frozen=True, slots=True)
class SimilarityMatch:
    matched_id: str
    score: float
    section: str
    source_kind: str


def _get(value: Any, key: str, default: str = "") -> str:
    if isinstance(value, dict):
        return str(value.get(key, default))
    return str(getattr(value, key, default))


def normalize_for_similarity(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[^\w\u3400-\u9fff]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _sections(item: Any) -> dict[str, str]:
    title = normalize_for_similarity(_get(item, "title"))
    body = normalize_for_similarity(_get(item, "body"))
    return {"title": title, "opening": body[:80], "full": f"{title} {body}".strip()}


def _compare(
    item: Any, candidates: list[Any], threshold: int, source_kind: str
) -> list[SimilarityMatch]:
    item_id = _get(item, "id")
    source_sections = _sections(item)
    matches: list[SimilarityMatch] = []
    for candidate in candidates:
        candidate_id = _get(candidate, "id")
        if source_kind == "batch_item" and candidate_id == item_id:
            continue
        candidate_sections = _sections(candidate)
        scores = {
            name: ratio(source_sections[name], candidate_sections[name]) for name in source_sections
        }
        section, score = max(scores.items(), key=lambda pair: pair[1])
        if score >= threshold:
            matches.append(SimilarityMatch(candidate_id, round(score, 2), section, source_kind))
    return sorted(matches, key=lambda match: match.score, reverse=True)


def compare_items(item: Any, candidates: list[Any], threshold: int = 85) -> list[SimilarityMatch]:
    return _compare(item, candidates, threshold, "batch_item")


def compare_with_references(
    item: Any, references: list[Any], threshold: int = 85
) -> list[SimilarityMatch]:
    return _compare(item, references, threshold, "reference_example")


def later_duplicate_candidates(
    items: list[Any], threshold: int = 85
) -> dict[str, list[SimilarityMatch]]:
    result: dict[str, list[SimilarityMatch]] = {}
    for index, item in enumerate(items):
        matches = compare_items(item, items[:index], threshold)
        if matches:
            result[_get(item, "id")] = matches
    return result

from __future__ import annotations

from typing import Mapping


TRUST_SCORES: dict[str, float] = {
    "meta": 1.0,
    "counter": 1.0,
    "synergy": 0.6,
}

CONFIDENCE_LABELS: dict[str, str] = {
    "meta": "high",
    "counter": "high",
    "synergy": "low",
}

DEFAULT_COMPONENT_WEIGHTS: dict[str, float] = {
    "counter": 0.35,
    "meta": 0.35,
    "synergy": 0.10,
}


def get_trust_score(source: str) -> float:
    return TRUST_SCORES.get(source, 0.5)


def get_confidence_label(source: str) -> str:
    return CONFIDENCE_LABELS.get(source, "medium")


def get_sources_confidence() -> dict[str, str]:
    return {source: get_confidence_label(source) for source in TRUST_SCORES}


def get_composite_trust_weight(component_weights: Mapping[str, float] | None = None) -> float:
    weights = dict(component_weights or DEFAULT_COMPONENT_WEIGHTS)
    total = sum(max(value, 0.0) for value in weights.values())
    if total <= 0:
        return 1.0
    weighted = sum(max(weight, 0.0) * get_trust_score(source) for source, weight in weights.items())
    return round(weighted / total, 4)


def get_trust_tags() -> list[str]:
    return ["✔ 实证数据", "✔ 对位统计", "⚠ 推断数据（协同）"]


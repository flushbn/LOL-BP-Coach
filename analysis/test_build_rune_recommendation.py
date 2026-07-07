from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.build_recommendation import BuildRecommendationEngine
from analysis.rune_recommendation import RuneRecommendationEngine


def main():
    build_engine = BuildRecommendationEngine()
    rune_engine = RuneRecommendationEngine(build_engine.client)

    scenarios = [
        ("Malphite", "TOP", ["Yasuo", "Yone", "JarvanIV", "Zed", "Nautilus"]),
        ("Malphite", "TOP", ["Rumble", "Ahri", "Karthus", "Kaisa", "Lulu"]),
        ("LeeSin", "JUNGLE", ["Darius", "Ahri", "Jinx", "Nautilus", "Ekko"]),
    ]
    for champion, role, enemy in scenarios:
        print("=" * 80)
        print(champion, role, "vs", ", ".join(enemy))
        payload = {
            "runes": rune_engine.recommend(champion, role, enemy),
            "builds": build_engine.recommend(champion, role, enemy),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

import json
from pathlib import Path
from typing import Dict, List, Optional

from utils.champion_names import canonical_champion_key


PROJECT_ROOT = Path(__file__).resolve().parent.parent

_ROLE_ALIASES = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "MID": "MID",
    "MIDDLE": "MID",
    "ADC": "ADC",
    "BOTTOM": "ADC",
    "SUPPORT": "SUPPORT",
    "UTILITY": "SUPPORT",
}


def _role_key(role: str | None) -> str:
    return _ROLE_ALIASES.get(str(role or "").upper(), "")


class CounterAnalyzer:
    """Role-aware counter scoring with conservative sample confidence."""

    def __init__(self, data_path: Optional[Path] = None, use_v2: bool = False):
        if data_path is None:
            data_path = PROJECT_ROOT / "data" / "counter_data_v2.json" if use_v2 else self._resolve_data_path()
        if not data_path.exists():
            raise FileNotFoundError(f"Counter data not found: {data_path}")
        with open(data_path, "r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
        self._counter_by_role = self._normalize_schema(raw_data)

    @staticmethod
    def _resolve_data_path() -> Path:
        data_dir = PROJECT_ROOT / "data"
        patch_file = data_dir / "patch_version.json"
        try:
            patch = json.loads(patch_file.read_text(encoding="utf-8")).get("current_patch")
            patch_path = data_dir / str(patch) / "counter_data.json"
            if patch and patch_path.exists():
                return patch_path
        except Exception:
            pass
        return data_dir / "counter_data.json"

    @staticmethod
    def _sample_confidence(games: int) -> float:
        if games <= 0:
            return 0.35
        if games < 500:
            return 0.35 + games / 500 * 0.4
        if games < 1500:
            return 0.75
        return 1.0

    @classmethod
    def _evidence(cls, payload: object) -> dict:
        if isinstance(payload, dict):
            score = float(payload.get("counter_score", 50) or 50)
            games = int(payload.get("games", 0) or 0)
            role = _role_key(payload.get("role")) or "ALL"
        else:
            score = float(payload or 50)
            games = 0
            role = "ALL"
        return {
            "score": min(100.0, max(0.0, score)),
            "games": max(0, games),
            "confidence": cls._sample_confidence(games),
            "role": role,
        }

    def _add_pairs(self, result: dict, role: str, candidate: str, pairs: object):
        if not isinstance(pairs, dict):
            return
        candidate_key = canonical_champion_key(candidate)
        table = result.setdefault(role, {})
        for opponent, payload in pairs.items():
            evidence = self._evidence(payload)
            opponent_key = canonical_champion_key(opponent)
            bucket = table.setdefault(opponent_key, {})
            existing = bucket.get(candidate_key)
            if existing is None or (evidence["games"], evidence["confidence"]) > (existing["games"], existing["confidence"]):
                bucket[candidate_key] = evidence

    def _normalize_schema(self, data: Dict) -> Dict[str, Dict[str, Dict[str, dict]]]:
        result: Dict[str, Dict[str, Dict[str, dict]]] = {}
        role_matchups = data.get("role_matchups", {}) if isinstance(data, dict) else {}
        if isinstance(role_matchups, dict):
            for raw_role, candidates in role_matchups.items():
                role = _role_key(raw_role) or "ALL"
                for candidate, pairs in (candidates or {}).items():
                    self._add_pairs(result, role, candidate, pairs)

        champions = data.get("champions", data) if isinstance(data, dict) else {}
        if isinstance(champions, dict):
            for candidate, pairs in champions.items():
                if not isinstance(pairs, dict):
                    continue
                grouped: Dict[str, dict] = {}
                for opponent, payload in pairs.items():
                    role = _role_key(payload.get("role")) if isinstance(payload, dict) else "ALL"
                    grouped.setdefault(role or "ALL", {})[opponent] = payload
                for role, role_pairs in grouped.items():
                    self._add_pairs(result, role, candidate, role_pairs)
        return result

    def normalize_name(self, name: str) -> str:
        return canonical_champion_key(name)

    def analyze(self, enemy_picks: List[str], target_role: str | None = None) -> Dict[str, float]:
        """Return 0-100 composition counter scores for the selected role.

        A missing matchup is neutral. Unknown sample sizes retain only 35% of
        their directional signal so old cache rows cannot dominate a draft.
        """
        role = _role_key(target_role)
        tables = [self._counter_by_role.get(role, {})] if role else list(self._counter_by_role.values())
        if not role and "ALL" in self._counter_by_role:
            tables.append(self._counter_by_role["ALL"])
        tables = [table for table in tables if table]
        if not tables or not enemy_picks:
            return {}

        effects: Dict[str, float] = {}
        enemy_count = max(1, len(enemy_picks))
        for enemy in enemy_picks:
            enemy_key = self.normalize_name(enemy)
            merged: Dict[str, dict] = {}
            for table in tables:
                for candidate, evidence in table.get(enemy_key, {}).items():
                    previous = merged.get(candidate)
                    if previous is None or (evidence["games"], evidence["confidence"]) > (previous["games"], previous["confidence"]):
                        merged[candidate] = evidence
            for candidate, evidence in merged.items():
                effects[candidate] = effects.get(candidate, 0.0) + (evidence["score"] - 50.0) * evidence["confidence"]

        scores = {
            candidate: round(min(100.0, max(0.0, 50.0 + effect / enemy_count)), 1)
            for candidate, effect in effects.items()
        }
        return dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))

    def get_top_counters(self, enemy_picks: List[str], top_n: int = 10, target_role: str | None = None) -> List[tuple[str, int]]:
        result = self.analyze(enemy_picks, target_role)
        return [(champion, round(score)) for champion, score in list(result.items())[:top_n]]

    def get_counter_score(self, champion: str, enemy_picks: List[str], target_role: str | None = None) -> int:
        result = self.analyze(enemy_picks, target_role)
        return round(result.get(self.normalize_name(champion), 50))

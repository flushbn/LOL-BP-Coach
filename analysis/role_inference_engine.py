from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

ROLES = ["TOP", "JUNGLE", "MID", "ADC", "SUPPORT"]
ROLE_DATA_KEYS = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "MID": "MIDDLE",
    "ADC": "BOTTOM",
    "SUPPORT": "UTILITY",
}
META_ROLE_ALIASES = {
    "TOP": ["TOP"],
    "JUNGLE": ["JUNGLE"],
    "MID": ["MID", "MIDDLE"],
    "ADC": ["ADC", "BOTTOM"],
    "SUPPORT": ["SUPPORT", "UTILITY"],
}
ROLE_DISPLAY = {
    "TOP": "上路",
    "JUNGLE": "打野",
    "MID": "中路",
    "ADC": "射手",
    "SUPPORT": "辅助",
}
CHAMPION_DATA_ROLE_MAP = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MID": "mid",
    "ADC": "adc",
    "SUPPORT": "support",
}


def _normalize_champion(name: str) -> str:
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


class RoleInferenceEngine:
    """Infer likely enemy lane assignments during BP.

    Scores combine:
    role_frequency * 0.5 +
    meta_lane_bias * 0.2 +
    pickrate_lane_distribution * 0.2 +
    matchup_bias * 0.1
    then softmax-normalize into probabilities.
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.role_data = self._load_json(self.data_dir / "role_data.json", {})
        self.champion_data = self._load_json(ROOT / "champion_data.json", {})
        self.meta_data = self._load_json(self._resolve_meta_path(), {})
        self._canonical = self._build_canonical_index()

    def infer_roles(self, enemy_picks: list[str]) -> dict[str, dict[str, float]]:
        clean_picks = [self.normalize_champion(champion) for champion in enemy_picks if champion]
        raw_scores: dict[str, dict[str, float]] = {}
        for champion in clean_picks:
            raw_scores[champion] = {}
            matchup_bias = self._matchup_bias(champion, clean_picks)
            for role in ROLES:
                role_frequency = self._role_frequency(champion, role)
                meta_lane_bias = self._meta_lane_bias(champion, role)
                pickrate_lane_distribution = self._pickrate_lane_distribution(champion, role)
                score = (
                    role_frequency * 0.5
                    + meta_lane_bias * 0.2
                    + pickrate_lane_distribution * 0.2
                    + matchup_bias.get(role, 0.0) * 0.1
                )
                score *= self._role_viability_multiplier(champion, role)
                if score > 0:
                    raw_scores[champion][role] = round(score, 4)

        return {
            champion: self._softmax(role_scores)
            for champion, role_scores in raw_scores.items()
        }

    def infer_enemy_lane(
        self,
        enemy_picks: list[str],
        target_role: str,
        min_probability: float = 0.15,
    ) -> dict[str, Any] | None:
        role = self.normalize_role(target_role)
        if role not in ROLES:
            return None
        inference = self.infer_roles(enemy_picks)
        best_champion = ""
        best_probability = 0.0
        for champion, probabilities in inference.items():
            probability = probabilities.get(role, 0.0)
            if probability > best_probability:
                best_champion = champion
                best_probability = probability
        if not best_champion or best_probability < min_probability:
            return None
        return {
            "champion": best_champion,
            "role": role,
            "probability": round(best_probability, 4),
            "probabilities": inference.get(best_champion, {}),
            "all": inference,
        }

    def normalize_champion(self, champion: str) -> str:
        key = _normalize_champion(champion)
        return self._canonical.get(key, champion)

    @staticmethod
    def normalize_role(role: str) -> str:
        text = str(role or "").upper()
        aliases = {
            "TOP": "TOP",
            "上路": "TOP",
            "JUNGLE": "JUNGLE",
            "打野": "JUNGLE",
            "MID": "MID",
            "MIDDLE": "MID",
            "中路": "MID",
            "ADC": "ADC",
            "BOTTOM": "ADC",
            "BOT": "ADC",
            "射手": "ADC",
            "SUPPORT": "SUPPORT",
            "SUP": "SUPPORT",
            "UTILITY": "SUPPORT",
            "辅助": "SUPPORT",
        }
        return aliases.get(text, text)

    def _role_frequency(self, champion: str, role: str) -> float:
        role_key = ROLE_DATA_KEYS[role]
        return float(self.role_data.get(champion, {}).get(role_key, 0.0))

    def _meta_lane_bias(self, champion: str, role: str) -> float:
        payload = self._meta_role_payload(champion, role)
        if not payload:
            return self._role_frequency(champion, role) * 0.75
        meta_score = float(payload.get("meta_score", 0.0) or 0.0)
        games = float(payload.get("games", 0.0) or 0.0)
        sample_factor = 1.0 if games >= 5000 else 0.65 if games >= 1000 else 0.35
        return max(0.0, min(100.0, meta_score * 2.0 * sample_factor))

    def _pickrate_lane_distribution(self, champion: str, role: str) -> float:
        role_payloads = self._champion_meta_roles(champion)
        if not role_payloads:
            return self._role_data_distribution(champion, role)
        pickrates = {
            role_name: float(payload.get("pickrate", 0.0) or 0.0)
            for role_name, payload in role_payloads.items()
        }
        total = sum(max(0.0, value) for value in pickrates.values())
        if total <= 0:
            return self._role_data_distribution(champion, role)
        if pickrates.get(role, 0.0) <= 0 and self._role_frequency(champion, role) > 0:
            return self._role_data_distribution(champion, role) * 0.7
        return max(0.0, min(100.0, pickrates.get(role, 0.0) / total * 100.0))

    def _role_data_distribution(self, champion: str, role: str) -> float:
        role_values = {
            normalized_role: self._role_frequency(champion, normalized_role)
            for normalized_role in ROLES
        }
        total = sum(role_values.values())
        if total <= 0:
            return 0.0
        return role_values.get(role, 0.0) / total * 100.0

    def _matchup_bias(self, champion: str, enemy_picks: list[str]) -> dict[str, float]:
        """Draft-structure bias: if another enemy strongly owns a role, reduce that role.

        This is the V1 local approximation of matchup/lane bias. It preserves flex
        picks but avoids assigning Jayce and Yasuo both to TOP when one is clearly
        more likely to occupy that lane.
        """
        bias = {role: 50.0 for role in ROLES}
        for role in ROLES:
            other_strength = 0.0
            for other in enemy_picks:
                if other == champion:
                    continue
                other_strength = max(other_strength, self._role_frequency(other, role))
            own_strength = self._role_frequency(champion, role)
            if other_strength >= 70 and other_strength - own_strength >= 20:
                bias[role] = 15.0
            elif other_strength >= 50 and other_strength > own_strength:
                bias[role] = 30.0
            elif own_strength >= 70:
                bias[role] = 70.0
        return bias

    def _role_viability_multiplier(self, champion: str, role: str) -> float:
        roles = [
            str(item).lower()
            for item in self.champion_data.get(champion, {}).get("roles", [])
        ]
        data_role = CHAMPION_DATA_ROLE_MAP.get(role, "")
        if not roles or data_role in roles:
            return 1.0

        role_frequency = self._role_frequency(champion, role)
        meta_payload = self._meta_role_payload(champion, role)
        if role_frequency >= 10 or meta_payload:
            return 0.35
        return 0.12

    def _champion_meta_roles(self, champion: str) -> dict[str, dict]:
        if "champions" in self.meta_data:
            roles = self.meta_data.get("champions", {}).get(champion, {}).get("roles", {})
            return {self.normalize_role(role): payload for role, payload in roles.items()}

        roles: dict[str, dict] = {}
        for role, role_payload in self.meta_data.get("roles", {}).items():
            payload = role_payload.get(champion)
            if payload:
                roles[self.normalize_role(role)] = payload
        return roles

    def _meta_role_payload(self, champion: str, role: str) -> dict:
        if "roles" in self.meta_data:
            for meta_role in META_ROLE_ALIASES.get(role, [role]):
                payload = self.meta_data.get("roles", {}).get(meta_role, {}).get(champion, {})
                if payload:
                    return payload
            return {}
        if "champions" in self.meta_data:
            roles = self.meta_data.get("champions", {}).get(champion, {}).get("roles", {})
            for meta_role in META_ROLE_ALIASES.get(role, [role]):
                payload = roles.get(meta_role, {})
                if payload:
                    return payload
        return {}

    def _softmax(self, scores: dict[str, float]) -> dict[str, float]:
        if not scores:
            return {}
        filtered = {role: score for role, score in scores.items() if score > 0}
        if not filtered:
            return {}
        temperature = 16.0
        max_score = max(filtered.values())
        exp_scores = {
            role: math.exp((score - max_score) / temperature)
            for role, score in filtered.items()
        }
        total = sum(exp_scores.values())
        probabilities = {
            role: round(value / total, 4)
            for role, value in exp_scores.items()
            if value / total >= 0.01
        }
        return dict(sorted(probabilities.items(), key=lambda item: item[1], reverse=True))

    def _resolve_meta_path(self) -> Path:
        patch_file = self.data_dir / "patch_version.json"
        try:
            if patch_file.exists():
                patch = json.loads(patch_file.read_text(encoding="utf-8")).get("current_patch")
                patch_path = self.data_dir / str(patch) / "meta_data.json"
                if patch and patch_path.exists():
                    return patch_path
        except Exception:
            pass
        return self.data_dir / "meta_data.json"

    def _build_canonical_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for champion in self.role_data.keys():
            index[_normalize_champion(champion)] = champion
        try:
            champion_json = self.data_dir / "zh_CN" / "champion.json"
            if champion_json.exists():
                data = json.loads(champion_json.read_text(encoding="utf-8")).get("data", {})
                for key, info in data.items():
                    index[_normalize_champion(key)] = key
                    index[_normalize_champion(info.get("name", ""))] = key
                    index[_normalize_champion(info.get("title", ""))] = key
        except Exception:
            pass
        return index

    @staticmethod
    def _load_json(path: Path, default):
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return default


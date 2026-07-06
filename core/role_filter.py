import json
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RoleFilter:
    """Filter champion pool by role / position.

    Uses role_data.json (from Riot API match stats) as primary source,
    falls back to champion_roles.json (manual).
    """

    VALID_ROLES = {"Top", "Jungle", "Mid", "ADC", "Support"}
    POS_MAP = {
        "TOP": "Top", "JUNGLE": "Jungle", "MIDDLE": "Mid",
        "BOTTOM": "ADC", "UTILITY": "Support",
    }

    def __init__(self, data_path: Optional[Path] = None):
        if data_path is None:
            data_path = PROJECT_ROOT / "data" / "champion_roles.json"
        # Load Riot stats-based role data
        self._role_stats: Dict[str, Dict[str, int]] = {}
        stats_path = PROJECT_ROOT / "data" / "role_data.json"
        if stats_path.exists():
            with open(stats_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for champ, pos_pct in raw.items():
                entry = {}
                for riot_pos, pct in pos_pct.items():
                    mapped = self.POS_MAP.get(riot_pos)
                    if mapped and pct >= 10:
                        entry[mapped] = pct
                if entry:
                    self._role_stats[champ] = entry

        # Fallback to manual data
        if not data_path.exists():
            raise FileNotFoundError(f"Role data not found: {data_path}")
        with open(data_path, "r", encoding="utf-8") as f:
            self._role_data: Dict[str, List[str]] = json.load(f)

        self._cn_to_en: Dict[str, str] = {}
        try:
            dt_path = PROJECT_ROOT / "data" / "zh_CN" / "champion.json"
            if dt_path.exists():
                with open(dt_path, "r", encoding="utf-8") as f:
                    dt = json.load(f)
                for eng_key, info in dt.get("data", {}).items():
                    self._cn_to_en[info["name"]] = eng_key
        except Exception:
            pass

    def normalize_name(self, name: str) -> str:
        if name in self._role_data:
            return name
        if name in self._cn_to_en:
            eng = self._cn_to_en[name]
            if eng in self._role_data:
                return eng
        for key in self._role_data:
            if key.lower() == name.lower():
                return key
        return name

    def get_roles(self, champion: str) -> list:
        """Return list of roles a champion can play."""
        rd = self._role_data.get(champion, {})
        return [k for k, v in rd.items() if v >= 10]

    def get_candidates(self, role: str) -> List[str]:
        valid = [r.lower() for r in self.VALID_ROLES]
        if role.lower() not in valid:
            return []
        # Primary: role_data.json (Riot stats)
        candidates = [
            name for name, roles in self._role_stats.items()
            if role.lower() in (r.lower() for r in roles)
        ]
        # Fallback: champion_roles.json for champs not in stats
        for name, roles in self._role_data.items():
            if name not in self._role_stats:
                if any(role.lower() == r.lower() for r in roles):
                    candidates.append(name)
        return sorted(candidates)

    def get_roles(self, champion_name: str) -> List[str]:
        key = self.normalize_name(champion_name)
        if key in self._role_stats:
            return list(self._role_stats[key].keys())
        return self._role_data.get(key, [])

    def can_play(self, champion_name: str, role: str) -> bool:
        return any(role.lower() == r.lower() for r in self.get_roles(champion_name))



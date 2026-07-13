import json
from pathlib import Path
from typing import Dict, List, Optional

from utils.champion_names import canonical_champion_key


PROJECT_ROOT = Path(__file__).resolve().parent.parent

_ROLE_MAP = {
    "TOP": "Top",
    "JUNGLE": "Jungle",
    "MID": "Mid",
    "MIDDLE": "Mid",
    "ADC": "ADC",
    "BOTTOM": "ADC",
    "SUPPORT": "Support",
    "UTILITY": "Support",
}
_RIOT_ROLE_MAP = {"Top": "TOP", "Jungle": "JUNGLE", "Mid": "MIDDLE", "ADC": "BOTTOM", "Support": "UTILITY"}


class RoleFilter:
    """Use the current patch's role distribution before legacy role lists."""

    VALID_ROLES = {"Top", "Jungle", "Mid", "ADC", "Support"}

    def __init__(self, data_path: Optional[Path] = None):
        self._role_stats = self._load_patch_role_stats()
        if not self._role_stats:
            self._role_stats = self._load_legacy_role_stats()

        path = data_path or PROJECT_ROOT / "data" / "champion_roles.json"
        self._role_data: Dict[str, List[str]] = {}
        if path.exists():
            try:
                self._role_data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass

    @staticmethod
    def _patch_meta_path() -> Path:
        data_dir = PROJECT_ROOT / "data"
        try:
            patch = json.loads((data_dir / "patch_version.json").read_text(encoding="utf-8")).get("current_patch")
            path = data_dir / str(patch) / "meta_data.json"
            if patch and path.exists():
                return path
        except Exception:
            pass
        return data_dir / "meta_data.json"

    def _load_patch_role_stats(self) -> Dict[str, Dict[str, int]]:
        try:
            raw = json.loads(self._patch_meta_path().read_text(encoding="utf-8"))
            champions = raw.get("champions", {})
        except Exception:
            return {}

        result: Dict[str, Dict[str, int]] = {}
        for raw_champion, payload in champions.items():
            roles = payload.get("roles", {}) if isinstance(payload, dict) else {}
            weighted = []
            for raw_role, entry in roles.items():
                display_role = _ROLE_MAP.get(str(raw_role).upper())
                if display_role and isinstance(entry, dict):
                    weighted.append((display_role, max(0, int(entry.get("games", 0) or 0))))
            total_games = sum(games for _, games in weighted)
            if total_games <= 0:
                continue
            champion = canonical_champion_key(raw_champion)
            result[champion] = {
                role: round(games / total_games * 100)
                for role, games in weighted
                if games > 0
            }
        return result

    def _load_legacy_role_stats(self) -> Dict[str, Dict[str, int]]:
        path = PROJECT_ROOT / "data" / "role_data.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        result: Dict[str, Dict[str, int]] = {}
        for champion, positions in raw.items():
            entry = {}
            for riot_role, percentage in positions.items():
                role = _ROLE_MAP.get(str(riot_role).upper())
                if role and float(percentage or 0) >= 10:
                    entry[role] = int(percentage)
            if entry:
                result[canonical_champion_key(champion)] = entry
        return result

    def normalize_name(self, name: str) -> str:
        key = canonical_champion_key(name)
        if key in self._role_stats or key in self._role_data:
            return key
        lowered = key.lower()
        for champion in set(self._role_stats) | set(self._role_data):
            if champion.lower() == lowered:
                return champion
        return key

    def get_role_percent(self, champion_name: str, role: str) -> int:
        key = self.normalize_name(champion_name)
        display_role = _ROLE_MAP.get(str(role).upper(), role)
        return int(self._role_stats.get(key, {}).get(display_role, 0))

    def get_roles(self, champion_name: str) -> List[str]:
        key = self.normalize_name(champion_name)
        if key in self._role_stats:
            return list(self._role_stats[key])
        return self._role_data.get(key, [])

    def get_candidates(self, role: str) -> List[str]:
        display_role = _ROLE_MAP.get(str(role).upper(), role)
        if display_role not in self.VALID_ROLES:
            return []
        candidates = [champion for champion, roles in self._role_stats.items() if roles.get(display_role, 0) >= 10]
        for champion, roles in self._role_data.items():
            if champion not in self._role_stats and display_role in roles:
                candidates.append(champion)
        return sorted(set(candidates))

    def can_play(self, champion_name: str, role: str) -> bool:
        display_role = _ROLE_MAP.get(str(role).upper(), role)
        return display_role in self.get_roles(champion_name)

    def export_riot_role_data(self) -> Dict[str, Dict[str, int]]:
        return {
            champion: {_RIOT_ROLE_MAP[role]: percentage for role, percentage in roles.items() if role in _RIOT_ROLE_MAP}
            for champion, roles in self._role_stats.items()
        }

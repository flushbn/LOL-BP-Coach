import json
from pathlib import Path
from typing import Dict, Optional

from utils.champion_names import canonical_champion_key


PROJECT_ROOT = Path(__file__).resolve().parent.parent

TIER_SCORE = {"S": 95, "A": 80, "B": 65, "C": 50, "D": 35}

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


class MetaAnalyzer:
    """Read patch-scoped Meta data and keep every role independent."""

    def __init__(self, data_path: Optional[Path] = None):
        if data_path is None:
            data_path = self._resolve_data_path()
        if not data_path.exists():
            raise FileNotFoundError(f"Meta data not found: {data_path}")
        with open(data_path, "r", encoding="utf-8") as handle:
            raw_data: Dict[str, dict] = json.load(handle)
        self._meta_data = self._normalize_schema(raw_data)

    @staticmethod
    def _resolve_data_path() -> Path:
        data_dir = PROJECT_ROOT / "data"
        patch_file = data_dir / "patch_version.json"
        try:
            patch = json.loads(patch_file.read_text(encoding="utf-8")).get("current_patch")
            patch_path = data_dir / str(patch) / "meta_data.json"
            if patch and patch_path.exists():
                return patch_path
        except Exception:
            pass
        return data_dir / "meta_data.json"

    @staticmethod
    def _entry(payload: dict) -> dict:
        meta_score = float(payload.get("meta_score", 50) or 50)
        return {
            "win_rate": float(payload.get("winrate", payload.get("win_rate", 50)) or 50),
            "pick_rate": float(payload.get("pickrate", payload.get("pick_rate", 0)) or 0),
            "ban_rate": float(payload.get("banrate", payload.get("ban_rate", 0)) or 0),
            "tier": payload.get("tier", "Unknown"),
            "picks": int(payload.get("games", payload.get("picks", 0)) or 0),
            "games": int(payload.get("games", payload.get("picks", 0)) or 0),
            "meta_score": meta_score,
            "viability": min(100, max(0, round(meta_score * 2))),
        }

    def _normalize_schema(self, data: Dict[str, dict]) -> Dict[str, dict]:
        source = data.get("champions", data)
        normalized: Dict[str, dict] = {}
        for raw_champion, payload in source.items():
            if not isinstance(payload, dict):
                continue
            champion = canonical_champion_key(raw_champion)
            record = normalized.setdefault(champion, {"roles": {}})
            role_entries = payload.get("roles", {})
            if not isinstance(role_entries, dict) or not role_entries:
                role_entries = {"ALL": payload}

            for raw_role, raw_entry in role_entries.items():
                if not isinstance(raw_entry, dict):
                    continue
                role = _role_key(raw_role) or "ALL"
                entry = self._entry(raw_entry)
                current = record["roles"].get(role)
                if current is None or (entry["games"], entry["meta_score"]) > (current["games"], current["meta_score"]):
                    record["roles"][role] = entry

        for record in normalized.values():
            roles = record["roles"]
            best_role = max(roles, key=lambda role: (roles[role]["meta_score"], roles[role]["games"]))
            record["best_role"] = best_role
        return normalized

    def normalize_name(self, name: str) -> str:
        key = canonical_champion_key(name)
        if key in self._meta_data:
            return key
        lowered = key.lower()
        for champion in self._meta_data:
            if champion.lower() == lowered:
                return champion
        return key

    def get_details(self, champion_name: str, role: str | None = None) -> Optional[dict]:
        record = self._meta_data.get(self.normalize_name(champion_name))
        if not record:
            return None
        requested_role = _role_key(role)
        if requested_role:
            entry = record["roles"].get(requested_role)
            if entry is None:
                entry = record["roles"].get("ALL")
            if entry is None:
                return None
        else:
            entry = record["roles"].get(record["best_role"])
        return {**entry, "role": requested_role or record["best_role"], "available_roles": list(record["roles"])}

    def analyze(self, champion_name: str, role: str | None = None) -> int:
        details = self.get_details(champion_name, role)
        if not details:
            return 50
        tier_score = TIER_SCORE.get(str(details["tier"]).split("-")[0].split("+")[0], 50)
        score = tier_score * 0.4 + details["win_rate"] * 0.3 + details["pick_rate"] * 0.15 + details["ban_rate"] * 0.15
        return min(100, max(0, round(score)))

    def get_viability(self, champion_name: str, role: str | None = None) -> int:
        details = self.get_details(champion_name, role)
        return int(details["viability"]) if details else 50

    def get_tier(self, champion_name: str, role: str | None = None) -> str:
        details = self.get_details(champion_name, role)
        return str(details["tier"]) if details else "?"

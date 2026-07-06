import json
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


TIER_SCORE = {"S": 95, "A": 80, "B": 65, "C": 50, "D": 35}


class MetaAnalyzer:
    """Analyze champion meta strength and viability."""

    def __init__(self, data_path: Optional[Path] = None):
        if data_path is None:
            data_path = self._resolve_data_path()
        if not data_path.exists():
            raise FileNotFoundError(f"Meta data not found: {data_path}")
        with open(data_path, "r", encoding="utf-8") as f:
            raw_data: Dict[str, dict] = json.load(f)
        self._meta_data: Dict[str, dict] = self._normalize_schema(raw_data)
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

    def _resolve_data_path(self) -> Path:
        data_dir = PROJECT_ROOT / "data"
        patch_file = data_dir / "patch_version.json"
        try:
            if patch_file.exists():
                patch = json.loads(patch_file.read_text(encoding="utf-8")).get("current_patch")
                if patch:
                    patch_path = data_dir / str(patch) / "meta_data.json"
                    if patch_path.exists():
                        return patch_path
        except Exception:
            pass
        return data_dir / "meta_data.json"

    def _normalize_schema(self, data: Dict[str, dict]) -> Dict[str, dict]:
        if "champions" not in data:
            return data
        normalized: Dict[str, dict] = {}
        for champion, payload in data.get("champions", {}).items():
            roles = payload.get("roles", {})
            best_role = payload.get("best_role")
            entry = roles.get(best_role) if best_role else None
            if not entry and roles:
                entry = next(iter(roles.values()))
            if not entry:
                continue
            meta_score = float(entry.get("meta_score", 50) or 50)
            normalized[champion] = {
                "win_rate": entry.get("winrate", 50),
                "pick_rate": entry.get("pickrate", 0),
                "ban_rate": entry.get("banrate", 0),
                "tier": entry.get("tier", "Unknown"),
                "picks": entry.get("games", 0),
                "games": entry.get("games", 0),
                "meta_score": meta_score,
                "viability": min(100, max(0, round(meta_score * 2))),
                "roles": roles,
            }
        return normalized

    def normalize_name(self, name: str) -> str:
        if name in self._meta_data:
            return name
        if name in self._cn_to_en:
            eng = self._cn_to_en[name]
            if eng in self._meta_data:
                return eng
        for key in self._meta_data:
            if key.lower() == name.lower():
                return key
        return name

    def analyze(self, champion_name: str) -> int:
        """Get MetaScore (0-100)."""
        key = self.normalize_name(champion_name)
        if key not in self._meta_data:
            return 50
        m = self._meta_data[key]
        tier_s = TIER_SCORE.get(m["tier"], 50)
        score = tier_s * 0.4 + m["win_rate"] * 0.3 + m["pick_rate"] * 0.15 + m["ban_rate"] * 0.15
        return min(100, max(0, round(score)))

    def get_viability(self, champion_name: str) -> int:
        """Get champion viability score (0-100). Higher = more viable in current meta."""
        key = self.normalize_name(champion_name)
        if key not in self._meta_data:
            return 50
        v = self._meta_data[key].get("viability", 50)
        return min(100, max(0, int(v)))

    def get_tier(self, champion_name: str) -> str:
        key = self.normalize_name(champion_name)
        if key not in self._meta_data:
            return "?"
        return self._meta_data[key]["tier"]

    def get_details(self, champion_name: str) -> Optional[dict]:
        key = self.normalize_name(champion_name)
        return self._meta_data.get(key)



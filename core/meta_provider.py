import json
from pathlib import Path
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class MetaProvider:
    """Unified champion meta data access layer.

    Currently reads from local JSON. Can be swapped for an online
    data source without changing the consumer code.
    """

    def __init__(self, data_path: Optional[Path] = None):
        if data_path is None:
            data_path = PROJECT_ROOT / "data" / "16.13" / "meta_data.json"
        if not data_path.exists():
            raise FileNotFoundError(f"Meta data not found: {data_path}")
        with open(data_path, "r", encoding="utf-8") as f:
            self._meta_data: Dict[str, dict] = json.load(f)
        self._meta_data.pop("_meta", None)  # Strip internal metadata

    def get_meta(self, champion: str) -> Optional[dict]:
        """Get full meta data for a champion.

        Returns:
            dict with win_rate, pick_rate, ban_rate, tier, viability,
            or None if champion not found.
        """
        # Direct lookup
        if champion in self._meta_data:
            return self._meta_data[champion]
        # Case-insensitive fallback
        for key in self._meta_data:
            if key.lower() == champion.lower():
                return self._meta_data[key]
        return None

    def get_win_rate(self, champion: str) -> float:
        meta = self.get_meta(champion)
        return meta["win_rate"] if meta else 50.0

    def get_pick_rate(self, champion: str) -> float:
        meta = self.get_meta(champion)
        return meta["pick_rate"] if meta else 5.0

    def get_ban_rate(self, champion: str) -> float:
        meta = self.get_meta(champion)
        return meta["ban_rate"] if meta else 2.0

    def get_tier(self, champion: str) -> str:
        meta = self.get_meta(champion)
        return meta["tier"] if meta else "?"

    def get_viability(self, champion: str) -> int:
        meta = self.get_meta(champion)
        return int(meta["viability"]) if meta else 50


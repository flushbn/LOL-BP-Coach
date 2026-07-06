import json
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class CounterAnalyzer:
    """Analyze champion counter picks against enemy team composition."""

    def __init__(self, data_path: Optional[Path] = None, use_v2: bool = False):
        if data_path is None:
            if use_v2:
                data_path = PROJECT_ROOT / "data" / "counter_data_v2.json"
            else:
                data_path = self._resolve_data_path()
        if not data_path.exists():
            raise FileNotFoundError(f"Counter data not found: {data_path}")
        with open(data_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        self._counter_data: Dict[str, Dict[str, int]] = self._normalize_schema(raw_data)

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
                    patch_path = data_dir / str(patch) / "counter_data.json"
                    if patch_path.exists():
                        return patch_path
        except Exception:
            pass
        return data_dir / "counter_data.json"

    def _normalize_schema(self, data: Dict) -> Dict[str, Dict[str, int]]:
        if "champions" not in data:
            return data
        converted: Dict[str, Dict[str, int]] = {}
        for champion, opponents in data.get("champions", {}).items():
            for opponent, payload in opponents.items():
                score = int(round(float(payload.get("counter_score", 50) or 50)))
                converted.setdefault(opponent, {})[champion] = score
        return converted

    def normalize_name(self, name: str) -> str:
        if name in self._counter_data:
            return name
        if name in self._cn_to_en:
            eng = self._cn_to_en[name]
            if eng in self._counter_data:
                return eng
        for key in self._counter_data:
            if key.lower() == name.lower():
                return key
        return name

    def analyze(self, enemy_picks: List[str]) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        for enemy in enemy_picks:
            enemy_key = self.normalize_name(enemy)
            if enemy_key not in self._counter_data:
                continue
            for counter, score in self._counter_data[enemy_key].items():
                scores[counter] = scores.get(counter, 0) + score
        return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))

    def get_top_counters(
        self, enemy_picks: List[str], top_n: int = 10
    ) -> List[tuple[str, int]]:
        result = self.analyze(enemy_picks)
        return [(champ, score) for champ, score in list(result.items())[:top_n]]

    def get_counter_score(self, champion: str, enemy_picks: List[str]) -> int:
        result = self.analyze(enemy_picks)
        champ_key = self.normalize_name(champion)
        return result.get(champ_key, 0)



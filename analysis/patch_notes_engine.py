from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analysis.data_patch_manager import DataPatchManager, normalize_patch
from utils.champion_names import champion_display_name


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PATCH_NOTES_DIR = DATA_DIR / "patch_notes"


def _champion_key(name: str) -> str:
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


class PatchNotesEngine:
    def __init__(self, patch: str | None = None, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.patch = normalize_patch(patch or DataPatchManager(self.data_dir).get_current_patch())
        self.patch_notes_dir = self.data_dir / "patch_notes"
        self._notes = self._load_notes()
        self._change_index = self._build_change_index()

    def get_patch_summary(self) -> dict[str, Any]:
        champion_changes = self._notes.get("champion_changes", [])
        item_changes = self._notes.get("item_changes", [])
        rune_changes = self._notes.get("rune_changes", [])
        system_changes = self._notes.get("system_changes", [])

        rising = []
        falling = []
        for change in champion_changes:
            trend = self.compare_patch_impact(change.get("champion", ""))
            row = {
                "champion": change.get("champion", ""),
                "type": change.get("type", ""),
                "description": change.get("description", ""),
                "delta": trend.get("delta"),
                "trend": trend.get("trend", "stable"),
            }
            if change.get("type") == "buff":
                rising.append(row)
            elif change.get("type") == "nerf":
                falling.append(row)

        return {
            "patch": self.patch,
            "riot_patch": self._notes.get("riot_patch", self.patch),
            "source": self._notes.get("source", ""),
            "source_url": self._notes.get("source_url", ""),
            "champion_changes": champion_changes,
            "item_changes": item_changes,
            "rune_changes": rune_changes,
            "system_changes": system_changes,
            "meta_impacts": self._notes.get("meta_impacts", []),
            "rising": rising,
            "falling": falling,
        }

    def get_champion_patch_reason(self, champion: str) -> str:
        change = self._change_index.get(_champion_key(champion))
        if not change:
            return ""

        champion_name = champion_display_name(change.get("champion", champion))
        change_type = change.get("type", "adjust")
        if change_type == "buff":
            prefix = "当前版本加强"
        elif change_type == "nerf":
            prefix = "当前版本削弱"
        else:
            prefix = "当前版本调整"

        description = str(change.get("description", "")).strip()
        return f"{prefix}: {champion_name}" + (f"（{description}）" if description else "")

    def compare_patch_impact(self, champion: str) -> dict[str, Any]:
        current = self._get_best_winrate(self.patch, champion)
        previous_patch = self._find_previous_patch()
        previous = self._get_best_winrate(previous_patch, champion) if previous_patch else None

        delta = None
        trend = "stable"
        if current is not None and previous is not None:
            delta = round(current - previous, 2)
            if delta >= 1:
                trend = "buffed"
            elif delta <= -1:
                trend = "nerfed"
        else:
            change = self._change_index.get(_champion_key(champion), {})
            if change.get("type") == "buff":
                trend = "buffed"
            elif change.get("type") == "nerf":
                trend = "nerfed"

        return {
            "champion": champion,
            "before_patch": previous_patch,
            "after_patch": self.patch,
            "before_wr": previous,
            "after_wr": current,
            "delta": delta,
            "trend": trend,
        }

    def _load_notes(self) -> dict[str, Any]:
        path = self.patch_notes_dir / f"{self.patch}.json"
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {
            "patch": self.patch,
            "champion_changes": [],
            "item_changes": [],
            "rune_changes": [],
            "system_changes": [],
            "meta_impacts": [],
        }

    def _build_change_index(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for change in self._notes.get("champion_changes", []):
            key = _champion_key(change.get("champion", ""))
            if key:
                index[key] = change
        return index

    def _find_previous_patch(self) -> str | None:
        patches = []
        for item in self.data_dir.iterdir() if self.data_dir.exists() else []:
            if item.is_dir() and (item / "meta_data.json").exists():
                patch = normalize_patch(item.name)
                if patch != "unknown":
                    patches.append(patch)
        patches = sorted(set(patches), key=self._patch_tuple)
        current_tuple = self._patch_tuple(self.patch)
        previous = [patch for patch in patches if self._patch_tuple(patch) < current_tuple]
        return previous[-1] if previous else None

    def _get_best_winrate(self, patch: str | None, champion: str) -> float | None:
        if not patch:
            return None
        path = self.data_dir / patch / "meta_data.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

        key = _champion_key(champion)
        candidates: list[dict[str, Any]] = []
        champion_data = data.get("champions", {})
        for champ_name, payload in champion_data.items():
            if _champion_key(champ_name) == key:
                candidates.extend(payload.get("roles", {}).values())
                break

        if not candidates:
            for role_data in data.get("roles", {}).values():
                for champ_name, payload in role_data.items():
                    if _champion_key(champ_name) == key:
                        candidates.append(payload)

        best = None
        for payload in candidates:
            games = int(payload.get("games", 0) or 0)
            winrate = payload.get("winrate", payload.get("win_rate"))
            if winrate is None:
                continue
            if best is None or games > best[0]:
                best = (games, float(winrate))
        return round(best[1], 2) if best else None

    @staticmethod
    def _patch_tuple(patch: str) -> tuple[int, int]:
        parts = normalize_patch(patch).split(".")
        try:
            return int(parts[0]), int(parts[1])
        except Exception:
            return 0, 0


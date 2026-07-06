from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PATCH_FILE = DATA_DIR / "patch_version.json"
VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"


def normalize_patch(version: str) -> str:
    parts = str(version or "").split(".")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{int(parts[0])}.{int(parts[1])}"
    return str(version or "unknown")


class DataPatchManager:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.patch_file = self.data_dir / "patch_version.json"

    def get_current_patch(self) -> str:
        data = self.read_patch_info()
        patch = data.get("current_patch")
        if patch:
            return normalize_patch(patch)
        inferred = self._infer_patch_from_champion_json()
        if inferred != "unknown":
            self.write_patch_info(inferred, source="local_infer")
        return inferred

    def get_latest_patch(self, timeout: int = 8) -> str:
        response = requests.get(VERSIONS_URL, timeout=timeout)
        response.raise_for_status()
        versions = response.json()
        if not versions:
            return "unknown"
        return normalize_patch(versions[0])

    def read_patch_info(self) -> dict[str, Any]:
        try:
            if self.patch_file.exists():
                return json.loads(self.patch_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def write_patch_info(self, patch: str, source: str = "unknown", latest_patch: str | None = None):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_patch": normalize_patch(patch),
            "latest_patch": normalize_patch(latest_patch or patch),
            "updated_at": int(time.time()),
            "source": source,
        }
        self.patch_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.ensure_patch_cache(payload["current_patch"])
        return payload

    def is_outdated(self) -> bool:
        latest = self.get_latest_patch()
        current = self.get_current_patch()
        return latest != "unknown" and current != "unknown" and latest != current

    def get_status(self) -> dict[str, Any]:
        current = self.get_current_patch()
        latest = "unknown"
        error = ""
        try:
            latest = self.get_latest_patch()
        except Exception as exc:
            error = str(exc)
        return {
            "current_patch": current,
            "latest_patch": latest,
            "outdated": latest not in ("", "unknown") and current != latest,
            "error": error,
            "local_patches": self.list_local_patches(),
        }

    def switch_patch(self, patch: str):
        patch = normalize_patch(patch)
        if patch not in self.list_local_patches():
            raise ValueError(f"Patch cache not found: {patch}")
        return self.write_patch_info(patch, source="manual_switch", latest_patch=patch)

    def list_local_patches(self) -> list[str]:
        patches = set()
        cache_root = self.data_dir / "cache"
        if cache_root.exists():
            for item in cache_root.iterdir():
                if item.is_dir() and item.name[0:1].isdigit():
                    patches.add(normalize_patch(item.name))
        lol_cache = cache_root / "lolalytics"
        if lol_cache.exists():
            for item in lol_cache.iterdir():
                if item.is_dir() and item.name[0:1].isdigit():
                    patches.add(normalize_patch(item.name))
        current = self.read_patch_info().get("current_patch")
        if current:
            patches.add(normalize_patch(current))
        return sorted(patches)

    def ensure_patch_cache(self, patch: str):
        patch = normalize_patch(patch)
        (self.data_dir / "cache" / patch).mkdir(parents=True, exist_ok=True)
        (self.data_dir / "cache" / "lolalytics" / patch).mkdir(parents=True, exist_ok=True)

    def _infer_patch_from_champion_json(self) -> str:
        champion_json = self.data_dir / "zh_CN" / "champion.json"
        try:
            if champion_json.exists():
                data = json.loads(champion_json.read_text(encoding="utf-8"))
                return normalize_patch(data.get("version", "unknown"))
        except Exception:
            pass
        return "unknown"


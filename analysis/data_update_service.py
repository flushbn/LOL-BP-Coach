from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Callable

import requests

from analysis.data_patch_manager import DATA_DIR, ROOT, DataPatchManager, normalize_patch
from analysis.lolalytics_client import LolalyticsClient
from analysis.online_meta_sync import OnlineMetaSync


LOG_PATH = ROOT / "logs" / "update.log"
DATA_FILES = [
    DATA_DIR / "meta_data.json",
    DATA_DIR / "counter_data.json",
    DATA_DIR / "synergy_data.json",
    ROOT / "champion_data.json",
    DATA_DIR / "zh_CN" / "champion.json",
]


class DataUpdateService:
    def __init__(self, manager: DataPatchManager | None = None):
        self.manager = manager or DataPatchManager()

    def update_all_data(self, progress: Callable[[int, str], None] | None = None, online: bool = True) -> dict:
        progress = progress or (lambda value, message: None)
        started = int(time.time())
        backup_dir = DATA_DIR / "backups" / f"update_{started}"
        latest_patch = self.manager.get_current_patch()
        source = "fallback"

        try:
            progress(5, "创建备份")
            self._backup_files(backup_dir)

            if online:
                progress(15, "检查最新 patch")
                latest_patch = self.manager.get_latest_patch()
                source = "online"

            progress(30, "更新英雄基础数据")
            self._update_champion_data(latest_patch, online=online)

            progress(50, "更新 Meta / Counter / Synergy")
            fallback_files = self._update_strategy_data(latest_patch, online=online, progress=progress)

            progress(65, "更新 Lolalytics cache")
            self.update_lolalytics_data(latest_patch)

            progress(80, "清理旧缓存")
            removed_cache = self.rebuild_cache(latest_patch)

            progress(92, "写入 patch 信息")
            info = self.manager.write_patch_info(latest_patch, source=source, latest_patch=latest_patch)

            result = {
                "ok": True,
                "patch": normalize_patch(latest_patch),
                "source": source,
                "fallback_files": fallback_files,
                "removed_cache": removed_cache,
                "patch_info": info,
            }
            self._log("SUCCESS", result)
            progress(100, "更新完成")
            return result
        except Exception as exc:
            self._rollback_files(backup_dir)
            result = {"ok": False, "error": str(exc), "patch": normalize_patch(latest_patch)}
            self._log("FAILED", result)
            progress(100, f"更新失败: {exc}")
            return result

    def update_lolalytics_data(self, patch: str | None = None) -> dict:
        patch = normalize_patch(patch or self.manager.get_current_patch())
        client = LolalyticsClient(patch=patch)
        client.clean_old_cache(max_days=30)
        self.manager.ensure_patch_cache(patch)
        return {"patch": patch, "cache_dir": str(client._cache_dir(patch))}

    def update_full_lolalytics_meta(
        self,
        patch: str | None = None,
        progress: Callable[[int, str], None] | None = None,
    ) -> dict:
        patch = normalize_patch(patch or self.manager.get_current_patch())
        self.manager.ensure_patch_cache(patch)
        sync = OnlineMetaSync(patch=patch, limit_per_role=20)
        result = sync.build_full_meta(progress=progress)
        self.manager.write_patch_info(patch, source="lolalytics_full_meta", latest_patch=patch)
        self._log("FULL_META_SUCCESS", result)
        return result

    def update_full_lolalytics_data(
        self,
        patch: str | None = None,
        progress: Callable[[int, str], None] | None = None,
    ) -> dict:
        progress = progress or (lambda value, message: None)
        patch = normalize_patch(patch or self.manager.get_current_patch())
        self.manager.ensure_patch_cache(patch)
        sync = OnlineMetaSync(patch=patch, limit_per_role=20)
        progress(3, "?????????????")
        meta_result = sync.build_full_meta(progress=lambda value, message: progress(3 + round(value * 0.42), message))
        detail_result = sync.build_full_detail_data(progress=lambda value, message: progress(45 + round(value * 0.53), message))
        self.manager.write_patch_info(patch, source="lolalytics_full_data", latest_patch=patch)
        result = {"patch": patch, "meta": meta_result, "detail": detail_result}
        self._log("FULL_LOLALYTICS_DATA_SUCCESS", result)
        progress(100, "????? / ?? / ???????")
        return result

    def rebuild_cache(self, patch: str | None = None) -> int:
        patch = normalize_patch(patch or self.manager.get_current_patch())
        self.manager.ensure_patch_cache(patch)
        client = LolalyticsClient(patch=patch)
        return client.clean_old_cache(max_days=30)

    def _update_champion_data(self, patch: str, online: bool):
        patch = normalize_patch(patch)
        if not online:
            self._ensure_required_file(ROOT / "champion_data.json")
            return
        version = self._resolve_full_version(patch)
        url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/zh_CN/champion.json"
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        champion_payload = response.json()
        self._atomic_write(DATA_DIR / "zh_CN" / "champion.json", champion_payload)
        self._atomic_write(ROOT / "champion_data.json", self._merge_champion_index(champion_payload))

    def _resolve_full_version(self, patch: str) -> str:
        versions = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=8).json()
        patch = normalize_patch(patch)
        for version in versions:
            if normalize_patch(version) == patch:
                return version
        if versions:
            return versions[0]
        raise RuntimeError("No Data Dragon versions available")

    def _merge_champion_index(self, champion_payload: dict) -> dict:
        old_path = ROOT / "champion_data.json"
        old = {}
        if old_path.exists():
            try:
                old = json.loads(old_path.read_text(encoding="utf-8"))
            except Exception:
                old = {}
        merged = {}
        for champion_id, info in champion_payload.get("data", {}).items():
            previous = old.get(champion_id, {})
            tags = set(str(tag).lower() for tag in info.get("tags", []))
            tags.update(previous.get("tags", []))
            merged[champion_id] = {
                "roles": previous.get("roles", []),
                "tags": sorted(tags),
            }
        return merged

    def _update_strategy_data(self, patch: str, online: bool, progress: Callable[[int, str], None] | None = None) -> list[str]:
        if online:
            progress = progress or (lambda value, message: None)
            sync = OnlineMetaSync(patch=normalize_patch(patch), limit_per_role=20)
            progress(50, "???? BP ??")
            sync.build_all()
            progress(58, "?????????? Meta / ?? / ????")
            sync.build_full_meta(progress=lambda value, message: progress(58 + round(value * 0.06), message))
            sync.build_full_detail_data(progress=lambda value, message: progress(64 + round(value * 0.14), message))
            return []
        for path in (DATA_DIR / "meta_data.json", DATA_DIR / "counter_data.json", DATA_DIR / "synergy_data.json"):
            self._ensure_required_file(path)
        return ["meta_data.json", "counter_data.json", "synergy_data.json"]

    def _update_meta_data_from_lolalytics(self, patch: str):
        meta_path = DATA_DIR / "meta_data.json"
        old = {}
        if meta_path.exists():
            old = json.loads(meta_path.read_text(encoding="utf-8"))
        client = LolalyticsClient(patch=patch)
        tier_score = {
            "S+": 92,
            "S": 86,
            "S-": 82,
            "A+": 78,
            "A": 74,
            "A-": 70,
            "B+": 66,
            "B": 62,
            "B-": 58,
            "C+": 54,
            "C": 50,
            "C-": 46,
            "D+": 42,
            "D": 38,
            "D-": 34,
        }
        updated = dict(old)
        for lane in ("top", "jungle", "middle", "bottom", "support"):
            tierlist = client.get_tierlist(lane=lane, tier="emerald", limit=50) or []
            for item in tierlist:
                name = item.get("name")
                tier = item.get("tier", "Unknown")
                if not name:
                    continue
                current = dict(updated.get(name, {}))
                current["tier"] = tier
                current["viability"] = max(int(current.get("viability", 0) or 0), tier_score.get(tier, 50))
                updated[name] = current
        if not updated:
            raise RuntimeError("Lolalytics tierlist returned no data")
        self._atomic_write(meta_path, updated)

    def _preserve_local_strategy_data(self) -> list[str]:
        preserved = []
        for path in (DATA_DIR / "meta_data.json", DATA_DIR / "counter_data.json", DATA_DIR / "synergy_data.json"):
            self._ensure_required_file(path)
            preserved.append(path.name)
        return preserved

    def _ensure_required_file(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Required data file missing: {path}")

    def _backup_files(self, backup_dir: Path):
        backup_dir.mkdir(parents=True, exist_ok=True)
        for path in DATA_FILES:
            if path.exists():
                dest = backup_dir / path.relative_to(ROOT)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)

    def _rollback_files(self, backup_dir: Path):
        if not backup_dir.exists():
            return
        for backup in backup_dir.rglob("*"):
            if backup.is_file():
                target = ROOT / backup.relative_to(backup_dir)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)

    def _atomic_write(self, path: Path, payload: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _log(self, status: str, payload: dict):
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"time": int(time.time()), "status": status, **payload}, ensure_ascii=False)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


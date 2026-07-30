from __future__ import annotations

import hashlib
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SNAPSHOT_FILES = ("meta_data.json", "counter_data.json", "synergy_data.json")


class DataSnapshotManager:
    """Stores immutable, timestamped BP-data snapshots inside each patch."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR

    def capture(self, patch: str, source: str) -> dict[str, Any]:
        patch_dir = self.data_dir / str(patch)
        payloads = self._load_and_validate(patch_dir)
        fingerprints = {
            name: self._file_fingerprint(patch_dir / name)
            for name in SNAPSHOT_FILES
        }
        content_hash = hashlib.sha256(
            json.dumps(fingerprints, sort_keys=True).encode("utf-8")
        ).hexdigest()

        latest = self.get_latest(patch)
        if latest and latest.get("content_hash") == content_hash:
            return {"created": False, "snapshot": latest}

        now = datetime.now(timezone.utc)
        snapshot_id = now.strftime("%Y%m%d_%H%M%S")
        target = patch_dir / "snapshots" / snapshot_id
        target.mkdir(parents=True, exist_ok=False)
        for name in SNAPSHOT_FILES:
            shutil.copy2(patch_dir / name, target / name)

        manifest = {
            "schema_version": 1,
            "patch": str(patch),
            "captured_at": now.isoformat(),
            "captured_at_epoch": int(time.time()),
            "source": source,
            "source_generated_at": payloads["meta_data.json"].get("generated_at"),
            "content_hash": content_hash,
            "files": fingerprints,
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"created": True, "snapshot": manifest}

    def get_latest(self, patch: str) -> dict[str, Any] | None:
        snapshots_dir = self.data_dir / str(patch) / "snapshots"
        if not snapshots_dir.exists():
            return None
        manifests: list[dict[str, Any]] = []
        for manifest_path in snapshots_dir.glob("*/manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["snapshot_id"] = manifest_path.parent.name
                manifests.append(manifest)
            except (OSError, ValueError, TypeError):
                continue
        if not manifests:
            return None
        return max(manifests, key=lambda item: int(item.get("captured_at_epoch", 0) or 0))

    def get_status(self, patch: str, stale_after_hours: int = 72) -> dict[str, Any]:
        latest = self.get_latest(patch)
        if not latest:
            return {
                "available": False,
                "stale": True,
                "snapshot_count": 0,
                "message": "No verified data snapshot is available.",
            }
        snapshots_dir = self.data_dir / str(patch) / "snapshots"
        count = len(list(snapshots_dir.glob("*/manifest.json")))
        source_time = int(latest.get("source_generated_at") or latest.get("captured_at_epoch") or 0)
        age_hours = max(0.0, (time.time() - source_time) / 3600) if source_time else None
        return {
            "available": True,
            "stale": age_hours is None or age_hours >= stale_after_hours,
            "snapshot_count": count,
            "latest_snapshot": latest,
            "age_hours": round(age_hours, 1) if age_hours is not None else None,
            "stale_after_hours": stale_after_hours,
        }

    @staticmethod
    def _file_fingerprint(path: Path) -> dict[str, Any]:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return {"sha256": digest, "size": path.stat().st_size}

    @staticmethod
    def _load_and_validate(patch_dir: Path) -> dict[str, dict[str, Any]]:
        payloads: dict[str, dict[str, Any]] = {}
        for name in SNAPSHOT_FILES:
            path = patch_dir / name
            if not path.exists():
                raise FileNotFoundError(f"Cannot snapshot missing data file: {path}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not payload:
                raise ValueError(f"Cannot snapshot invalid data file: {path}")
            payloads[name] = payload
        meta = payloads["meta_data.json"]
        if not meta.get("roles") or not meta.get("champions"):
            raise ValueError("Cannot snapshot Meta data without role and champion entries")
        return payloads

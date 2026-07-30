"""Create a signed-by-hash GitHub data manifest after a validated Firecrawl sync."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PACKAGE_FILES = ("meta_data.json", "counter_data.json", "synergy_data.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(patch: str) -> dict:
    patch_dir = DATA_DIR / patch
    files = {}
    for name in PACKAGE_FILES:
        path = patch_dir / name
        if not path.exists():
            raise FileNotFoundError(path)
        files[name] = {
            "path": f"data/{patch}/{name}",
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }
    content_hash = hashlib.sha256(
        json.dumps(files, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    patch_info = {}
    try:
        patch_info = json.loads((DATA_DIR / "patch_version.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    manifest = {
        "schema_version": 1,
        "patch": patch,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "source": str(patch_info.get("source") or "maintainer_verified"),
        "content_hash": content_hash,
        "files": files,
    }
    (patch_dir / "data_package_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def update_index(manifest: dict) -> dict:
    index_path = DATA_DIR / "data_package_index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        index = {"schema_version": 1, "packages": []}
    entry = {
        "patch": manifest["patch"],
        "published_at": manifest["published_at"],
        "content_hash": manifest["content_hash"],
        "manifest_path": f"data/{manifest['patch']}/data_package_manifest.json",
    }
    packages = [
        item for item in index.get("packages", [])
        if isinstance(item, dict) and item.get("patch") != manifest["patch"]
    ]
    packages.append(entry)
    index = {"schema_version": 1, "packages": packages}
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("patch", nargs="?", default="")
    args = parser.parse_args()
    if args.patch:
        patch = args.patch
    else:
        patch = json.loads((DATA_DIR / "patch_version.json").read_text(encoding="utf-8"))["current_patch"]
    manifest = build_manifest(patch)
    update_index(manifest)
    print(f"Published local package manifest for {patch}: {manifest['content_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

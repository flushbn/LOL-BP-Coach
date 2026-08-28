from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from base64 import b64decode
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REPOSITORY = "flushbn/LOL-BP-Coach"
RAW_BASE_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/main"
RAW_FALLBACK_URL = f"https://github.com/{REPOSITORY}/raw/main"
CONTENTS_API_URL = f"https://api.github.com/repos/{REPOSITORY}/contents"
INDEX_PATH = "data/data_package_index.json"
PACKAGE_FILES = ("meta_data.json", "counter_data.json", "synergy_data.json")


class DataPackageError(RuntimeError):
    pass


class GitHubDataPackageClient:
    """Downloads maintainer-verified BP data from the public GitHub repository."""

    def __init__(self, data_dir: Path | None = None, base_url: str | None = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.base_urls = [base_url.rstrip("/")] if base_url else [RAW_BASE_URL, RAW_FALLBACK_URL]
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "LoL-BP-Coach-Data-Updater/1.0",
            "Cache-Control": "no-cache",
        })

    def get_remote_status(self, current_patch: str) -> dict[str, Any]:
        index = self.fetch_index()
        package = self._select_package(index, preferred_patch=current_patch)
        latest = self._select_package(index)
        if not package:
            return {
                "available": False,
                "error": f"No verified GitHub package for patch {current_patch}.",
                "latest_patch": latest.get("patch") if latest else "unknown",
            }

        local_manifest = self._read_json(self.data_dir / str(current_patch) / "data_package_manifest.json")
        remote_revision = str(package.get("content_hash", ""))
        local_revision = str(local_manifest.get("content_hash", ""))
        return {
            "available": True,
            "current_package": package,
            "latest_package": latest,
            "latest_patch": str(latest.get("patch", current_patch)) if latest else current_patch,
            "update_available": remote_revision != local_revision,
            "published_at": package.get("published_at", ""),
        }

    def fetch_index(self) -> dict[str, Any]:
        return self._request_json(INDEX_PATH)

    def update(self, preferred_patch: str | None = None) -> dict[str, Any]:
        index = self.fetch_index()
        package = self._select_package(index, preferred_patch=preferred_patch)
        if not package:
            package = self._select_package(index)
        if not package:
            raise DataPackageError("GitHub has not published a verified data package yet.")

        patch = self._validate_manifest_reference(package)
        manifest = self._request_json(str(package["manifest_path"]))
        self._validate_manifest(manifest, patch, expected_hash=str(package.get("content_hash", "")))
        result = self._stage_and_apply(manifest)
        result["index"] = package
        return result

    def _stage_and_apply(self, manifest: dict[str, Any]) -> dict[str, Any]:
        patch = str(manifest["patch"])
        files = manifest["files"]
        staging = self.data_dir / ".staging" / f"github_{patch}_{uuid.uuid4().hex}"
        backup = self.data_dir / "backups" / f"github_{int(time.time())}" / patch
        target_dir = self.data_dir / patch
        downloaded: list[str] = []
        try:
            staging.mkdir(parents=True, exist_ok=False)
            for name in PACKAGE_FILES:
                entry = files[name]
                content = self._request_bytes(str(entry["path"]))
                if len(content) != int(entry["size"]):
                    raise DataPackageError(f"Downloaded size mismatch for {name}.")
                if self._sha256(content) != str(entry["sha256"]):
                    raise DataPackageError(f"Downloaded checksum mismatch for {name}.")
                payload = json.loads(content.decode("utf-8"))
                if not isinstance(payload, dict) or not payload:
                    raise DataPackageError(f"Downloaded JSON is invalid for {name}.")
                (staging / name).write_bytes(content)
                downloaded.append(name)

            meta = json.loads((staging / "meta_data.json").read_text(encoding="utf-8"))
            if not meta.get("roles") or not meta.get("champions"):
                raise DataPackageError("Downloaded Meta data has no champion coverage.")

            target_dir.mkdir(parents=True, exist_ok=True)
            backup.mkdir(parents=True, exist_ok=True)
            for name in PACKAGE_FILES:
                target = target_dir / name
                if target.exists():
                    shutil.copy2(target, backup / name)
            for name in PACKAGE_FILES:
                (staging / name).replace(target_dir / name)
            (target_dir / "data_package_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return {
                "patch": patch,
                "downloaded": downloaded,
                "source": manifest.get("source", "github_verified"),
                "published_at": manifest.get("published_at", ""),
                "backup": str(backup),
            }
        except Exception as exc:
            if backup.exists():
                for name in PACKAGE_FILES:
                    previous = backup / name
                    if previous.exists():
                        shutil.copy2(previous, target_dir / name)
            if isinstance(exc, DataPackageError):
                raise
            raise DataPackageError(str(exc)) from exc
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _select_package(self, index: dict[str, Any], preferred_patch: str | None = None) -> dict[str, Any] | None:
        packages = [item for item in index.get("packages", []) if isinstance(item, dict)]
        if preferred_patch:
            matching = [item for item in packages if str(item.get("patch")) == str(preferred_patch)]
            if matching:
                return max(matching, key=lambda item: str(item.get("published_at", "")))
        if not packages:
            return None
        return max(packages, key=lambda item: self._patch_key(str(item.get("patch", "0.0"))))

    def _validate_manifest_reference(self, package: dict[str, Any]) -> str:
        patch = str(package.get("patch", ""))
        manifest_path = str(package.get("manifest_path", ""))
        expected = f"data/{patch}/data_package_manifest.json"
        if not patch or manifest_path != expected:
            raise DataPackageError("Invalid GitHub data package reference.")
        return patch

    def _validate_manifest(self, manifest: dict[str, Any], patch: str, expected_hash: str) -> None:
        if manifest.get("schema_version") != 1 or str(manifest.get("patch")) != patch:
            raise DataPackageError("Invalid data package manifest.")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != set(PACKAGE_FILES):
            raise DataPackageError("Data package file list is not allowed.")
        actual_hash = str(manifest.get("content_hash", ""))
        if not actual_hash or (expected_hash and actual_hash != expected_hash):
            raise DataPackageError("Data package revision does not match the index.")
        for name in PACKAGE_FILES:
            entry = files.get(name)
            expected_path = f"data/{patch}/{name}"
            if not isinstance(entry, dict) or str(entry.get("path")) != expected_path:
                raise DataPackageError(f"Invalid data package path for {name}.")
            if not str(entry.get("sha256", "")) or int(entry.get("size", 0) or 0) <= 0:
                raise DataPackageError(f"Invalid data package checksum for {name}.")

    def _request_json(self, path: str) -> dict[str, Any]:
        try:
            response = self._request(path, timeout=12)
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DataPackageError(f"GitHub data request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise DataPackageError("GitHub returned an invalid JSON package.")
        return payload

    def _request_bytes(self, path: str) -> bytes:
        """Fetch committed file bytes through GitHub's Contents API.

        The raw CDN normalizes CRLF JSON to LF, which invalidates manifests
        created from the checked-in package bytes on Windows.
        """
        relative_path = quote(path.lstrip("/"), safe="/")
        url = f"{CONTENTS_API_URL}/{relative_path}?ref=main"
        errors: list[str] = []
        try:
            for attempt in range(2):
                try:
                    response = self.session.get(url, timeout=35)
                    response.raise_for_status()
                    payload = response.json()
                    encoded = payload.get("content") if isinstance(payload, dict) else None
                    if not isinstance(encoded, str) or payload.get("encoding") != "base64":
                        blob_url = payload.get("git_url") if isinstance(payload, dict) else None
                        if not isinstance(blob_url, str) or not blob_url:
                            raise DataPackageError("GitHub returned an invalid file payload.")
                        blob_response = self.session.get(blob_url, timeout=35)
                        blob_response.raise_for_status()
                        blob_payload = blob_response.json()
                        encoded = blob_payload.get("content") if isinstance(blob_payload, dict) else None
                        if not isinstance(encoded, str) or blob_payload.get("encoding") != "base64":
                            raise DataPackageError("GitHub returned an invalid file payload.")
                    return b64decode(encoded)
                except (requests.RequestException, ValueError, TypeError) as exc:
                    errors.append(str(exc))
                    if attempt == 0:
                        time.sleep(0.8)
        except DataPackageError:
            raise
        detail = errors[-1] if errors else "unknown network error"
        raise DataPackageError(f"GitHub data download failed: {detail}")

    def _request(self, path: str, timeout: int) -> requests.Response:
        errors: list[str] = []
        relative_path = path.lstrip("/")
        for base_url in self.base_urls:
            url = f"{base_url}/{relative_path}"
            for attempt in range(2):
                try:
                    response = self.session.get(url, timeout=timeout)
                    response.raise_for_status()
                    return response
                except requests.RequestException as exc:
                    errors.append(f"{base_url}: {exc}")
                    if attempt == 0:
                        time.sleep(0.8)
        detail = errors[-1] if errors else "unknown network error"
        raise DataPackageError(f"GitHub data service is unavailable: {detail}")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _patch_key(value: str) -> tuple[int, int]:
        parts = value.split(".")
        try:
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return 0, 0

"""Resource Manager — unified path resolution for frozen/Python modes."""

import sys, os, json, shutil
from pathlib import Path
from typing import Optional


class ResourceManager:
    """Central resource path resolver.

    - Frozen (PyInstaller): uses sys._MEIPASS as base.
    - Normal Python: uses project root (parent of this file -> utils/).
    - All paths are relative to the resolved base.
    """

    _instance: Optional["ResourceManager"] = None

    def __init__(self, base: Optional[Path] = None):
        if base:
            self._base = Path(base).resolve()
        elif getattr(sys, "frozen", False):
            self._base = Path(sys._MEIPASS).resolve()
        else:
            self._base = Path(__file__).resolve().parent.parent

        # Ensure standard directories exist
        self._ensure_dirs()

    @classmethod
    def get_instance(cls) -> "ResourceManager":
        if cls._instance is None:
            cls._instance = ResourceManager()
        return cls._instance

    @property
    def base(self) -> Path:
        return self._base

    def path(self, *parts: str) -> Path:
        """Get a resource path relative to project base."""
        return self._base.joinpath(*parts).resolve()

    def ensure_path(self, *parts: str) -> Path:
        """Get path, creating parent directory if needed."""
        p = self.path(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # --- Common resource shortcuts ---

    def data(self, *parts: str) -> Path:
        return self.path("data", *parts)

    def cache(self, *parts: str) -> Path:
        return self.ensure_path("data", "cache", *parts)

    def logs(self, *parts: str) -> Path:
        return self.ensure_path("logs", *parts)

    def config(self, *parts: str) -> Path:
        return self.ensure_path("data", *parts)

    def templates(self, *parts: str) -> Path:
        return self.path("img", "champion", *parts)

    def analysis(self, *parts: str) -> Path:
        return self.path("analysis", *parts)

    # --- Data loading helpers ---

    def load_json(self, *parts: str, default=None):
        """Load a JSON file, returning default on failure."""
        p = self.path(*parts)
        try:
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return default if default is not None else {}

    def write_json(self, data, *parts: str):
        """Write JSON file, creating parent dirs."""
        p = self.ensure_path(*parts)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    # --- Auto-create directories ---

    def _ensure_dirs(self):
        for sub in ["data", "data/cache", "data/cache/lolalytics", "logs"]:
            (self._base / sub).mkdir(parents=True, exist_ok=True)

    def seed_cache(self, seed_dir: str = "data/cache_seed"):
        """Copy seed cache files to live cache (does not overwrite newer)."""
        seed = self.path(seed_dir)
        if not seed.exists():
            return 0
        target = self.path("data", "cache")
        count = 0
        for f in seed.rglob("*.json"):
            rel = f.relative_to(seed)
            dest = target / rel
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
                count += 1
        return count

    # --- Crash log ---

    def log_crash(self, exc_info, context: str = ""):
        """Log an unhandled exception to logs/crash.log."""
        import traceback, datetime
        p = self.logs("crash.log")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tb = "".join(traceback.format_exception(*exc_info))
        msg = f"=== {timestamp} ===\nContext: {context}\n{tb}\n"
        with open(p, "a", encoding="utf-8") as f:
            f.write(msg)
        return p


# Module-level convenience
def get_resource_path(*parts: str) -> Path:
    return ResourceManager.get_instance().path(*parts)

def get_data_path(*parts: str) -> Path:
    return ResourceManager.get_instance().data(*parts)

def get_cache_path(*parts: str) -> Path:
    return ResourceManager.get_instance().cache(*parts)

def load_json(*parts: str, default=None):
    return ResourceManager.get_instance().load_json(*parts, default=default)

def log_crash(exc_info, context: str = ""):
    return ResourceManager.get_instance().log_crash(exc_info, context)


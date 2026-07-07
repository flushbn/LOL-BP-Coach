from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from utils.resource_manager import get_resource_path


def _normalize(name: str) -> str:
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


@lru_cache(maxsize=1)
def _load_champion_keys() -> dict[str, str]:
    keys: dict[str, str] = {}

    champion_data = get_resource_path("champion_data.json")
    try:
        if champion_data.exists():
            for key in json.loads(champion_data.read_text(encoding="utf-8")).keys():
                keys[_normalize(key)] = key
    except Exception:
        pass

    dragon_tail = get_resource_path("data", "zh_CN", "champion.json")
    try:
        if dragon_tail.exists():
            data = json.loads(dragon_tail.read_text(encoding="utf-8")).get("data", {})
            for key, info in data.items():
                keys[_normalize(key)] = key
                keys[_normalize(info.get("name", ""))] = key
                keys[_normalize(info.get("title", ""))] = key
    except Exception:
        pass

    aliases = {
        "wukong": "MonkeyKing",
        "monkeyking": "MonkeyKing",
        "kaisa": "Kaisa",
        "kaisa": "Kaisa",
        "belveth": "Belveth",
        "ksante": "KSante",
        "jarvaniv": "JarvanIV",
        "chogath": "Chogath",
        "velkoz": "Velkoz",
        "kogmaw": "KogMaw",
        "leesin": "LeeSin",
        "masteryi": "MasterYi",
        "missfortune": "MissFortune",
        "twistedfate": "TwistedFate",
        "xinzhao": "XinZhao",
        "aurelionsol": "AurelionSol",
        "drmundo": "DrMundo",
        "sona": "Sona",
        "琴女": "Sona",
        "娑娜": "Sona",
        "琴瑟仙女": "Sona",
    }
    for alias, key in aliases.items():
        keys[_normalize(alias)] = key

    return keys


def champion_key(name: str | None) -> str:
    if not name:
        return ""
    text = str(name)
    keys = _load_champion_keys()
    return keys.get(_normalize(text), text)


def champion_icon_path(name: str | None) -> Path | None:
    key = champion_key(name)
    if not key:
        return None

    candidates = [
        get_resource_path("img", "champion", f"{key}.png"),
        get_resource_path("demo1", "img", "champion", f"{key}.png"),
        get_resource_path("release", "LoL_BP_Assistant", "_internal", "img", "champion", f"{key}.png"),
    ]
    for path in candidates:
        if path.exists():
            return path
    icon_dir = get_resource_path("img", "champion")
    if icon_dir.exists():
        normalized_key = _normalize(key)
        for path in icon_dir.glob("*.png"):
            if _normalize(path.stem) == normalized_key:
                return path
    return None

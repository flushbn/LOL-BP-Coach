from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


def _normalize(name: str) -> str:
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


@lru_cache(maxsize=1)
def _load_name_maps() -> tuple[dict[str, str], dict[str, str]]:
    direct: dict[str, str] = {}
    normalized: dict[str, str] = {}

    paths = [
        ROOT / "data" / "zh_CN" / "champion.json",
        ROOT / "champion.json",
    ]
    for path in paths:
        try:
            if not path.exists():
                continue
            payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            for key, info in payload.get("data", {}).items():
                display = str(info.get("title") or info.get("name") or key).strip()
                if not display:
                    display = key
                direct[key] = display
                direct[display] = display
                normalized[_normalize(key)] = display
                normalized[_normalize(display)] = display
                if info.get("name"):
                    normalized[_normalize(info["name"])] = display
            if direct:
                break
        except Exception:
            continue

    aliases = {
        "wukong": "MonkeyKing",
        "monkeyking": "MonkeyKing",
        "kaisa": "Kaisa",
        "kai sa": "Kaisa",
        "kai'sa": "Kaisa",
        "belveth": "Belveth",
        "bel veth": "Belveth",
        "ksante": "KSante",
        "k sante": "KSante",
        "k'sante": "KSante",
        "jarvaniv": "JarvanIV",
        "jarvan iv": "JarvanIV",
        "chogath": "Chogath",
        "cho gath": "Chogath",
        "cho'gath": "Chogath",
        "velkoz": "Velkoz",
        "vel koz": "Velkoz",
        "vel'koz": "Velkoz",
        "kogmaw": "KogMaw",
        "kog maw": "KogMaw",
        "kog'maw": "KogMaw",
        "leesin": "LeeSin",
        "lee sin": "LeeSin",
        "masteryi": "MasterYi",
        "master yi": "MasterYi",
        "missfortune": "MissFortune",
        "miss fortune": "MissFortune",
        "twistedfate": "TwistedFate",
        "twisted fate": "TwistedFate",
        "xinzhao": "XinZhao",
        "xin zhao": "XinZhao",
        "aurelionsol": "AurelionSol",
        "aurelion sol": "AurelionSol",
        "drmundo": "DrMundo",
        "dr mundo": "DrMundo",
        "sona": "Sona",
        "琴女": "Sona",
        "娑娜": "Sona",
        "琴瑟仙女": "Sona",
    }
    for alias, canonical in aliases.items():
        display = direct.get(canonical) or normalized.get(_normalize(canonical))
        if display:
            normalized[_normalize(alias)] = display

    return direct, normalized


def champion_display_name(name: str | None) -> str:
    if not name:
        return ""
    direct, normalized = _load_name_maps()
    text = str(name)
    return direct.get(text) or normalized.get(_normalize(text)) or text


def champion_display_names(names: list[str] | tuple[str, ...] | None) -> list[str]:
    return [champion_display_name(name) for name in (names or [])]


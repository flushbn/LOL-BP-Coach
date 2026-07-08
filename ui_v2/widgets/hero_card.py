from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from utils.champion_assets import champion_icon_path, champion_key
from utils.champion_names import champion_display_name
from utils.game_terms_zh import items_zh


ROOT = Path(__file__).resolve().parent.parent.parent


class HeroCard(QFrame):
    clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._champion_key = ""
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("HeroCard")
        self.setFrameShape(QFrame.StyledPanel)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(12)

        self.avatar = QLabel("")
        self.avatar.setFixedSize(56, 56)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setObjectName("HeroAvatar")
        root.addWidget(self.avatar)

        center = QVBoxLayout()
        center.setSpacing(4)
        self.name = QLabel("")
        self.name.setObjectName("HeroName")
        self.tags = QLabel("")
        self.tags.setWordWrap(True)
        self.tags.setObjectName("HeroTags")
        center.addWidget(self.name)
        center.addWidget(self.tags)
        root.addLayout(center, 1)

        self.score = QLabel("")
        self.score.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.score.setObjectName("HeroScore")
        root.addWidget(self.score)

    def render(self, data: dict):
        raw_champion = data.get("champion") or data.get("champion_cn") or "Unknown"
        self._champion_key = str(raw_champion)
        champion = _safe_display_name(data)
        score = data.get("final_score", data.get("score", ""))
        lane_bonus = data.get("lane_bonus", 0)
        comfort_bonus = data.get("comfort_bonus", 0)
        patch_reason = data.get("patch_reason", "")
        reasons = data.get("reasons", [])
        confidence = data.get("data_sources_confidence", {})

        tags: list[str] = []
        if isinstance(reasons, list):
            tags.extend(str(reason) for reason in reasons[:2] if reason and not _looks_broken_text(str(reason)))
        elif reasons and not _looks_broken_text(str(reasons)):
            tags.append(str(reasons))
        if confidence.get("meta") == "high":
            tags.append("✔ 实证数据")
        if confidence.get("counter") == "high":
            tags.append("✔ 对位统计")
        if confidence.get("synergy") == "low":
            tags.append("⚠ 推断数据（协同）")
        if lane_bonus:
            tags.append(f"Lane {lane_bonus:+}")
        if comfort_bonus:
            tags.append(f"Comfort {comfort_bonus:+}")
        if patch_reason:
            tags.append(f"版本: {patch_reason}")
        quick_build = _quick_build(raw_champion, data.get("target_role", data.get("role", "")))
        if quick_build:
            tags.append("装备: " + " → ".join(items_zh(quick_build[:3])))

        self._set_avatar(raw_champion, champion)
        self.name.setText(str(champion))
        self.score.setText(str(score))
        self.tags.setText(" / ".join(tags) if tags else "Meta / Counter")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._champion_key:
            self.clicked.emit(self._champion_key)
        super().mousePressEvent(event)

    def _set_avatar(self, raw_champion: str, display_name: str):
        icon_path = champion_icon_path(raw_champion) or champion_icon_path(display_name)
        if icon_path:
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                self.avatar.setText("")
                self.avatar.setPixmap(
                    pixmap.scaled(
                        self.avatar.size(),
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation,
                    )
                )
                return

        self.avatar.clear()
        self.avatar.setText(display_name[:2])


def _safe_display_name(data: dict) -> str:
    champion_key = str(data.get("champion") or "")
    champion_cn = str(data.get("champion_cn") or "")
    if champion_cn and not _looks_broken_text(champion_cn):
        return champion_cn
    return champion_display_name(champion_key or champion_cn or "Unknown")


def _looks_broken_text(text: str) -> bool:
    clean = str(text or "").strip()
    if not clean:
        return False
    question_count = clean.count("?") + clean.count("？")
    return question_count >= max(2, len(clean) // 2)


@lru_cache(maxsize=1)
def _champion_data() -> dict:
    path = ROOT / "champion_data.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _role_data() -> dict:
    path = ROOT / "data" / "role_data.json"
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    except Exception:
        return {}


ROLE_TO_LANE = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MID": "middle",
    "MIDDLE": "middle",
    "ADC": "bottom",
    "BOTTOM": "bottom",
    "SUPPORT": "support",
    "UTILITY": "support",
}
ROLE_ALIASES = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "MID": "MID",
    "MIDDLE": "MID",
    "ADC": "ADC",
    "BOTTOM": "ADC",
    "SUPPORT": "SUPPORT",
    "UTILITY": "SUPPORT",
}
RIOT_ROLE_TO_INTERNAL = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "MIDDLE": "MID",
    "BOTTOM": "ADC",
    "UTILITY": "SUPPORT",
}

CHAMPION_QUICK_BUILDS = {
    "Malphite": ["Plated Steelcaps", "Sunfire Aegis", "Frozen Heart"],
    "LeeSin": ["Eclipse", "Sundered Sky", "Mercury's Treads"],
    "Ahri": ["Malignance", "Sorcerer's Shoes", "Lich Bane"],
    "Jhin": ["The Collector", "Infinity Edge", "Boots of Swiftness"],
    "Leona": ["Bloodsong", "Plated Steelcaps", "Locket of the Iron Solari"],
    "Garen": ["Stridebreaker", "Phantom Dancer", "Dead Man's Plate"],
    "Kennen": ["Hextech Rocketbelt", "Shadowflame", "Zhonya's Hourglass"],
    "Qiyana": ["Hubris", "Ionian Boots of Lucidity", "Serylda's Grudge"],
    "Zed": ["Hubris", "Serylda's Grudge", "Edge of Night"],
    "Talon": ["Youmuu's Ghostblade", "Opportunity", "Serylda's Grudge"],
    "Akali": ["Stormsurge", "Lich Bane", "Zhonya's Hourglass"],
    "Poppy": ["Iceborn Gauntlet", "Sunfire Aegis", "Thornmail"],
    "Rammus": ["Thornmail", "Plated Steelcaps", "Jak'Sho, The Protean"],
    "Darius": ["Stridebreaker", "Sterak's Gage", "Dead Man's Plate"],
    "Aatrox": ["Eclipse", "Sundered Sky", "Death's Dance"],
    "Camille": ["Trinity Force", "Sundered Sky", "Sterak's Gage"],
    "Fiora": ["Ravenous Hydra", "Trinity Force", "Death's Dance"],
    "Jax": ["Trinity Force", "Sundered Sky", "Wit's End"],
    "Irelia": ["Blade of The Ruined King", "Wit's End", "Death's Dance"],
    "Ashe": ["Kraken Slayer", "Terminus", "Runaan's Hurricane"],
    "Caitlyn": ["The Collector", "Infinity Edge", "Rapid Firecannon"],
    "KaiSa": ["Statikk Shiv", "Nashor's Tooth", "Guinsoo's Rageblade"],
    "Vi": ["Sundered Sky", "Black Cleaver", "Sterak's Gage"],
    "JarvanIV": ["Sundered Sky", "Black Cleaver", "Sterak's Gage"],
    "Lissandra": ["Malignance", "Zhonya's Hourglass", "Shadowflame"],
    "Malzahar": ["Blackfire Torch", "Rylai's Crystal Scepter", "Liandry's Torment"],
    "Galio": ["Hollow Radiance", "Kaenic Rookern", "Zhonya's Hourglass"],
    "Janna": ["Moonstone Renewer", "Redemption", "Mikael's Blessing"],
    "Milio": ["Moonstone Renewer", "Redemption", "Ardent Censer"],
    "Taric": ["Locket of the Iron Solari", "Knight's Vow", "Redemption"],
}


def _quick_build(champion: str, role: str = "") -> list[str]:
    raw_key = str(champion or "")
    key = raw_key if raw_key in _champion_data() else (champion_key(raw_key) or raw_key)
    if key in CHAMPION_QUICK_BUILDS:
        return CHAMPION_QUICK_BUILDS[key]
    cached = _cached_quick_build(key, role)
    if cached:
        return cached
    tags = set(_champion_data().get(key, {}).get("tags", []))
    if "marksman" in tags or "dps" in tags:
        return ["Kraken Slayer", "Infinity Edge", "Lord Dominik's Regards"]
    if "assassin" in tags and "ap" in tags:
        return ["Stormsurge", "Lich Bane", "Zhonya's Hourglass"]
    if "assassin" in tags:
        return ["Hubris", "Serylda's Grudge", "Edge of Night"]
    if "mage" in tags or "ap" in tags:
        return ["Malignance", "Shadowflame", "Rabadon's Deathcap"]
    if "support" in tags or "enchanter" in tags:
        return ["Moonstone Renewer", "Redemption", "Mikael's Blessing"]
    if "fighter" in tags:
        return ["Sundered Sky", "Black Cleaver", "Sterak's Gage"]
    if "tank" in tags or "frontline" in tags:
        return ["Sunfire Aegis", "Thornmail", "Kaenic Rookern"]
    return []


def _cached_quick_build(champion: str, role: str = "") -> list[str]:
    lane = ROLE_TO_LANE.get(str(role or "").upper()) or _primary_lane(champion)
    if not lane:
        return []
    cache_dir = ROOT / "data" / "cache" / "lolalytics" / "16.13" / "builds"
    lower = champion.lower()
    candidates = [
        cache_dir / f"item_paths_v2_champion={lower}_lane={lane}_tier=emerald.json",
        cache_dir / f"item_paths_champion={lower}_lane={lane}_tier=emerald.json",
    ]
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        data = payload.get("data", payload)
        names = [
            item.get("name", "")
            for item in (data.get("core_build", []) or [])
            if isinstance(item, dict) and item.get("name")
        ]
        if names:
            return names[:3]
    return []


def _primary_lane(champion: str) -> str:
    role_payload = _role_data().get(champion, {})
    best_role = ""
    best_score = -1
    for role, value in role_payload.items():
        internal = RIOT_ROLE_TO_INTERNAL.get(str(role).upper(), "")
        try:
            score = float(value)
        except Exception:
            score = 0
        if internal and score > best_score:
            best_role, best_score = internal, score
    if best_role:
        return ROLE_TO_LANE.get(best_role, "")
    roles = _champion_data().get(champion, {}).get("roles", [])
    if roles:
        return {
            "top": "top",
            "jungle": "jungle",
            "mid": "middle",
            "adc": "bottom",
            "support": "support",
        }.get(str(roles[0]).lower(), "")
    return ""

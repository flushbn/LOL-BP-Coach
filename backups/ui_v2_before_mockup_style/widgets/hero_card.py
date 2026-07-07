from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from utils.champion_assets import champion_icon_path
from utils.champion_names import champion_display_name


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

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from analysis.hero_detail_context import HeroDetailContextBuilder
from ui_v2.components.hero_detail_panel import HeroDetailPanel
from utils.champion_assets import champion_icon_path
from utils.champion_names import champion_display_name


ROLE_LABELS = {
    "TOP": "上路",
    "JUNGLE": "打野",
    "MID": "中路",
    "MIDDLE": "中路",
    "ADC": "射手",
    "BOTTOM": "射手",
    "SUPPORT": "辅助",
    "UTILITY": "辅助",
}


class LanePickCard(QFrame):
    clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._champion_key = ""
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("HeroCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(92)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(12)

        self.avatar = QLabel("")
        self.avatar.setFixedSize(50, 50)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setObjectName("HeroAvatar")
        root.addWidget(self.avatar)

        center = QVBoxLayout()
        center.setSpacing(4)
        self.name = QLabel("")
        self.name.setObjectName("HeroName")
        self.matchup = QLabel("")
        self.matchup.setObjectName("HeroTags")
        self.matchup.setWordWrap(True)
        self.stats = QLabel("")
        self.stats.setObjectName("HeroTags")
        self.stats.setWordWrap(True)
        center.addWidget(self.name)
        center.addWidget(self.matchup)
        center.addWidget(self.stats)
        root.addLayout(center, 1)

        self.score = QLabel("")
        self.score.setObjectName("HeroScore")
        self.score.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        root.addWidget(self.score)

    def render(self, data: dict):
        champion_key = str(data.get("champion", "") or "")
        self._champion_key = champion_key
        champion_name = champion_display_name(champion_key)
        opponent = champion_display_name(data.get("opponent", "") or "")
        lane_score = data.get("lane_score", "")
        delta = _format_delta(data.get("delta", 0))
        games = _format_games(data.get("games", 0))
        role_score = data.get("role_score", "")
        viability = data.get("viability_score", "")
        opponent_probability = data.get("opponent_probability", 0)

        self._set_avatar(champion_key, champion_name)
        self.name.setText(champion_name or champion_key or "未知英雄")
        self.score.setText(str(round(float(lane_score))) if _is_number(lane_score) else str(lane_score))
        self.matchup.setText(f"对位 {opponent or '未知'} / 优势 {delta}")
        probability_text = ""
        if _is_number(opponent_probability) and float(opponent_probability) > 0:
            probability_text = f" / 对位概率 {round(float(opponent_probability) * 100)}%"
        self.stats.setText(
            f"样本 {games} / 分路可信 {role_score}% / 强度 {viability}{probability_text}"
        )

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
        self.avatar.setText((display_name or raw_champion or "?")[:2])


class LanePage(QWidget):
    def __init__(self):
        super().__init__()
        self._state: dict = {}
        self._recs: list[dict] = []
        self._detail_builder = HeroDetailContextBuilder()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("对线推荐")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget{background:transparent;border:none;}")
        layout.addWidget(self.stack, 1)

        self.list_page = QWidget()
        list_layout = QVBoxLayout(self.list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)

        self.enemy = QLabel("可能对位英雄：暂无")
        self.enemy.setObjectName("MutedText")
        list_layout.addWidget(self.enemy)

        self.inference = QLabel("敌方位置推断：暂无数据")
        self.inference.setObjectName("CoachGrades")
        self.inference.setWordWrap(True)
        list_layout.addWidget(self.inference)

        self.card_area = QScrollArea()
        self.card_area.setWidgetResizable(True)
        self.card_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.card_area.setStyleSheet("QScrollArea{border:none;background:transparent}")

        self.card_container = QWidget()
        self.card_grid = QGridLayout(self.card_container)
        self.card_grid.setContentsMargins(0, 0, 0, 0)
        self.card_grid.setHorizontalSpacing(10)
        self.card_grid.setVerticalSpacing(10)
        self.card_grid.setColumnStretch(0, 1)
        self.card_grid.setColumnStretch(1, 1)

        self.cards = [LanePickCard() for _ in range(10)]
        for index, card in enumerate(self.cards):
            card.clicked.connect(self.on_hero_click)
            self.card_grid.addWidget(card, index // 2, index % 2)

        self.card_area.setWidget(self.card_container)
        list_layout.addWidget(self.card_area, 1)

        self.empty = QLabel("暂无对线优势推荐：等待识别敌方对位英雄，或当前没有明显优势选择")
        self.empty.setObjectName("MutedText")
        self.empty.setWordWrap(True)
        list_layout.addWidget(self.empty)

        self.detail = HeroDetailPanel()
        self.detail.closed.connect(self._show_list)
        self.stack.addWidget(self.list_page)
        self.stack.addWidget(self.detail)
        self.stack.setCurrentWidget(self.list_page)

    def render(self, state: dict):
        self._state = state or {}
        recs = [
            rec for rec in state.get("lane_recommendations", [])
            if _is_positive_delta(rec.get("delta", 0))
        ][:10]
        self._recs = recs
        inferred_opponent = state.get("inferred_lane_opponent", "")
        enemy = inferred_opponent
        for rec in recs:
            enemy = rec.get("opponent", "") or enemy
        self.enemy.setText(f"可能对位英雄：{champion_display_name(enemy) or '暂无'}")
        self.inference.setText(self._format_inference(state.get("role_inference", {})))

        self.empty.setVisible(not recs)
        self.card_area.setVisible(bool(recs))
        for index, card in enumerate(self.cards):
            if index < len(recs):
                card.render(recs[index])
                card.show()
            else:
                card.hide()

    def on_hero_click(self, hero_name: str):
        recommendation = self._find_recommendation(hero_name)
        context = self._detail_builder.build(
            hero_name,
            current_state=self._state,
            recommendation=recommendation,
        )
        self.detail.render_detail(context)
        self.stack.setCurrentWidget(self.detail)

    def _show_list(self):
        self.stack.setCurrentWidget(self.list_page)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.stack.currentWidget() is self.detail:
            self.detail.hide_panel()
            return
        super().keyPressEvent(event)

    def _find_recommendation(self, hero_name: str) -> dict:
        target = str(hero_name or "").lower()
        for rec in self._recs:
            if str(rec.get("champion", "")).lower() == target:
                return rec
        for rec in self._state.get("recommendations", []) or []:
            if str(rec.get("champion", "")).lower() == target:
                return rec
        return {}

    def _format_inference(self, inference: dict) -> str:
        if not inference:
            return "敌方位置推断：暂无数据"

        blocks = ["敌方位置推断"]
        for champion, probabilities in inference.items():
            if not isinstance(probabilities, dict):
                continue
            sorted_roles = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
            if not sorted_roles:
                continue
            parts = []
            for index, (role, probability) in enumerate(sorted_roles[:3]):
                mark = "✔" if index == 0 else "⚠" if index == 1 else "·"
                role_label = ROLE_LABELS.get(role, role)
                parts.append(f"{mark}{role_label} {round(float(probability) * 100)}%")
            blocks.append(f"{champion_display_name(champion)}：{'  '.join(parts)}")
        return "\n".join(blocks)


def _is_number(value) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False


def _format_delta(value) -> str:
    try:
        return f"{float(value):+.1f}%"
    except Exception:
        return str(value)


def _is_positive_delta(value) -> bool:
    try:
        return float(value or 0) > 0
    except Exception:
        return False


def _format_games(value) -> str:
    try:
        games = int(float(value or 0))
    except Exception:
        return str(value)
    if games >= 10000:
        return f"{games / 10000:.1f}万"
    return str(games)

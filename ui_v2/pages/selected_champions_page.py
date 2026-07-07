from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from analysis.build_recommendation import BuildRecommendationEngine
from analysis.lolalytics_client import LolalyticsClient
from analysis.rune_recommendation import RuneRecommendationEngine
from utils.champion_assets import champion_icon_path, champion_key
from utils.champion_names import champion_display_name
from utils.game_terms_zh import item_zh, items_zh, rune_zh, runes_zh


ROLE_TO_LABEL = {
    "TOP": "上路",
    "JUNGLE": "打野",
    "MID": "中路",
    "MIDDLE": "中路",
    "ADC": "射手",
    "BOTTOM": "射手",
    "SUPPORT": "辅助",
    "UTILITY": "辅助",
}


class _LoadoutSignals(QObject):
    loaded = Signal(str, dict)


class SelectedChampionCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("HeroCard")
        self.setMinimumHeight(148)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(12)

        self.avatar = QLabel("")
        self.avatar.setFixedSize(56, 56)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setObjectName("HeroAvatar")
        root.addWidget(self.avatar)

        box = QVBoxLayout()
        box.setSpacing(6)
        self.title = QLabel("")
        self.title.setObjectName("HeroName")
        self.runes = QLabel("符文：等待加载")
        self.runes.setObjectName("HeroTags")
        self.runes.setWordWrap(True)
        self.core = QLabel("核心装：等待加载")
        self.core.setObjectName("HeroTags")
        self.core.setWordWrap(True)
        self.situational = QLabel("调整：等待加载")
        self.situational.setObjectName("MutedText")
        self.situational.setWordWrap(True)
        box.addWidget(self.title)
        box.addWidget(self.runes)
        box.addWidget(self.core)
        box.addWidget(self.situational)
        root.addLayout(box, 1)

    def render_base(self, champion: str, index: int, role: str):
        key = champion_key(champion)
        name = champion_display_name(key)
        self.title.setText(f"{index}. {name or key}　{ROLE_TO_LABEL.get(role, role or '未知位置')}")
        self._set_avatar(key, name)
        self.runes.setText("符文：加载中，不影响推荐页")
        self.core.setText("核心装：加载中")
        self.situational.setText("调整：根据敌方阵容计算中")

    def render_loadout(self, payload: dict):
        rune = payload.get("rune", {}) or {}
        build = payload.get("build", {}) or {}

        primary = rune_zh(rune.get("primary", ""))
        keystone = rune_zh(rune.get("keystone", ""))
        secondary = " / ".join(runes_zh(rune.get("secondary", []))) or "暂无"
        self.runes.setText(f"符文：{primary} / {keystone}　副系：{secondary}")

        core = (build.get("core_build", []) or [{}])[0]
        core_items = " → ".join(items_zh(core.get("items", []))) or "暂无"
        stats = []
        if core.get("winrate") is not None:
            stats.append(f"胜率 {core.get('winrate')}%")
        if core.get("games"):
            stats.append(f"样本 {core.get('games')}")
        self.core.setText("核心装：" + core_items + (f"（{' / '.join(stats)}）" if stats else ""))

        situational = build.get("situational", []) or []
        if situational:
            first = situational[0]
            items = " / ".join(items_zh(first.get("items", [])))
            self.situational.setText(f"调整：{items}\n原因：{first.get('reason', '')}")
        else:
            self.situational.setText("调整：暂无阵容适配建议")

    def render_error(self):
        self.runes.setText("符文：暂无在线数据")
        self.core.setText("核心装：暂无在线数据")
        self.situational.setText("调整：网络失败时仍可先按推荐页完成 BP")

    def _set_avatar(self, key: str, display_name: str):
        icon_path = champion_icon_path(key) or champion_icon_path(display_name)
        if icon_path:
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                self.avatar.setText("")
                self.avatar.setPixmap(
                    pixmap.scaled(self.avatar.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                )
                return
        self.avatar.clear()
        self.avatar.setText((display_name or key or "?")[:2])


class SelectedChampionsPage(QWidget):
    def __init__(self):
        super().__init__()
        self._signature = ""
        self._loading_signature = ""
        self._cards: dict[str, SelectedChampionCard] = {}
        self._signals = _LoadoutSignals()
        self._signals.loaded.connect(self._on_loaded)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("已选英雄")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        hint = QLabel("符文和出装放在这里后台加载，避免拖慢英雄推荐页；已选英雄即使从推荐列表过滤掉，也能在这里查看。")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.status = QLabel("等待识别己方已选英雄")
        self.status.setObjectName("CoachGrades")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{border:none;background:transparent}")
        self.container = QWidget()
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(10)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)

    def render(self, state: dict):
        ally = [champion_key(item) for item in (state.get("ally", []) or []) if champion_key(item)]
        enemy = [champion_key(item) for item in (state.get("enemy", []) or []) if champion_key(item)]
        role = str(state.get("role") or state.get("target_role") or "")
        signature = "|".join(ally) + "::" + "|".join(enemy) + "::" + role
        if signature == self._signature:
            return
        self._signature = signature
        self._render_cards(ally, role)
        if not ally:
            self.status.setText("等待识别己方已选英雄")
            return
        self.status.setText(f"已识别己方 {len(ally)} 个英雄，正在后台加载符文和出装...")
        self._start_loading(signature, ally, enemy, role)

    def _render_cards(self, ally: list[str], role: str):
        self._clear_layout()
        self._cards = {}
        for index, champion in enumerate(ally, start=1):
            card = SelectedChampionCard()
            card.render_base(champion, index, role)
            self._cards[champion] = card
            self.card_layout.addWidget(card)
        self.card_layout.addStretch()

    def _start_loading(self, signature: str, ally: list[str], enemy: list[str], role: str):
        if signature == self._loading_signature:
            return
        self._loading_signature = signature

        def worker():
            try:
                client = LolalyticsClient(patch="16.13")
                build_engine = BuildRecommendationEngine(client)
                rune_engine = RuneRecommendationEngine(client)
                for champion in ally:
                    payload = {
                        "rune": rune_engine.recommend(champion, role, enemy),
                        "build": build_engine.recommend(champion, role, enemy),
                    }
                    self._signals.loaded.emit(champion, payload)
            except Exception:
                for champion in ally:
                    self._signals.loaded.emit(champion, {"error": True})

        threading.Thread(target=worker, daemon=True).start()

    def _on_loaded(self, champion: str, payload: dict):
        card = self._cards.get(champion)
        if not card:
            return
        if payload.get("error"):
            card.render_error()
        else:
            card.render_loadout(payload)
        self.status.setText("符文和出装加载完成，可在本页慢慢查看。")

    def _clear_layout(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

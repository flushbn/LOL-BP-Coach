from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from analysis.hero_detail_context import HeroDetailContextBuilder
from ui_v2.components.hero_detail_panel import HeroDetailPanel
from ui_v2.components.hero_search_bar import HeroSearchBar
from ui_v2.widgets.hero_card import HeroCard
from utils.champion_names import champion_display_name


class RecommendPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self._state: dict = {}
        self._recs: list[dict] = []
        self._selected_index = -1
        self._detail_builder = HeroDetailContextBuilder()

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        title = QLabel("英雄推荐")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget{background:transparent;border:none;}")
        root.addWidget(self.stack, 1)

        self.list_page = QWidget()
        list_layout = QVBoxLayout(self.list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)

        self.search = HeroSearchBar()
        self.search.hero_selected.connect(self.on_hero_click)
        list_layout.addWidget(self.search)

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

        self.cards = [HeroCard() for _ in range(10)]
        for index, card in enumerate(self.cards):
            card.clicked.connect(self.on_hero_click)
            self.card_grid.addWidget(card, index // 2, index % 2)
        self.card_area.setWidget(self.card_container)
        list_layout.addWidget(self.card_area, 1)

        self.empty = QLabel("请选择英雄或搜索英雄")
        self.empty.setObjectName("MutedText")
        self.empty.setWordWrap(True)
        list_layout.addWidget(self.empty)

        self.detail = HeroDetailPanel()
        self.detail.closed.connect(self._restore_focus)
        self.stack.addWidget(self.list_page)
        self.stack.addWidget(self.detail)
        self.stack.setCurrentWidget(self.list_page)

    def render(self, state: dict):
        self._state = state or {}
        self._recs = self._state.get("recommendations", [])[:10]
        self.empty.setVisible(not self._recs)
        if not self._recs:
            recognition = self._state.get("recognition", {}) or {}
            if recognition:
                ally = self._state.get("ally", []) or []
                enemy = self._state.get("enemy", []) or []
                bans = self._state.get("bans", []) or []
                message = recognition.get("message", "等待识别")
                self.empty.setText(
                    f"{message}\n己方: {', '.join(ally) or '暂无'}\n敌方: {', '.join(enemy) or '暂无'}\nBan: {', '.join(bans) or '暂无'}"
                )
            else:
                self.empty.setText("请选择英雄或搜索英雄")

        for index, card in enumerate(self.cards):
            if index < len(self._recs):
                card.render(self._recs[index])
                card.show()
            else:
                card.hide()

    def on_hero_click(self, hero_name: str):
        recommendation = self._find_recommendation(hero_name)
        context = self._detail_builder.build(
            hero_name,
            current_state=self._state,
            recommendation=recommendation,
            include_online=False,
        )
        self._selected_index = self._index_of(hero_name)
        self.detail.render_detail(context)
        self.stack.setCurrentWidget(self.detail)
        self.empty.setVisible(False)

    def _restore_focus(self):
        self.stack.setCurrentWidget(self.list_page)
        self.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.detail.isVisible():
            self.detail.hide_panel()
            return
        if event.key() in (Qt.Key_Down, Qt.Key_Up) and self._recs:
            step = 1 if event.key() == Qt.Key_Down else -1
            if self._selected_index < 0:
                self._selected_index = 0
            else:
                self._selected_index = (self._selected_index + step) % len(self._recs)
            self.on_hero_click(self._recs[self._selected_index].get("champion", ""))
            return
        super().keyPressEvent(event)

    def _find_recommendation(self, hero_name: str) -> dict:
        target = str(hero_name or "").lower()
        for rec in self._recs:
            if str(rec.get("champion", "")).lower() == target:
                return rec
            if champion_display_name(rec.get("champion", "")).lower() == target:
                return rec
        return {}

    def _index_of(self, hero_name: str) -> int:
        target = str(hero_name or "").lower()
        for index, rec in enumerate(self._recs):
            if str(rec.get("champion", "")).lower() == target:
                return index
        return -1

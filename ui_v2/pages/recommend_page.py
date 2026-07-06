from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget

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
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        title = QLabel("英雄推荐")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        self.search = HeroSearchBar()
        self.search.hero_selected.connect(self.on_hero_click)
        root.addWidget(self.search)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.cards = [HeroCard() for _ in range(5)]
        for card in self.cards:
            card.clicked.connect(self.on_hero_click)
            left_layout.addWidget(card)

        self.empty = QLabel("请选择英雄或搜索英雄")
        self.empty.setObjectName("MutedText")
        self.empty.setWordWrap(True)
        left_layout.addWidget(self.empty)
        left_layout.addStretch()
        splitter.addWidget(left)

        self.detail = HeroDetailPanel()
        self.detail.hide()
        splitter.addWidget(self.detail)
        splitter.setSizes([520, 520])

    def render(self, state: dict):
        self._state = state or {}
        self._recs = self._state.get("recommendations", [])[:5]
        self.empty.setVisible(not self._recs)
        if not self._recs:
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
        )
        self._selected_index = self._index_of(hero_name)
        self.detail.render_detail(context)
        self.empty.setVisible(False)

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


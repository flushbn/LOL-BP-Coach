from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from analysis.patch_notes_engine import PatchNotesEngine
from utils.champion_assets import champion_icon_path
from utils.champion_names import champion_display_name


ROLE_LABELS = {
    "TOP": "上路",
    "JUNGLE": "打野",
    "MID": "中路",
    "ADC": "下路",
    "SUPPORT": "辅助",
}


class MetaStrengthPage(QWidget):
    def __init__(self):
        super().__init__()
        self._patch = ""
        self._role_grids: dict[str, QGridLayout] = {}
        self._unconventional_grids: dict[str, QGridLayout] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("版本强势英雄")
        title.setObjectName("PageTitle")
        title_box.addWidget(title)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("MutedText")
        title_box.addWidget(self.subtitle)
        header.addLayout(title_box, 1)
        refresh = QPushButton("刷新榜单")
        refresh.clicked.connect(self.reload)
        header.addWidget(refresh, 0, Qt.AlignTop)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)

        for role in ("TOP", "JUNGLE", "MID", "ADC", "SUPPORT"):
            heading = QLabel(ROLE_LABELS[role])
            heading.setStyleSheet("font-size:16px;color:#F9FAFB;font-weight:800;")
            content_layout.addWidget(heading)

            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(8)
            for column in range(4):
                grid.setColumnStretch(column, 1)
            content_layout.addLayout(grid)
            self._role_grids[role] = grid

            extra_heading = QLabel("非常规英雄（不作为主流推荐）")
            extra_heading.setStyleSheet("font-size:12px;color:#9CA3AF;font-weight:700;")
            content_layout.addWidget(extra_heading)
            extra_grid = QGridLayout()
            extra_grid.setContentsMargins(0, 0, 0, 0)
            extra_grid.setHorizontalSpacing(8)
            extra_grid.setVerticalSpacing(8)
            for column in range(4):
                extra_grid.setColumnStretch(column, 1)
            content_layout.addLayout(extra_grid)
            self._unconventional_grids[role] = extra_grid

        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self.reload()

    def render(self, state: dict):
        patch = str(state.get("patch") or state.get("current_patch") or "")
        if patch and patch != self._patch:
            self.reload()

    def reload(self):
        engine = PatchNotesEngine()
        self._patch = engine.patch
        summary = engine.get_patch_summary()
        riot_patch = summary.get("riot_patch") or self._patch
        self.subtitle.setText(
            f"来源：Lolalytics GLOBAL / Emerald+ 单排 · 主流分路英雄 · 数据 {self._patch} / Riot {riot_patch}"
        )
        strengths = engine.get_role_strengths()
        unconventional = engine.get_unconventional_role_strengths()
        for role, grid in self._role_grids.items():
            self._clear_grid(grid)
            for index, row in enumerate(strengths.get(role, [])):
                grid.addWidget(self._hero_row(row), index // 4, index % 4)
            extra_grid = self._unconventional_grids[role]
            self._clear_grid(extra_grid)
            for index, row in enumerate(unconventional.get(role, [])):
                extra_grid.addWidget(self._hero_row(row, unconventional=True), 0, index)

    @staticmethod
    def _clear_grid(grid: QGridLayout):
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    @staticmethod
    def _hero_row(row: dict, unconventional: bool = False) -> QFrame:
        champion = str(row.get("champion", ""))
        frame = QFrame()
        frame.setObjectName("StrengthHero")
        frame.setStyleSheet(
            "QFrame#StrengthHero {background:#172033;border:1px solid #334155;border-radius:8px;}"
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(8)

        avatar = QLabel()
        avatar.setFixedSize(44, 44)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "background:#334155;border-radius:6px;color:#F8FAFC;font-size:16px;font-weight:700;"
        )
        path = champion_icon_path(champion)
        if path:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                avatar.setPixmap(pixmap.scaled(44, 44, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            else:
                avatar.setText(champion[:1])
        else:
            avatar.setText(champion[:1])
        layout.addWidget(avatar)

        text = QVBoxLayout()
        text.setSpacing(2)
        name = QLabel(champion_display_name(champion))
        name.setStyleSheet("color:#F9FAFB;font-size:14px;font-weight:800;")
        name.setWordWrap(True)
        text.addWidget(name)
        winrate = QLabel(f'{float(row.get("winrate", 0)):.2f}% 胜率')
        color = "#9CA3AF" if unconventional else "#FACC15"
        winrate.setStyleSheet(f"color:{color};font-size:13px;font-weight:700;")
        text.addWidget(winrate)
        games = QLabel(f'{int(row.get("games", 0)):,} 场')
        games.setStyleSheet("color:#9CA3AF;font-size:11px;")
        text.addWidget(games)
        layout.addLayout(text, 1)
        return frame

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from utils.champion_names import champion_display_name


class PlayerPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("我的数据")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.summary = QLabel("暂无玩家数据")
        self.summary.setObjectName("CoachGrades")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["英雄", "场次", "胜率", "最近使用"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def render(self, state: dict):
        player = state.get("player") or state.get("player_stats") or {}
        summary = player.get("summary", {}) if isinstance(player, dict) else {}
        games = summary.get("games", 0)
        winrate = summary.get("winrate", 0)
        recent = summary.get("recent30_wr", "")
        if games:
            text = f"总场次 {games}　总胜率 {winrate}%"
            if recent != "":
                text += f"　最近30场 {recent}%"
            self.summary.setText(text)
        else:
            self.summary.setText("暂无玩家数据")

        heroes = []
        if isinstance(player, dict):
            heroes = player.get("heroes") or player.get("hero_stats") or []
        self.table.setRowCount(len(heroes))
        for row, hero in enumerate(heroes):
            values = [
                champion_display_name(hero.get("champion", hero.get("hero", ""))),
                hero.get("games", ""),
                hero.get("winrate", ""),
                hero.get("last_played", ""),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()


"""可排序、可搜索、可筛选的历史记录表格。"""

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from utils.champion_names import champion_display_name


class 历史记录TableWidget(QWidget):
    HEADERS = ["时间", "英雄", "位置", "结果"]

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search + filter bar
        bar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索英雄...")
        self._search.textChanged.connect(self._apply_filters)
        bar.addWidget(self._search)
        self._filter_win = QPushButton("胜利")
        self._filter_win.setCheckable(True)
        self._filter_win.clicked.connect(self._apply_filters)
        bar.addWidget(self._filter_win)
        self._filter_lose = QPushButton("失败")
        self._filter_lose.setCheckable(True)
        self._filter_lose.clicked.connect(self._apply_filters)
        bar.addWidget(self._filter_lose)
        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.clicked.connect(self._on_refresh)
        bar.addWidget(self._refresh_btn)
        bar.addStretch()
        layout.addLayout(bar)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(len(self.HEADERS))
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        layout.addWidget(self._table)

        # Footer stats
        self._footer = QLabel("无数据")
        layout.addWidget(self._footer)

        self._all_rows = []
        self._refresh_callback = None

    def set_data(self, rows):
        self._all_rows = list(rows)
        self._apply_filters()

    def set_refresh_callback(self, cb):
        self._refresh_callback = cb

    def _apply_filters(self):
        search = self._search.text().strip().lower()
        filter_win = self._filter_win.isChecked()
        filter_lose = self._filter_lose.isChecked()
        filtered = []
        for r in self._all_rows:
            hero = r.get('hero', '')
            result = r.get('result', '')
            if search and search not in hero.lower() and search not in champion_display_name(hero).lower():
                continue
            if filter_win and result != 'WIN':
                continue
            if filter_lose and result != 'LOSE':
                continue
            filtered.append(r)
        self._populate_table(filtered)
        self._update_footer(filtered)
    def _populate_table(self, rows):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            ts = row.get('timestamp', 0)
            time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
            hero = row.get('hero', '')
            pos = row.get('position', '')
            result = row.get('result', '')
            items = [QTableWidgetItem(time_str), QTableWidgetItem(champion_display_name(hero)),
                     QTableWidgetItem(pos), QTableWidgetItem(result)]
            for c, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter)
                if c == 3:
                    color = '#4caf50' if result == 'WIN' else '#f44336'
                    item.setForeground(QColor(color))
                self._table.setItem(r, c, item)
        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()

    def _update_footer(self, rows):
        total = len(rows)
        wins = sum(1 for r in rows if r.get('result') == 'WIN')
        wr = round(wins / total * 100, 1) if total else 0
        self._footer.setText(f'总场: {total}  |  胜场: {wins}  |  胜率: {wr}%')

    def _on_refresh(self):
        if self._refresh_callback:
            self._refresh_callback()


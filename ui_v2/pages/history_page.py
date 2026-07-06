"""历史记录 页面 - 对局会请记录。"""

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..widgets.history_table_widget import 历史记录TableWidget

MATCH_SESSIONS_PATH = Path(__file__).resolve().parent.parent.parent / 'data' / 'match_sessions.json'


class 历史记录Page(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        title = QLabel('<h1 style=color:#f5c518;margin:0>历史记录</h1>')
        layout.addWidget(title)
        self._table = 历史记录TableWidget()
        self._table.set_refresh_callback(self._load_data)
        layout.addWidget(self._table)
        self._load_data()

    def _load_data(self):
        try:
            if not MATCH_SESSIONS_PATH.exists():
                self._table.set_data([])
                return
            raw = MATCH_SESSIONS_PATH.read_text(encoding='utf-8')
            data = json.loads(raw) if raw.strip() else []
            if not isinstance(data, list):
                data = []
            data.sort(key=lambda r: r.get('timestamp', 0), reverse=True)
            self._table.set_data(data)
        except Exception:
            self._table.set_data([])


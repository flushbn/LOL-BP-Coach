from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCompleter, QLineEdit, QWidget

from utils.champion_assets import champion_key
from utils.champion_names import champion_display_name


ROOT = Path(__file__).resolve().parent.parent.parent


class HeroSearchBar(QLineEdit):
    hero_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setPlaceholderText("搜索英雄：输入中文名或英文名，回车查看详情")
        self._display_to_key = self._build_index()
        completer = QCompleter(sorted(self._display_to_key.keys()), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.activated.connect(self._on_complete)
        self.setCompleter(completer)
        self.returnPressed.connect(self._on_return)

    def _build_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        path = ROOT / "champion_data.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            data = {}

        for key in data.keys():
            cn = champion_display_name(key)
            index[key] = key
            index[cn] = key
            index[f"{cn} ({key})"] = key

        dragon_tail = ROOT / "data" / "zh_CN" / "champion.json"
        try:
            payload = json.loads(dragon_tail.read_text(encoding="utf-8")) if dragon_tail.exists() else {}
            for key, info in payload.get("data", {}).items():
                if key in data:
                    for alias in (info.get("name", ""), info.get("title", "")):
                        if alias:
                            index[str(alias)] = key
        except Exception:
            pass
        return index

    def _on_complete(self, text: str):
        key = self._display_to_key.get(text) or champion_key(text)
        if key:
            self.hero_selected.emit(key)

    def _on_return(self):
        text = self.text().strip()
        if not text:
            return
        key = self._display_to_key.get(text) or champion_key(text)
        self.hero_selected.emit(key)


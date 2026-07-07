from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget


class TacticalAdvicePage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("战术建议")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        hint = QLabel("这里只显示最终决策建议；路线细节和节奏计划已拆到左侧单独页面。")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.advice = QTextEdit()
        self.advice.setReadOnly(True)
        self.advice.setPlaceholderText("暂无战术建议")
        self.advice.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(self.advice, 1)

    def render(self, state: dict):
        coach = state.get("coach", {}) or {}
        advice = coach.get("advice", "")
        lane_summary = (coach.get("lane_state", {}) or {}).get("summary", []) or []
        plan_summary = (coach.get("macro_plan", {}) or {}).get("summary", []) or []

        lines: list[str] = []
        if isinstance(advice, list):
            lines.extend(str(item) for item in advice if item)
        elif advice:
            lines.extend(str(advice).splitlines())
        lines.extend(str(item) for item in lane_summary if item)
        lines.extend(str(item) for item in plan_summary if item)

        text = "\n".join(f"✓ {item}" for item in dict.fromkeys(lines))
        self._set_text_preserving_scroll(text or "暂无战术建议")

    def _set_text_preserving_scroll(self, text: str):
        if self.advice.toPlainText() == text:
            return
        bar = self.advice.verticalScrollBar()
        old_value = bar.value()
        was_at_bottom = old_value >= bar.maximum() - 2
        self.advice.setPlainText(text)
        if was_at_bottom:
            self.advice.verticalScrollBar().setValue(self.advice.verticalScrollBar().maximum())
        else:
            self.advice.verticalScrollBar().setValue(min(old_value, self.advice.verticalScrollBar().maximum()))

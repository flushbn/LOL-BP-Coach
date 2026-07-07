from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QTextEdit, QVBoxLayout, QWidget


DIMENSIONS = [
    ("frontline", "前排"),
    ("engage", "开团"),
    ("protect", "保护"),
    ("burst", "爆发"),
    ("dps", "持续输出"),
    ("late", "后期"),
]

COMPARISON_LABELS = {
    "frontline": "前排",
    "engage": "开团",
    "peel": "保护",
    "protect": "保护",
    "burst": "爆发",
    "dps": "持续输出",
    "late": "后期",
    "lategame": "后期",
}

COMPARISON_VALUES = {
    "ally_big_advantage": "己方大优",
    "ally_advantage": "己方优势",
    "enemy_big_advantage": "敌方大优",
    "enemy_advantage": "敌方优势",
    "even": "均势",
}


class CoachPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("战术分析")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.grades = QLabel("等待阵容分析...")
        self.grades.setWordWrap(True)
        self.grades.setObjectName("CoachGrades")
        self.grades.setMinimumHeight(150)
        layout.addWidget(self.grades)

        advice_group = self._build_group("战术建议")
        self.advice = self._build_scroll_text("暂无战术建议")
        advice_group.layout().addWidget(self.advice)
        layout.addWidget(advice_group, 1)

    def render(self, state: dict):
        coach = state.get("coach", {}) or {}
        self._render_grades(coach)
        self._render_advice(coach)

    def _build_group(self, title: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setStyleSheet(
            """
            QGroupBox {
                color: #F9FAFB;
                font-weight: 800;
                border: 1px solid #233044;
                border-radius: 14px;
                margin-top: 12px;
                padding-top: 12px;
                background: #0F172A;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                background: #0F172A;
            }
            """
        )
        box = QVBoxLayout(group)
        box.setContentsMargins(10, 12, 10, 10)
        box.setSpacing(8)
        return group

    def _build_scroll_text(self, placeholder: str) -> QTextEdit:
        widget = QTextEdit()
        widget.setReadOnly(True)
        widget.setPlaceholderText(placeholder)
        widget.setLineWrapMode(QTextEdit.WidgetWidth)
        return widget

    def _render_grades(self, coach: dict):
        lines: list[str] = []
        for side_key, side_name in (("ally", "己方"), ("enemy", "敌方")):
            side = coach.get(side_key, {}) or {}
            parts = [f"{label} {side.get(key)}" for key, label in DIMENSIONS if side.get(key)]
            if parts:
                lines.append(f"<b>{side_name}</b>　" + "　".join(parts))

        comparison = coach.get("comparison", {}) or {}
        if comparison:
            parts = []
            for key, value in comparison.items():
                label = COMPARISON_LABELS.get(str(key), str(key))
                text = COMPARISON_VALUES.get(str(value), str(value))
                parts.append(f"{label}：{text}")
            if parts:
                lines.append("<b>双方对比</b>　" + "　".join(parts))

        self.grades.setText("<br>".join(lines) if lines else "等待阵容分析...")

    def _render_advice(self, coach: dict):
        advice = coach.get("advice", "")
        lane_summary = (coach.get("lane_state", {}) or {}).get("summary", []) or []
        plan_summary = (coach.get("macro_plan", {}) or {}).get("summary", []) or []

        advice_lines: list[str] = []
        if isinstance(advice, list):
            advice_lines.extend(str(item) for item in advice if item)
        elif advice:
            advice_lines.extend(str(advice).splitlines())
        advice_lines.extend(str(item) for item in lane_summary if item)
        advice_lines.extend(str(item) for item in plan_summary if item)

        self._set_text_preserving_scroll(self.advice, "\n".join(dict.fromkeys(advice_lines)))

    @staticmethod
    def _set_text_preserving_scroll(widget: QTextEdit, text: str):
        if widget.toPlainText() == text:
            return
        bar = widget.verticalScrollBar()
        old_value = bar.value()
        was_at_bottom = old_value >= bar.maximum() - 2
        widget.setPlainText(text)
        if was_at_bottom:
            widget.verticalScrollBar().setValue(widget.verticalScrollBar().maximum())
        else:
            widget.verticalScrollBar().setValue(min(old_value, widget.verticalScrollBar().maximum()))

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QScrollArea, QTextEdit, QVBoxLayout, QWidget


DIMENSIONS = [
    (("frontline",), "前排"),
    (("engage",), "开团"),
    (("peel", "protect"), "保护"),
    (("burst",), "爆发"),
    (("dps",), "持续输出"),
    (("late", "lategame"), "后期"),
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

        subtitle = QLabel("整合展示阵容能力、双方差异和最终战术建议。路线与节奏请看“战术·路线节奏”。")
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent}")
        layout.addWidget(scroll, 1)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        scroll.setWidget(content)

        ally_group = self._build_group("己方阵容")
        self.ally_grades = self._build_label("等待己方阵容分析...")
        ally_group.layout().addWidget(self.ally_grades)
        content_layout.addWidget(ally_group)

        enemy_group = self._build_group("敌方阵容")
        self.enemy_grades = self._build_label("等待敌方阵容分析...")
        enemy_group.layout().addWidget(self.enemy_grades)
        content_layout.addWidget(enemy_group)

        comparison_group = self._build_group("双方对比")
        self.comparison = self._build_label("等待双方对比...")
        comparison_group.layout().addWidget(self.comparison)
        content_layout.addWidget(comparison_group)

        advice_group = self._build_group("战术建议")
        self.advice = self._build_scroll_text("暂无战术建议")
        advice_group.layout().addWidget(self.advice)
        content_layout.addWidget(advice_group, 1)

    def render(self, state: dict):
        coach = state.get("coach", {}) or {}
        self._render_side(self.ally_grades, coach.get("ally", {}) or {}, "等待己方阵容分析...")
        self._render_side(self.enemy_grades, coach.get("enemy", {}) or {}, "等待敌方阵容分析...")
        self._render_comparison(coach.get("comparison", {}) or {})
        self._render_advice_brief(coach)

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

    def _build_label(self, placeholder: str) -> QLabel:
        label = QLabel(placeholder)
        label.setObjectName("CoachGrades")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label

    def _build_scroll_text(self, placeholder: str) -> QTextEdit:
        widget = QTextEdit()
        widget.setReadOnly(True)
        widget.setPlaceholderText(placeholder)
        widget.setLineWrapMode(QTextEdit.WidgetWidth)
        widget.setMinimumHeight(150)
        return widget

    def _render_side(self, label: QLabel, side: dict, fallback: str):
        parts = []
        for keys, name in DIMENSIONS:
            value = _first_value(side, keys)
            if value:
                parts.append(f"{name}：{value}")
        label.setText("　".join(parts) if parts else fallback)

    def _render_comparison(self, comparison: dict):
        if not comparison:
            self.comparison.setText("等待双方对比...")
            return

        lines = []
        for key, value in comparison.items():
            label = COMPARISON_LABELS.get(str(key), str(key))
            text = COMPARISON_VALUES.get(str(value), str(value))
            lines.append(f"{label}：{text}")
        self.comparison.setText("　".join(lines) if lines else "等待双方对比...")

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

        text = "\n".join(f"✓ {item}" for item in dict.fromkeys(advice_lines))
        self._set_text_preserving_scroll(self.advice, text or "暂无战术建议")

    def _render_advice_brief(self, coach: dict):
        raw = coach.get("advice", "")
        lines: list[str] = []
        if isinstance(raw, list):
            lines.extend(str(item) for item in raw if item)
        elif raw:
            lines.extend(str(raw).splitlines())
        lines.extend(str(item) for item in (coach.get("lane_state", {}) or {}).get("summary", []) if item)
        lines.extend(str(item) for item in (coach.get("macro_plan", {}) or {}).get("summary", []) if item)

        selected: list[str] = []
        for line in dict.fromkeys(lines):
            text = " ".join(line.split())
            if not text:
                continue
            selected.append(text[:45].rstrip("，。；;、 ") + ("..." if len(text) > 45 else ""))
            if len(selected) >= 3:
                break
        self._set_text_preserving_scroll(self.advice, "\n".join(f"✓ {item}" for item in selected) or "暂无战术建议")

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


def _first_value(payload: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return ""

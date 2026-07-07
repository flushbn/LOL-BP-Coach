from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QSplitter, QTextEdit, QVBoxLayout, QWidget


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
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("战术分析")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.grades = QLabel("等待阵容分析...")
        self.grades.setWordWrap(True)
        self.grades.setObjectName("CoachGrades")
        self.grades.setMaximumHeight(120)
        layout.addWidget(self.grades)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        lane_group = self._build_group("路线强弱分析")
        self.lane_state = self._build_scroll_text("暂无路线强弱分析")
        lane_group.layout().addWidget(self.lane_state)
        splitter.addWidget(lane_group)

        advice_group = self._build_group("战术建议")
        self.advice = self._build_scroll_text("暂无战术建议")
        advice_group.layout().addWidget(self.advice)
        splitter.addWidget(advice_group)
        splitter.setSizes([430, 210])

    def render(self, state: dict):
        coach = state.get("coach", {}) or {}
        self._render_grades(coach)
        self._render_lane_state(coach)
        self._render_advice(coach)

    def _build_group(self, title: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setStyleSheet(
            """
            QGroupBox {
                color: #F2C94C;
                font-weight: 700;
                border: 1px solid #252A33;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                background: #111318;
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

    def _render_lane_state(self, coach: dict):
        lane_state = coach.get("lane_state", {}) or {}
        lanes = lane_state.get("lanes", []) or []
        if not lanes:
            self._set_text_preserving_scroll(self.lane_state, "暂无路线强弱分析")
            return

        chunks: list[str] = []
        for lane in lanes:
            ally = lane.get("ally_display") or lane.get("ally") or "未知"
            enemy = lane.get("enemy_display") or lane.get("enemy") or "未知"
            header = (
                f"{lane.get('label', lane.get('lane', '路线'))} "
                f"{lane.get('state', '未知')}｜击杀{lane.get('kill_potential', '-')}"
                f"｜防守{lane.get('defense_value', '-')}｜{lane.get('priority', '-')}"
            )
            chunks.append(
                "\n".join(
                    [
                        header,
                        f"我方 {ally}  vs  敌方 {enemy}",
                        f"建议：{lane.get('jungle_action', lane.get('advice', ''))}",
                        f"原因：{lane.get('reason', '')}",
                    ]
                )
            )

        self._set_text_preserving_scroll(self.lane_state, "\n\n".join(chunks))

    def _render_advice(self, coach: dict):
        advice = coach.get("advice", "")
        lane_summary = (coach.get("lane_state", {}) or {}).get("summary", []) or []

        advice_lines: list[str] = []
        if isinstance(advice, list):
            advice_lines.extend(str(item) for item in advice if item)
        elif advice:
            advice_lines.extend(str(advice).splitlines())
        advice_lines.extend(str(item) for item in lane_summary if item)

        self._set_text_preserving_scroll(self.advice, "\n".join(advice_lines))

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

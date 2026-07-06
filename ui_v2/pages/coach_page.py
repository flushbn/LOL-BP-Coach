from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget


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
        layout.addWidget(self.grades)

        self.advice = QTextEdit()
        self.advice.setReadOnly(True)
        self.advice.setPlaceholderText("暂无战术建议")
        layout.addWidget(self.advice, 1)

    def render(self, state: dict):
        coach = state.get("coach", {}) or {}
        dims = [
            ("frontline", "前排"),
            ("engage", "开团"),
            ("protect", "保护"),
            ("burst", "爆发"),
            ("dps", "持续输出"),
            ("late", "后期"),
        ]

        lines: list[str] = []
        for side_key, side_name in (("ally", "己方"), ("enemy", "敌方")):
            side = coach.get(side_key, {})
            parts = [f"{label} {side.get(key)}" for key, label in dims if side.get(key)]
            if parts:
                lines.append(f"<b>{side_name}</b>　" + "　".join(parts))

        comparison = coach.get("comparison", {})
        if comparison:
            diff = "　".join(f"{key}: {value}" for key, value in comparison.items())
            lines.append(f"<b>对比</b>　{diff}")

        self.grades.setText("<br>".join(lines) if lines else "等待阵容分析...")
        advice = coach.get("advice", "")
        if isinstance(advice, list):
            advice = "\n".join(str(item) for item in advice)
        self.advice.setPlainText(str(advice or ""))


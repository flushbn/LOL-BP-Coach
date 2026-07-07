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

        lane_title = QLabel("路线强弱分析")
        lane_title.setObjectName("SectionTitle")
        layout.addWidget(lane_title)

        self.lane_state = QTextEdit()
        self.lane_state.setReadOnly(True)
        self.lane_state.setPlaceholderText("暂无路线强弱分析")
        layout.addWidget(self.lane_state, 2)

        advice_title = QLabel("战术建议")
        advice_title.setObjectName("SectionTitle")
        layout.addWidget(advice_title)

        self.advice = QTextEdit()
        self.advice.setReadOnly(True)
        self.advice.setPlaceholderText("暂无战术建议")
        layout.addWidget(self.advice, 1)

    def render(self, state: dict):
        coach = state.get("coach", {}) or {}
        self._render_grades(coach)
        self._render_lane_state(coach)
        self._render_advice(coach)

    def _render_grades(self, coach: dict):
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
            side = coach.get(side_key, {}) or {}
            parts = [f"{label} {side.get(key)}" for key, label in dims if side.get(key)]
            if parts:
                lines.append(f"<b>{side_name}</b>　" + "　".join(parts))

        comparison = coach.get("comparison", {}) or {}
        if comparison:
            diff = "　".join(f"{key}: {value}" for key, value in comparison.items())
            lines.append(f"<b>双方对比</b>　{diff}")

        self.grades.setText("<br>".join(lines) if lines else "等待阵容分析...")

    def _render_lane_state(self, coach: dict):
        lane_state = coach.get("lane_state", {}) or {}
        lanes = lane_state.get("lanes", []) or []
        if not lanes:
            self.lane_state.setPlainText("暂无路线强弱分析")
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

        self.lane_state.setPlainText("\n\n".join(chunks))

    def _render_advice(self, coach: dict):
        advice = coach.get("advice", "")
        lane_summary = (coach.get("lane_state", {}) or {}).get("summary", []) or []

        advice_lines: list[str] = []
        if isinstance(advice, list):
            advice_lines.extend(str(item) for item in advice if item)
        elif advice:
            advice_lines.extend(str(advice).splitlines())
        advice_lines.extend(str(item) for item in lane_summary if item)

        self.advice.setPlainText("\n".join(advice_lines))

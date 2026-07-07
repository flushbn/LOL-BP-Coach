from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QSplitter, QTextEdit, QVBoxLayout, QWidget


class MacroPage(QWidget):
    def __init__(self, mode: str = "all"):
        super().__init__()
        self.mode = mode
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title_text = {
            "lane": "路线强弱",
            "plan": "节奏计划",
        }.get(mode, "路线节奏")
        title = QLabel(title_text)
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        hint_text = {
            "lane": "只看三路线权、击杀潜力、防守价值和打野处理建议。",
            "plan": "只看前中期路线、资源优先级和风险提醒。",
        }.get(mode, "重点看哪路线优、哪路要保、打野前中期怎么走。")
        hint = QLabel(hint_text)
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        lane_group = self._build_group("路线强弱分析")
        self.lane_state = self._build_scroll_text("暂无路线强弱分析")
        lane_group.layout().addWidget(self.lane_state)
        if mode in ("all", "lane"):
            splitter.addWidget(lane_group)

        plan_group = self._build_group("节奏计划")
        self.macro_plan = self._build_scroll_text("暂无节奏计划")
        plan_group.layout().addWidget(self.macro_plan)
        if mode in ("all", "plan"):
            splitter.addWidget(plan_group)
        splitter.setSizes([360, 300])

    def render(self, state: dict):
        coach = state.get("coach", {}) or {}
        if self.mode in ("all", "lane"):
            self._render_lane_state(coach)
        if self.mode in ("all", "plan"):
            self._render_macro_plan(coach)

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

    def _render_macro_plan(self, coach: dict):
        plan = coach.get("macro_plan", {}) or {}
        if not plan:
            self._set_text_preserving_scroll(self.macro_plan, "暂无节奏计划")
            return

        blocks: list[str] = []
        if plan.get("summary"):
            blocks.append("核心思路\n" + "\n".join(f"✓ {item}" for item in plan.get("summary", [])))

        overview = []
        if plan.get("primary_side"):
            overview.append(f"主攻半区：{plan.get('primary_side')}")
        if plan.get("primary_lane"):
            overview.append(f"主节奏路线：{plan.get('primary_lane')}")
        if plan.get("jungle_path"):
            overview.append(f"打野路线：{plan.get('jungle_path')}")
        if overview:
            blocks.append("节奏概览\n" + "\n".join(overview))

        sections = [
            ("前5分钟", plan.get("first_5_min", [])),
            ("5-14分钟", plan.get("minute_5_14", [])),
            ("资源优先级", plan.get("objectives", [])),
            ("风险提醒", plan.get("risk_alerts", [])),
        ]
        for title, items in sections:
            if items:
                blocks.append(title + "\n" + "\n".join(f"• {item}" for item in items))

        self._set_text_preserving_scroll(self.macro_plan, "\n\n".join(blocks) or "暂无节奏计划")

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

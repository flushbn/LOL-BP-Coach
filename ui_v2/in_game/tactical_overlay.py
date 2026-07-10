from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui_v2.state_reader import read_state
from utils.champion_names import champion_display_name
from utils.window_capture_exclusion import exclude_window_from_capture


ROLE_LABELS = {
    "TOP": "上路",
    "JUNGLE": "打野",
    "MID": "中路",
    "ADC": "射手",
    "SUPPORT": "辅助",
}


OVERLAY_STYLE = """
QWidget {
    background: #080B14;
    color: #E5E7EB;
    font-family: Microsoft YaHei, Segoe UI, Arial;
    font-size: 13px;
}
QFrame#Root {
    background: rgba(12, 18, 33, 238);
    border: 1px solid #31415E;
    border-radius: 14px;
}
QFrame#TitleBar {
    background: #111827;
    border: 1px solid #263244;
    border-radius: 12px;
}
QLabel#Title {
    color: #FBBF24;
    font-size: 16px;
    font-weight: 800;
}
QLabel#Muted {
    color: #94A3B8;
}
QLabel#SectionTitle {
    color: #93C5FD;
    font-size: 14px;
    font-weight: 800;
}
QLabel#Card {
    background: #111827;
    border: 1px solid #263244;
    border-radius: 10px;
    padding: 8px;
    line-height: 150%;
}
QLabel#AlertCard {
    background: #1E1B12;
    border: 1px solid #854D0E;
    border-radius: 10px;
    color: #FDE68A;
    padding: 8px;
}
QPushButton {
    background: #1F2937;
    color: #F8FAFC;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 5px 9px;
    font-weight: 700;
}
QPushButton:hover {
    background: #334155;
}
QPushButton#PrimaryButton {
    background: #2563EB;
    border-color: #2563EB;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: #0B1020;
    width: 8px;
}
QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _join_lines(items: list[str], empty: str = "暂无") -> str:
    valid = [item for item in items if item]
    return "\n".join(valid) if valid else empty


class InGameTacticalOverlay(QWidget):
    """Safe in-game tactical card.

    This window only renders already-generated `data/live_state.json` content.
    It does not read game memory, call the recommendation engine, or automate input.
    """

    DEFAULT_W = 360
    DEFAULT_H = 520
    COLLAPSED_W = 210
    COLLAPSED_H = 96

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL BP Coach 局内战术")
        self.resize(self.DEFAULT_W, self.DEFAULT_H)
        self.setMinimumSize(260, 180)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setStyleSheet(OVERLAY_STYLE)
        self.setWindowOpacity(0.92)

        self._drag_pos = None
        self._paused = False
        self._collapsed = False
        self._last_state: dict[str, Any] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        root = QFrame()
        root.setObjectName("Root")
        outer.addWidget(root)

        self._layout = QVBoxLayout(root)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(8)

        self._build_title_bar()
        self._build_scroll_content()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.poll_state)
        self._timer.start(500)

        self.poll_state()
        QTimer.singleShot(300, self.enable_capture_exclusion)

    def _build_title_bar(self):
        title_bar = QFrame()
        title_bar.setObjectName("TitleBar")
        row = QHBoxLayout(title_bar)
        row.setContentsMargins(10, 7, 8, 7)
        row.setSpacing(6)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("局内战术卡")
        title.setObjectName("Title")
        self.status_label = QLabel("等待 BP 数据")
        self.status_label.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(self.status_label)
        row.addLayout(title_box, 1)

        self.pause_button = QPushButton("暂停")
        self.pause_button.clicked.connect(self.toggle_pause)
        row.addWidget(self.pause_button)

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(lambda: self.poll_state(force=True))
        row.addWidget(refresh_button)

        self.collapse_button = QPushButton("—")
        self.collapse_button.setFixedWidth(30)
        self.collapse_button.clicked.connect(self.toggle_collapse)
        row.addWidget(self.collapse_button)

        close_button = QPushButton("×")
        close_button.setFixedWidth(30)
        close_button.clicked.connect(self.close)
        row.addWidget(close_button)

        self._layout.addWidget(title_bar)

    def _build_scroll_content(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)

        self.draft_label = self._card()
        self.key_plan_label = self._card()
        self.lane_label = self._card()
        self.team_label = self._card()
        self.advice_label = self._card(alert=True)

        self.content_layout.addWidget(self._section("阵容快照"))
        self.content_layout.addWidget(self.draft_label)
        self.content_layout.addWidget(self._section("核心节奏"))
        self.content_layout.addWidget(self.key_plan_label)
        self.content_layout.addWidget(self._section("路线强弱"))
        self.content_layout.addWidget(self.lane_label)
        self.content_layout.addWidget(self._section("阵容对比"))
        self.content_layout.addWidget(self.team_label)
        self.content_layout.addWidget(self._section("战术建议"))
        self.content_layout.addWidget(self.advice_label)
        self.content_layout.addStretch()

        self.scroll.setWidget(self.content)
        self._layout.addWidget(self.scroll, 1)

    def _section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    def _card(self, alert: bool = False) -> QLabel:
        label = QLabel("暂无数据")
        label.setObjectName("AlertCard" if alert else "Card")
        label.setWordWrap(True)
        label.setTextFormat(Qt.PlainText)
        return label

    def enable_capture_exclusion(self):
        exclude_window_from_capture(int(self.winId()))

    def toggle_pause(self):
        self._paused = not self._paused
        self.pause_button.setText("继续" if self._paused else "暂停")
        if self._paused:
            self.status_label.setText("已暂停刷新 / 当前战术已定格")
        else:
            self.poll_state(force=True)

    def toggle_collapse(self):
        self._collapsed = not self._collapsed
        self.scroll.setVisible(not self._collapsed)
        self.collapse_button.setText("+" if self._collapsed else "—")
        if self._collapsed:
            self.resize(self.COLLAPSED_W, self.COLLAPSED_H)
            self.setMinimumSize(self.COLLAPSED_W, self.COLLAPSED_H)
        else:
            self.setMinimumSize(260, 180)
            self.resize(self.DEFAULT_W, self.DEFAULT_H)

    def poll_state(self, force: bool = False):
        if self._paused and not force:
            return
        state = read_state()
        self._last_state = state
        self.render(state)

    def render(self, state: dict[str, Any]):
        timestamp = int(state.get("timestamp") or 0)
        role = ROLE_LABELS.get(state.get("role") or state.get("target_role") or "", "未选择")
        if timestamp:
            updated = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
            self.status_label.setText(f"● 已连接  位置：{role}  更新：{updated}")
        else:
            self.status_label.setText("等待 BP 数据")

        self.draft_label.setText(self._format_draft(state))
        self.key_plan_label.setText(self._format_key_plan(state))
        self.lane_label.setText(self._format_lanes(state))
        self.team_label.setText(self._format_team_comparison(state))
        self.advice_label.setText(self._format_advice(state))

    def _format_draft(self, state: dict[str, Any]) -> str:
        ally = [champion_display_name(item) for item in _safe_list(state.get("ally"))]
        enemy = [champion_display_name(item) for item in _safe_list(state.get("enemy"))]
        role = ROLE_LABELS.get(state.get("role") or state.get("target_role") or "", "未选择")
        return "\n".join(
            [
                f"我的位置：{role}",
                f"己方：{', '.join(ally) if ally else '暂无'}",
                f"敌方：{', '.join(enemy) if enemy else '暂无'}",
            ]
        )

    def _format_key_plan(self, state: dict[str, Any]) -> str:
        coach = _safe_dict(state.get("coach"))
        macro = _safe_dict(coach.get("macro_plan"))
        if not macro:
            return "暂无路线节奏数据，请先完成 BP 识别或载入演示阵容。"
        lines = []
        primary_side = macro.get("primary_side") or "未判断"
        primary_lane = macro.get("primary_lane") or "未判断"
        lines.append(f"主节奏：{primary_side} / {primary_lane}")
        summary = _safe_list(macro.get("summary"))[:3]
        lines.extend([f"✓ {item}" for item in summary])
        first = _safe_list(macro.get("first_5_min"))[:2]
        if first:
            lines.append("前5分钟：")
            lines.extend([f"· {item}" for item in first])
        mid = _safe_list(macro.get("minute_5_14"))[:2]
        if mid:
            lines.append("5-14分钟：")
            lines.extend([f"· {item}" for item in mid])
        return _join_lines(lines)

    def _format_lanes(self, state: dict[str, Any]) -> str:
        coach = _safe_dict(state.get("coach"))
        lane_state = _safe_dict(coach.get("lane_state"))
        lanes = _safe_list(lane_state.get("lanes"))
        if not lanes:
            return "暂无路线强弱数据。"
        lines = []
        for lane in lanes[:5]:
            if not isinstance(lane, dict):
                continue
            label = lane.get("label") or lane.get("lane") or "路线"
            ally = lane.get("ally_display") or champion_display_name(lane.get("ally", ""))
            enemy = lane.get("enemy_display") or champion_display_name(lane.get("enemy", ""))
            state_text = lane.get("state") or "未知"
            priority = lane.get("priority") or "观察"
            action = lane.get("jungle_action") or lane.get("advice") or ""
            lines.append(f"{label}：{ally} vs {enemy}｜{state_text}｜{priority}")
            if action:
                lines.append(f"  → {action}")
        return _join_lines(lines)

    def _format_team_comparison(self, state: dict[str, Any]) -> str:
        coach = _safe_dict(state.get("coach"))
        ally = _safe_dict(coach.get("ally"))
        enemy = _safe_dict(coach.get("enemy"))
        comparison = _safe_dict(coach.get("comparison"))
        if not ally and not enemy:
            return "暂无阵容分析。"
        dimensions = [
            ("frontline", "前排"),
            ("engage", "开团"),
            ("protect", "保护"),
            ("peel", "保护"),
            ("burst", "爆发"),
            ("dps", "持续输出"),
            ("late", "后期"),
            ("lategame", "后期"),
        ]
        seen = set()
        lines = []
        for key, label in dimensions:
            if label in seen:
                continue
            seen.add(label)
            ally_grade = ally.get(key) or "-"
            enemy_grade = enemy.get(key) or "-"
            diff = comparison.get(key) or ""
            diff_text = self._comparison_text(diff)
            lines.append(f"{label}：己方 {ally_grade} / 敌方 {enemy_grade} {diff_text}".rstrip())
        return _join_lines(lines)

    def _comparison_text(self, value: str) -> str:
        mapping = {
            "ally_advantage": "（我方优）",
            "ally_big_advantage": "（我方大优）",
            "enemy_advantage": "（敌方优）",
            "enemy_big_advantage": "（敌方大优）",
            "even": "（均势）",
        }
        return mapping.get(value, "")

    def _format_advice(self, state: dict[str, Any]) -> str:
        coach = _safe_dict(state.get("coach"))
        advice = coach.get("advice")
        macro = _safe_dict(coach.get("macro_plan"))
        lines = []
        if isinstance(advice, str):
            lines.extend([line.strip() for line in advice.splitlines() if line.strip()])
        elif isinstance(advice, list):
            lines.extend([str(item).strip() for item in advice if str(item).strip()])
        lines.extend(_safe_list(macro.get("objectives"))[:2])
        lines.extend(_safe_list(macro.get("risk_alerts"))[:2])
        if not lines:
            return "暂无战术建议。"
        return "\n".join([f"✓ {item}" for item in lines[:6]])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    window = InGameTacticalOverlay()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

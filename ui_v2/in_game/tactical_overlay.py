from __future__ import annotations

import json
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
    QSlider,
    QVBoxLayout,
    QWidget,
)

from analysis.draft_session_control import read_control
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

SETTINGS_PATH = ROOT / "data" / "ingame_overlay_settings.json"
DEFAULT_SETTINGS = {
    "x": 80,
    "y": 80,
    "width": 360,
    "height": 520,
    "opacity": 92,
    "background_strength": 36,
    "collapsed": False,
    "prefer_frozen": True,
    "compact_mode": True,
}


OVERLAY_STYLE_TEMPLATE = """
QWidget {
    background: transparent;
    color: #0F172A;
    font-family: Microsoft YaHei, Segoe UI, Arial;
    font-size: 14px;
    font-weight: 700;
}
QFrame#Root {
    background: rgba(248, 250, 252, __ROOT_ALPHA__);
    border: 1px solid rgba(255, 255, 255, __BORDER_ALPHA__);
    border-radius: 14px;
}
QFrame#TitleBar {
    background: rgba(241, 245, 249, __TITLE_ALPHA__);
    border: 1px solid rgba(255, 255, 255, __BORDER_ALPHA__);
    border-radius: 12px;
}
QLabel#Title {
    color: #111827;
    font-size: 16px;
    font-weight: 800;
}
QLabel#Muted {
    color: #1E3A8A;
    font-weight: 800;
}
QLabel#SectionTitle {
    color: #075985;
    font-size: 14px;
    font-weight: 800;
}
QLabel#Card {
    background: rgba(255, 255, 255, __CARD_ALPHA__);
    border: 1px solid rgba(255, 255, 255, __BORDER_ALPHA__);
    border-radius: 10px;
    padding: 8px;
    line-height: 150%;
    color: #0F172A;
}
QLabel#AlertCard {
    background: rgba(254, 243, 199, __CARD_ALPHA__);
    border: 1px solid rgba(250, 204, 21, __BORDER_ALPHA__);
    border-radius: 10px;
    color: #7C2D12;
    padding: 8px;
    font-weight: 800;
}
QPushButton {
    background: rgba(255, 255, 255, __BUTTON_ALPHA__);
    color: #0F172A;
    border: 1px solid rgba(255, 255, 255, __BORDER_ALPHA__);
    border-radius: 8px;
    padding: 5px 9px;
    font-weight: 800;
}
QPushButton:hover {
    background: rgba(255, 255, 255, 155);
}
QPushButton#PrimaryButton {
    background: rgba(14, 165, 233, 185);
    border-color: rgba(125, 211, 252, 230);
    color: #FFFFFF;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: rgba(255, 255, 255, 45);
    width: 8px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 145);
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


def _build_style(background_strength: int) -> str:
    strength = max(20, min(100, int(background_strength)))
    root_alpha = int(18 + strength * 0.95)
    title_alpha = int(28 + strength * 1.05)
    card_alpha = int(20 + strength * 1.0)
    button_alpha = int(28 + strength * 0.95)
    border_alpha = int(95 + strength * 1.15)
    replacements = {
        "__ROOT_ALPHA__": str(min(220, root_alpha)),
        "__TITLE_ALPHA__": str(min(220, title_alpha)),
        "__CARD_ALPHA__": str(min(210, card_alpha)),
        "__BUTTON_ALPHA__": str(min(210, button_alpha)),
        "__BORDER_ALPHA__": str(min(230, border_alpha)),
    }
    style = OVERLAY_STYLE_TEMPLATE
    for key, value in replacements.items():
        style = style.replace(key, value)
    return style


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _join_lines(items: list[str], empty: str = "暂无") -> str:
    valid = [item for item in items if item]
    return "\n".join(valid) if valid else empty


def _load_settings() -> dict[str, Any]:
    try:
        if SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                settings = dict(DEFAULT_SETTINGS)
                settings.update(data)
                return settings
    except Exception:
        pass
    return dict(DEFAULT_SETTINGS)


def _save_settings(settings: dict[str, Any]):
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


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
        self._settings = _load_settings()
        self.resize(
            int(self._settings.get("width") or self.DEFAULT_W),
            int(self._settings.get("height") or self.DEFAULT_H),
        )
        self.setMinimumSize(260, 180)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._background_strength = max(
            20,
            min(100, int(self._settings.get("background_strength") or 48)),
        )
        self.setStyleSheet(_build_style(self._background_strength))
        self.setWindowOpacity(max(50, min(100, int(self._settings.get("opacity") or 92))) / 100)

        self._drag_pos = None
        self._paused = False
        self._collapsed = bool(self._settings.get("collapsed"))
        self._prefer_frozen = bool(self._settings.get("prefer_frozen", True))
        self._compact_mode = bool(self._settings.get("compact_mode", True))
        self._last_state: dict[str, Any] = {}
        self._full_widgets: list[QWidget] = []

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
        self._build_settings_bar()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.poll_state)
        self._timer.start(500)

        self._restore_geometry()
        if self._collapsed:
            self._apply_collapsed_state()
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

        self.frozen_button = QPushButton("定格优先")
        self.frozen_button.setObjectName("PrimaryButton" if self._prefer_frozen else "")
        self.frozen_button.clicked.connect(self.toggle_prefer_frozen)
        row.addWidget(self.frozen_button)

        self.compact_button = QPushButton("精简" if self._compact_mode else "完整")
        self.compact_button.setObjectName("PrimaryButton" if self._compact_mode else "")
        self.compact_button.clicked.connect(self.toggle_compact_mode)
        row.addWidget(self.compact_button)

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

    def _build_settings_bar(self):
        box = QVBoxLayout()
        box.setContentsMargins(2, 0, 2, 0)
        box.setSpacing(4)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.opacity_caption = QLabel("透明度")
        self.opacity_caption.setObjectName("Muted")
        row.addWidget(self.opacity_caption)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(60, 100)
        self.opacity_slider.setValue(max(60, min(100, int(self._settings.get("opacity") or 92))))
        self.opacity_slider.valueChanged.connect(self.set_overlay_opacity)
        row.addWidget(self.opacity_slider, 1)

        self.opacity_label = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_label.setObjectName("Muted")
        self.opacity_label.setFixedWidth(42)
        row.addWidget(self.opacity_label)

        bg_row = QHBoxLayout()
        bg_row.setContentsMargins(0, 0, 0, 0)
        bg_row.setSpacing(8)

        self.background_caption = QLabel("背景")
        self.background_caption.setObjectName("Muted")
        bg_row.addWidget(self.background_caption)

        self.background_slider = QSlider(Qt.Horizontal)
        self.background_slider.setRange(20, 100)
        self.background_slider.setValue(self._background_strength)
        self.background_slider.valueChanged.connect(self.set_background_strength)
        bg_row.addWidget(self.background_slider, 1)

        self.background_label = QLabel(f"{self.background_slider.value()}%")
        self.background_label.setObjectName("Muted")
        self.background_label.setFixedWidth(42)
        bg_row.addWidget(self.background_label)

        box.addLayout(row)
        box.addLayout(bg_row)
        self._layout.addLayout(box)

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

        self.compact_label = self._card(alert=True)
        self.content_layout.addWidget(self.compact_label)

        self._add_full_section("阵容快照", self.draft_label)
        self._add_full_section("核心节奏", self.key_plan_label)
        self._add_full_section("路线强弱", self.lane_label)
        self._add_full_section("阵容对比", self.team_label)
        self._add_full_section("战术建议", self.advice_label)
        self.content_layout.addStretch()

        self.scroll.setWidget(self.content)
        self._layout.addWidget(self.scroll, 1)
        self._apply_view_mode()

    def _add_full_section(self, title: str, card: QLabel):
        section = self._section(title)
        self._full_widgets.extend([section, card])
        self.content_layout.addWidget(section)
        self.content_layout.addWidget(card)

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

    def toggle_prefer_frozen(self):
        self._prefer_frozen = not self._prefer_frozen
        self.frozen_button.setText("定格优先" if self._prefer_frozen else "实时优先")
        self.frozen_button.setObjectName("PrimaryButton" if self._prefer_frozen else "")
        self.frozen_button.style().unpolish(self.frozen_button)
        self.frozen_button.style().polish(self.frozen_button)
        self._settings["prefer_frozen"] = self._prefer_frozen
        _save_settings(self._settings)
        self.poll_state(force=True)

    def toggle_compact_mode(self):
        self._compact_mode = not self._compact_mode
        self.compact_button.setText("精简" if self._compact_mode else "完整")
        self.compact_button.setObjectName("PrimaryButton" if self._compact_mode else "")
        self.compact_button.style().unpolish(self.compact_button)
        self.compact_button.style().polish(self.compact_button)
        self._settings["compact_mode"] = self._compact_mode
        _save_settings(self._settings)
        self._apply_view_mode()
        self.poll_state(force=True)

    def _apply_view_mode(self):
        if not hasattr(self, "compact_label"):
            return
        self.compact_label.setVisible(self._compact_mode)
        for widget in getattr(self, "_full_widgets", []):
            widget.setVisible(not self._compact_mode)

    def set_overlay_opacity(self, value: int):
        value = max(60, min(100, int(value)))
        self.opacity_label.setText(f"{value}%")
        self.setWindowOpacity(value / 100)
        self._settings["opacity"] = value
        _save_settings(self._settings)

    def set_background_strength(self, value: int):
        value = max(20, min(100, int(value)))
        self._background_strength = value
        self.background_label.setText(f"{value}%")
        self.setStyleSheet(_build_style(value))
        self._settings["background_strength"] = value
        _save_settings(self._settings)

    def toggle_pause(self):
        self._paused = not self._paused
        self.pause_button.setText("继续" if self._paused else "暂停")
        if self._paused:
            self.status_label.setText("已暂停刷新 / 当前战术已定格")
        else:
            self.poll_state(force=True)

    def toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._apply_collapsed_state()
        self._settings["collapsed"] = self._collapsed
        _save_settings(self._settings)

    def _apply_collapsed_state(self):
        self.scroll.setVisible(not self._collapsed)
        self.opacity_caption.setVisible(not self._collapsed)
        self.opacity_slider.setVisible(not self._collapsed)
        self.opacity_label.setVisible(not self._collapsed)
        self.background_caption.setVisible(not self._collapsed)
        self.background_slider.setVisible(not self._collapsed)
        self.background_label.setVisible(not self._collapsed)
        self.collapse_button.setText("+" if self._collapsed else "—")
        if self._collapsed:
            self.resize(self.COLLAPSED_W, self.COLLAPSED_H)
            self.setMinimumSize(self.COLLAPSED_W, self.COLLAPSED_H)
        else:
            self.setMinimumSize(260, 180)
            self.resize(
                int(self._settings.get("width") or self.DEFAULT_W),
                int(self._settings.get("height") or self.DEFAULT_H),
            )

    def poll_state(self, force: bool = False):
        if self._paused and not force:
            return
        state = self._read_display_state()
        self._last_state = state
        self.render(state)

    def _read_display_state(self) -> dict[str, Any]:
        live_state = read_state()
        if not self._prefer_frozen:
            live_state["_overlay_source"] = "实时"
            return live_state
        control = read_control()
        frozen_state = control.get("frozen_state")
        if isinstance(frozen_state, dict) and frozen_state.get("timestamp"):
            state = dict(frozen_state)
            state["_overlay_source"] = "定格"
            return state
        live_state["_overlay_source"] = "实时"
        return live_state

    def render(self, state: dict[str, Any]):
        timestamp = int(state.get("timestamp") or 0)
        role = ROLE_LABELS.get(state.get("role") or state.get("target_role") or "", "未选择")
        source = state.get("_overlay_source") or "实时"
        if timestamp:
            updated = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
            self.status_label.setText(f"● {source}  位置：{role}  更新：{updated}")
        else:
            self.status_label.setText("等待 BP 数据")

        self.draft_label.setText(self._format_draft(state))
        self.key_plan_label.setText(self._format_key_plan(state))
        self.lane_label.setText(self._format_lanes(state))
        self.team_label.setText(self._format_team_comparison(state))
        self.advice_label.setText(self._format_advice(state))
        self.compact_label.setText(self._format_compact(state))

    def _format_compact(self, state: dict[str, Any]) -> str:
        coach = _safe_dict(state.get("coach"))
        macro = _safe_dict(coach.get("macro_plan"))
        lane_state = _safe_dict(coach.get("lane_state"))
        lanes = _safe_list(lane_state.get("lanes"))

        lines = []
        primary_side = macro.get("primary_side") or "未判断"
        primary_lane = macro.get("primary_lane") or "未判断"
        lines.append(f"◆ 主节奏：{primary_side} / {primary_lane}")

        attack_lanes = []
        protect_lanes = []
        for lane in lanes:
            if not isinstance(lane, dict):
                continue
            label = lane.get("label") or lane.get("lane") or "路线"
            priority = str(lane.get("priority") or "")
            state_text = str(lane.get("state") or "")
            if "主攻" in priority or "大优" in state_text:
                attack_lanes.append(label)
            if "防守" in priority or "劣" in state_text:
                protect_lanes.append(label)
        if attack_lanes:
            lines.append(f"▲ 主攻：{'、'.join(attack_lanes[:2])}")
        if protect_lanes:
            lines.append(f"▼ 防守：{'、'.join(protect_lanes[:2])}")

        key_lane = self._pick_key_lane(lanes)
        if key_lane:
            lines.append(key_lane)

        advice_lines = self._collect_advice_lines(state, limit=3)
        if advice_lines:
            lines.append("★ 关键建议")
            lines.extend([f"✓ {item}" for item in advice_lines])
        else:
            lines.extend([f"✓ {item}" for item in _safe_list(macro.get("summary"))[:3]])

        return _join_lines(lines, "暂无精简战术，请先完成 BP 识别或载入演示阵容。")

    def _pick_key_lane(self, lanes: list) -> str:
        for lane in lanes:
            if not isinstance(lane, dict):
                continue
            priority = str(lane.get("priority") or "")
            if "主攻" in priority:
                return self._format_lane_one_line(lane)
        for lane in lanes:
            if isinstance(lane, dict):
                return self._format_lane_one_line(lane)
        return ""

    def _format_lane_one_line(self, lane: dict[str, Any]) -> str:
        label = lane.get("label") or lane.get("lane") or "路线"
        state_text = lane.get("state") or "未知"
        ally = lane.get("ally_display") or champion_display_name(lane.get("ally", ""))
        enemy = lane.get("enemy_display") or champion_display_name(lane.get("enemy", ""))
        action = lane.get("jungle_action") or lane.get("advice") or ""
        if action:
            return f"● {label}：{ally} vs {enemy}｜{state_text}\n→ {action}"
        return f"● {label}：{ally} vs {enemy}｜{state_text}"

    def _collect_advice_lines(self, state: dict[str, Any], limit: int = 3) -> list[str]:
        coach = _safe_dict(state.get("coach"))
        macro = _safe_dict(coach.get("macro_plan"))
        raw_advice = coach.get("advice")
        lines = []
        if isinstance(raw_advice, str):
            lines.extend([line.strip(" ✓·") for line in raw_advice.splitlines() if line.strip()])
        elif isinstance(raw_advice, list):
            lines.extend([str(item).strip(" ✓·") for item in raw_advice if str(item).strip()])
        lines.extend([str(item).strip(" ✓·") for item in _safe_list(macro.get("objectives"))])
        lines.extend([str(item).strip(" ✓·") for item in _safe_list(macro.get("risk_alerts"))])

        deduped = []
        seen = set()
        for line in lines:
            if not line or line in seen:
                continue
            seen.add(line)
            deduped.append(line)
            if len(deduped) >= limit:
                break
        return deduped

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
        lines = self._collect_advice_lines(state, limit=6)
        if not lines:
            return "暂无战术建议。"
        return "\n".join([f"✓ {item}" for item in lines])

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
        self._save_geometry()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not getattr(self, "_collapsed", False):
            self._settings["width"] = self.width()
            self._settings["height"] = self.height()
            _save_settings(self._settings)

    def closeEvent(self, event):
        self._save_geometry()
        super().closeEvent(event)

    def _restore_geometry(self):
        x = int(self._settings.get("x") or DEFAULT_SETTINGS["x"])
        y = int(self._settings.get("y") or DEFAULT_SETTINGS["y"])
        self.move(x, y)

    def _save_geometry(self):
        self._settings["x"] = self.x()
        self._settings["y"] = self.y()
        if not self._collapsed:
            self._settings["width"] = self.width()
            self._settings["height"] = self.height()
        _save_settings(self._settings)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    window = InGameTacticalOverlay()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

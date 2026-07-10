from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui_v2.pages.coach_page import CoachPage
from ui_v2.pages.lane_page import LanePage
from ui_v2.pages.macro_page import MacroPage
from ui_v2.pages.player_page import PlayerPage
from ui_v2.pages.patch_notes_page import PatchNotesPage
from ui_v2.pages.recommend_page import RecommendPage
from ui_v2.pages.selected_champions_page import SelectedChampionsPage
from ui_v2.pages.update_page import UpdatePage
from ui_v2.state_reader import LIVE_STATE_PATH, read_state
from ui_v2.in_game.tactical_overlay import InGameTacticalOverlay
from analysis.data_patch_manager import DataPatchManager
from analysis.draft_session_control import pause_state, resume_updates, start_new_game, write_live_state
from utils.champion_names import champion_display_name
from utils.window_capture_exclusion import exclude_window_from_capture


ROOT = Path(__file__).resolve().parent.parent
LIVE_DRAFT_PATH = LIVE_STATE_PATH.with_name("live_draft.json")
ROLES = [
    ("TOP", "上路"),
    ("JUNGLE", "打野"),
    ("MID", "中路"),
    ("ADC", "射手"),
    ("SUPPORT", "辅助"),
]


APP_STYLE = """
QMainWindow, QWidget {
    background: #0B1020;
    color: #E5E7EB;
    font-family: Microsoft YaHei, Segoe UI, Arial;
    font-size: 14px;
}
QFrame#AppShell {
    background: #111827;
    border: 2px solid #263244;
    border-radius: 22px;
}
QFrame#TopBar {
    background: transparent;
    border: none;
}
QFrame#SideBar {
    background: #0F172A;
    border: 1px solid #233044;
    border-radius: 16px;
}
QLabel#AppTitle {
    color: #F9FAFB;
    font-size: 30px;
    font-weight: 800;
}
QLabel#AppSubtitle {
    color: #9CA3AF;
    font-size: 14px;
}
QLabel#StatusText, QLabel#MutedText {
    color: #9CA3AF;
}
QLabel#NavStatus {
    color: #22C55E;
    font-weight: 700;
}
QLabel#DetectionStatus {
    color: #CBD5E1;
    background: #0F172A;
    border: 1px solid #233044;
    border-radius: 12px;
    padding: 8px 12px;
}
QLabel#PatchNotice {
    background: #3A2A12;
    color: #FACC15;
    border: 1px solid #7A5A20;
    border-radius: 12px;
    padding: 8px 12px;
    font-weight: 700;
}
QLabel#PageTitle {
    color: #F9FAFB;
    font-size: 24px;
    font-weight: 800;
}
QLabel#CoachGrades {
    color: #E5E7EB;
    padding: 10px;
    background: #0F172A;
    border: 1px solid #233044;
    border-radius: 12px;
}
QListWidget {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget::item {
    padding: 13px 18px;
    margin: 5px 10px;
    color: #CBD5E1;
    border-radius: 10px;
}
QListWidget::item:selected {
    background: #2563EB;
    color: white;
    font-weight: 700;
}
QTableWidget, QTextEdit {
    background: #0F172A;
    color: #E5E7EB;
    border: 1px solid #233044;
    border-radius: 12px;
    gridline-color: #233044;
    padding: 8px;
}
QHeaderView::section {
    background: #172033;
    color: #F9FAFB;
    padding: 8px;
    border: none;
}
QFrame#HeroCard {
    background: #172033;
    border: 1px solid transparent;
    border-radius: 14px;
}
QFrame#HeroCard:hover {
    background: #1D2940;
    border: 1px solid #2563EB;
}
QLabel#HeroAvatar {
    background: #334155;
    color: white;
    border: none;
    border-radius: 24px;
    font-weight: 700;
}
QLabel#HeroName {
    color: #F9FAFB;
    font-size: 18px;
    font-weight: 800;
}
QLabel#HeroTags {
    color: #93C5FD;
    font-size: 13px;
}
QLabel#HeroScore {
    color: #BFDBFE;
    font-size: 22px;
    font-weight: 800;
}
QPushButton#RoleButton {
    background: #172033;
    color: #CBD5E1;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 6px 10px;
}
QPushButton#RoleButton:checked {
    background: #2563EB;
    color: white;
    border-color: #2563EB;
    font-weight: 700;
}
QPushButton {
    background: #334155;
    color: #F8FAFC;
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 700;
}
QPushButton:hover {
    background: #475569;
}
QPushButton:disabled {
    background: #1E293B;
    color: #64748B;
}
QPushButton#PrimaryButton {
    background: #2563EB;
}
QPushButton#PrimaryButton:hover {
    background: #1D4ED8;
}
QStackedWidget {
    background: #0F172A;
    border: 1px solid #233044;
    border-radius: 16px;
}
QLineEdit {
    background: #172033;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 10px 14px;
    selection-background-color: #2563EB;
}
QLineEdit:focus {
    border: 1px solid #2563EB;
}
QScrollBar:vertical {
    background: #0F172A;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL BP Coach")
        self.setMinimumSize(980, 620)
        self.setStyleSheet(APP_STYLE)
        self.recognition_process: subprocess.Popen | None = None
        self.ingame_overlay: InGameTacticalOverlay | None = None

        self.update_page = UpdatePage()
        self.update_page.status_changed.connect(self.check_patch_notice)
        self.pages = [
            ("英雄推荐", RecommendPage()),
            ("对线推荐", LanePage()),
            ("已选英雄", SelectedChampionsPage()),
            ("战术·阵容建议", CoachPage()),
            ("战术·路线节奏", MacroPage()),
            ("我的数据", PlayerPage()),
            ("版本更新", PatchNotesPage()),
            ("数据更新", self.update_page),
        ]

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(22, 22, 22, 22)
        root_layout.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("AppShell")
        root_layout.addWidget(shell, 1)

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(28, 22, 28, 28)
        shell_layout.setSpacing(12)

        self.top_bar = self._build_top_bar()
        shell_layout.addWidget(self.top_bar)

        self.detected_status = QLabel("识别状态：等待识别")
        self.detected_status.setObjectName("DetectionStatus")
        self.detected_status.setWordWrap(False)
        self.detected_status.setMaximumHeight(40)
        shell_layout.addWidget(self.detected_status)

        self.patch_notice = QLabel("")
        self.patch_notice.setObjectName("PatchNotice")
        self.patch_notice.setWordWrap(True)
        self.patch_notice.hide()
        shell_layout.addWidget(self.patch_notice)

        body = QHBoxLayout()
        body.setSpacing(20)
        shell_layout.addLayout(body, 1)

        self.nav = self._build_nav()
        body.addWidget(self.nav_frame)

        self.stack = QStackedWidget()
        for _, page in self.pages:
            self.stack.addWidget(page)
        body.addWidget(self.stack, 1)

        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_state)
        self.timer.start(500)
        self.poll_state()
        QTimer.singleShot(200, self.check_patch_notice)
        QTimer.singleShot(300, self.enable_capture_exclusion)

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setMinimumHeight(112)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("LoL BP Coach")
        title.setObjectName("AppTitle")
        subtitle = QLabel("BP 识别 · 英雄推荐 · 对线分析 · 战术教练")
        subtitle.setObjectName("AppSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)

        control_box = QVBoxLayout()
        control_box.setSpacing(8)
        layout.addLayout(control_box, 1)

        role_row = QHBoxLayout()
        role_row.setSpacing(8)
        role_label = QLabel("位置")
        role_label.setObjectName("StatusText")
        role_row.addWidget(role_label)
        self.role_buttons: dict[str, QPushButton] = {}
        for role, label in ROLES:
            button = QPushButton(label)
            button.setObjectName("RoleButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, selected=role: self.change_role(selected))
            self.role_buttons[role] = button
            role_row.addWidget(button)
        role_row.addStretch()
        control_box.addLayout(role_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.start_bp_button = QPushButton("启动识别")
        self.start_bp_button.setObjectName("PrimaryButton")
        self.start_bp_button.clicked.connect(self.start_recognition)
        action_row.addWidget(self.start_bp_button)

        self.stop_bp_button = QPushButton("停止识别")
        self.stop_bp_button.clicked.connect(self.stop_recognition)
        self.stop_bp_button.setEnabled(False)
        action_row.addWidget(self.stop_bp_button)

        self.demo_button = QPushButton("\u6f14\u793a\u9635\u5bb9")
        self.demo_button.clicked.connect(self.load_demo_state)
        action_row.addWidget(self.demo_button)

        self.freeze_button = QPushButton("\u5b9a\u683c")
        self.freeze_button.setObjectName("PrimaryButton")
        self.freeze_button.setToolTip("\u5b9a\u683c\u5f53\u524d\u63a8\u8350\u548c\u6218\u672f\uff0c\u540e\u7eed\u8bc6\u522b\u4e0d\u4f1a\u8986\u76d6\u754c\u9762")
        self.freeze_button.clicked.connect(self.freeze_current_result)
        action_row.addWidget(self.freeze_button)

        self.resume_button = QPushButton("\u7ee7\u7eed")
        self.resume_button.setToolTip("\u6062\u590d\u5b9e\u65f6\u8bc6\u522b\u5237\u65b0")
        self.resume_button.clicked.connect(self.resume_live_updates)
        action_row.addWidget(self.resume_button)

        self.new_game_button = QPushButton("\u65b0\u5c40")
        self.new_game_button.setToolTip("\u6e05\u7a7a\u5f53\u524dBP\uff0c\u5f00\u59cb\u65b0\u7684\u4e00\u5c40")
        self.new_game_button.clicked.connect(self.start_new_draft_session)
        action_row.addWidget(self.new_game_button)

        self.ingame_overlay_button = QPushButton("局内浮窗")
        self.ingame_overlay_button.setToolTip("打开只读战术浮窗：显示已生成的局内战术，不读取游戏内存")
        self.ingame_overlay_button.clicked.connect(self.open_ingame_overlay)
        action_row.addWidget(self.ingame_overlay_button)
        action_row.addStretch()
        control_box.addLayout(action_row)

        self.bp_status = QLabel("BP状态: 等待数据")
        self.bp_status.setObjectName("StatusText")
        self.role_status = QLabel("当前角色: 未选择")
        self.role_status.setObjectName("StatusText")
        self.connection_status = QLabel("未连接")
        self.connection_status.setObjectName("StatusText")
        self.recognition_status = QLabel("识别未启动")
        self.recognition_status.setObjectName("StatusText")
        return bar

    def enable_capture_exclusion(self):
        if exclude_window_from_capture(int(self.winId())):
            self.recognition_status.setText("识别窗口隔离已启用")

    def _build_nav(self) -> QListWidget:
        self.nav_frame = QFrame()
        self.nav_frame.setObjectName("SideBar")
        layout = QVBoxLayout(self.nav_frame)
        layout.setContentsMargins(10, 20, 10, 12)
        layout.setSpacing(10)

        nav_title = QLabel("导航")
        nav_title.setObjectName("PageTitle")
        layout.addWidget(nav_title)

        nav = QListWidget()
        nav.setFixedWidth(158)
        for title, _ in self.pages:
            QListWidgetItem(title, nav)
        layout.addWidget(nav, 1)

        self.nav_connection_status = QLabel("● 未连接")
        self.nav_connection_status.setObjectName("NavStatus")
        self.nav_role_status = QLabel("当前分路：未选择")
        self.nav_role_status.setObjectName("StatusText")
        self.nav_recognition_status = QLabel("识别未启动")
        self.nav_recognition_status.setObjectName("StatusText")
        layout.addWidget(self.nav_connection_status)
        layout.addWidget(self.nav_role_status)
        layout.addWidget(self.nav_recognition_status)
        return nav

    def poll_state(self):
        state = read_state()
        self.render(state)
        self.update_recognition_status()

    def render(self, state: dict):
        timestamp = int(state.get("timestamp") or 0)
        role = state.get("role") or state.get("target_role") or "未选择"
        ally = state.get("ally", []) or []
        enemy = state.get("enemy", []) or []

        if timestamp:
            updated = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
            self.connection_status.setText(f"已连接 / {updated}")
            if hasattr(self, "nav_connection_status"):
                self.nav_connection_status.setText(f"● 已连接 / {updated}")
        else:
            self.connection_status.setText("未连接")
            if hasattr(self, "nav_connection_status"):
                self.nav_connection_status.setText("● 未连接")

        if ally or enemy:
            self.bp_status.setText(f"BP状态: 己方 {len(ally)} / 敌方 {len(enemy)}")
        else:
            self.bp_status.setText("BP状态: 等待数据")
        self.role_status.setText(f"当前角色: {role}")
        if hasattr(self, "nav_role_status"):
            self.nav_role_status.setText(f"当前分路：{self._role_label(role)}")
        self.detected_status.setText(self._format_detected_status(state))
        for role_id, button in self.role_buttons.items():
            button.setChecked(role_id == role)
        self._update_session_buttons(state)

        for _, page in self.pages:
            page.render(state)

    def change_role(self, role: str):
        state = read_state()
        state["role"] = role
        state["target_role"] = role
        state["timestamp"] = int(time.time())
        write_live_state(state, force=True)
        self.render(state)

    def start_recognition(self):
        self.update_recognition_status()
        if self.recognition_process and self.recognition_process.poll() is None:
            return

        state = read_state()
        role = state.get("role") or state.get("target_role") or ""
        valid_roles = {item[0] for item in ROLES}
        if role not in valid_roles:
            self.recognition_status.setText("请先选择位置")
            return

        self.change_role(role)
        self._write_recognition_status(
            role,
            phase="starting",
            message="识别已启动，等待扫描 LOL BP 界面",
            recommendation_status="waiting",
        )
        env = os.environ.copy()
        env["LOL_NO_OVERLAY"] = "1"
        env["LOL_HIDE_CAPTURE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        log_path = ROOT / "logs" / "recognition.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("a", encoding="utf-8")
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--recognize", role]
        else:
            command = [sys.executable, str(ROOT / "lol_bp_screenshot.py"), "--recommend", role]

        self.recognition_process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        self.start_bp_button.setEnabled(False)
        self.stop_bp_button.setEnabled(True)
        self.recognition_status.setText(f"识别运行中: {role}")

    def stop_recognition(self):
        if self.recognition_process and self.recognition_process.poll() is None:
            self.recognition_process.terminate()
            try:
                self.recognition_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.recognition_process.kill()
        self.recognition_process = None
        self.start_bp_button.setEnabled(True)
        self.stop_bp_button.setEnabled(False)
        self.recognition_status.setText("识别已停止")
        state = read_state()
        self._write_recognition_status(
            state.get("role") or state.get("target_role") or "",
            phase="stopped",
            message="识别已停止",
            recommendation_status="stopped",
        )


    def load_demo_state(self):
        try:
            resume_updates()
            from analysis.demo_state import write_demo_state
            state = write_demo_state()
            self.render(state)
            self.recognition_status.setText("\u6f14\u793a\u9635\u5bb9\u5df2\u8f7d\u5165")
        except Exception as exc:
            self.recognition_status.setText(f"\u6f14\u793a\u9635\u5bb9\u8f7d\u5165\u5931\u8d25: {exc}")

    def freeze_current_result(self):
        state = pause_state(read_state())
        self.render(state)
        self.recognition_status.setText("\u63a8\u8350\u7ed3\u679c\u5df2\u5b9a\u683c")

    def resume_live_updates(self):
        state = resume_updates()
        self.render(state)
        self.recognition_status.setText("\u5df2\u7ee7\u7eed\u5237\u65b0")

    def start_new_draft_session(self):
        current = read_state()
        role = current.get("role") or current.get("target_role") or ""
        state = start_new_game(role)
        self.render(state)
        self.recognition_status.setText("\u65b0\u7684\u4e00\u5c40\u5df2\u5f00\u59cb")

    def open_ingame_overlay(self):
        if self.ingame_overlay is None or not self.ingame_overlay.isVisible():
            self.ingame_overlay = InGameTacticalOverlay()
        self.ingame_overlay.show()
        self.ingame_overlay.raise_()
        self.ingame_overlay.poll_state(force=True)
        self.recognition_status.setText("局内战术浮窗已打开")

    def _update_session_buttons(self, state: dict):
        paused = bool((state.get("session_control") or {}).get("paused"))
        if hasattr(self, "freeze_button"):
            self.freeze_button.setEnabled(not paused)
        if hasattr(self, "resume_button"):
            self.resume_button.setEnabled(paused)
        if paused:
            self.bp_status.setText(self.bp_status.text() + " / \u5df2\u5b9a\u683c")

    def update_recognition_status(self):
        if self.recognition_process and self.recognition_process.poll() is None:
            self.start_bp_button.setEnabled(False)
            self.stop_bp_button.setEnabled(True)
            if hasattr(self, "nav_recognition_status"):
                self.nav_recognition_status.setText("识别运行中")
            return
        if self.recognition_process and self.recognition_process.poll() is not None:
            self.recognition_process = None
            self.recognition_status.setText("识别未运行")
        if hasattr(self, "nav_recognition_status"):
            self.nav_recognition_status.setText(self.recognition_status.text())
        self.start_bp_button.setEnabled(True)
        self.stop_bp_button.setEnabled(False)

    def _write_recognition_status(self, role: str, phase: str, message: str, recommendation_status: str):
        state = read_state()
        state["role"] = role
        state["target_role"] = role
        state["timestamp"] = int(time.time())
        state["recognition"] = {
            "phase": phase,
            "message": message,
            "recommendation_status": recommendation_status,
            "ally_count": len(state.get("ally", []) or []),
            "enemy_count": len(state.get("enemy", []) or []),
            "ban_count": len(state.get("bans", []) or []),
            "last_scan_at": int(time.time()),
        }
        write_live_state(state, force=True)

    def _format_detected_status(self, state: dict) -> str:
        recognition = state.get("recognition", {}) or {}
        message = recognition.get("message") or "等待识别"
        ally = [champion_display_name(item) for item in state.get("ally", [])]
        enemy = [champion_display_name(item) for item in state.get("enemy", [])]
        bans = [champion_display_name(item) for item in state.get("bans", [])]
        ally_text = ", ".join(ally) if ally else "暂无"
        enemy_text = ", ".join(enemy) if enemy else "暂无"
        bans_text = ", ".join(bans[:8]) if bans else "暂无"
        return f"识别状态: {message} | 己方: {ally_text} | 敌方: {enemy_text} | Ban: {bans_text}"

    def check_patch_notice(self):
        try:
            status = DataPatchManager().get_status()
            if status.get("outdated"):
                current = status.get("current_patch", "unknown")
                latest = status.get("latest_patch", "unknown")
                self.patch_notice.setText(f"检测到新版本数据，建议更新：当前 {current} / 最新 {latest}")
                self.patch_notice.show()
            else:
                self.patch_notice.hide()
        except Exception:
            self.patch_notice.hide()

    def _role_label(self, role: str) -> str:
        for role_id, label in ROLES:
            if role_id == role:
                return label
        return role or "未选择"

    def closeEvent(self, event):
        self.stop_recognition()
        super().closeEvent(event)

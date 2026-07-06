from __future__ import annotations

import json
import time
from datetime import datetime

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
from ui_v2.pages.player_page import PlayerPage
from ui_v2.pages.patch_notes_page import PatchNotesPage
from ui_v2.pages.recommend_page import RecommendPage
from ui_v2.pages.update_page import UpdatePage
from ui_v2.state_reader import LIVE_STATE_PATH, read_state
from analysis.data_patch_manager import DataPatchManager


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
    background: #111318;
    color: #E7EAF0;
    font-family: Microsoft YaHei, Segoe UI, Arial;
    font-size: 13px;
}
QFrame#TopBar, QFrame#SideBar {
    background: #171A21;
    border: 1px solid #252A33;
}
QLabel#AppTitle {
    color: #F2C94C;
    font-size: 18px;
    font-weight: 700;
}
QLabel#StatusText, QLabel#MutedText {
    color: #AAB2C0;
}
QLabel#PatchNotice {
    background: #3A2A12;
    color: #F2C94C;
    border: 1px solid #7A5A20;
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: 700;
}
QLabel#PageTitle {
    color: #F2C94C;
    font-size: 22px;
    font-weight: 700;
}
QLabel#CoachGrades {
    color: #E7EAF0;
    padding: 10px;
    background: #171A21;
    border: 1px solid #252A33;
    border-radius: 6px;
}
QListWidget {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget::item {
    padding: 12px 14px;
    color: #B8C0CC;
    border-radius: 6px;
}
QListWidget::item:selected {
    background: #2D6CDF;
    color: white;
}
QTableWidget, QTextEdit {
    background: #171A21;
    color: #E7EAF0;
    border: 1px solid #252A33;
    border-radius: 6px;
    gridline-color: #252A33;
}
QHeaderView::section {
    background: #202532;
    color: #F2C94C;
    padding: 8px;
    border: none;
}
QFrame#HeroCard {
    background: #171A21;
    border: 1px solid #252A33;
    border-radius: 8px;
}
QLabel#HeroAvatar {
    background: #0B0E14;
    color: white;
    border: 1px solid #303644;
    border-radius: 6px;
    font-weight: 700;
}
QLabel#HeroName {
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 700;
}
QLabel#HeroTags {
    color: #AAB2C0;
}
QLabel#HeroScore {
    color: #F2C94C;
    font-size: 24px;
    font-weight: 800;
}
QPushButton#RoleButton {
    background: #202532;
    color: #B8C0CC;
    border: 1px solid #303644;
    border-radius: 6px;
    padding: 6px 10px;
}
QPushButton#RoleButton:checked {
    background: #2D6CDF;
    color: white;
    border-color: #2D6CDF;
    font-weight: 700;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL BP Coach")
        self.setMinimumSize(1040, 680)
        self.setStyleSheet(APP_STYLE)

        self.update_page = UpdatePage()
        self.update_page.status_changed.connect(self.check_patch_notice)
        self.pages = [
            ("英雄推荐", RecommendPage()),
            ("对线", LanePage()),
            ("战术", CoachPage()),
            ("我的数据", PlayerPage()),
            ("版本更新", PatchNotesPage()),
            ("数据更新", self.update_page),
        ]

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        self.top_bar = self._build_top_bar()
        root_layout.addWidget(self.top_bar)
        self.patch_notice = QLabel("")
        self.patch_notice.setObjectName("PatchNotice")
        self.patch_notice.setWordWrap(True)
        self.patch_notice.hide()
        root_layout.addWidget(self.patch_notice)

        body = QHBoxLayout()
        body.setSpacing(10)
        root_layout.addLayout(body, 1)

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

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("TopBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(18)

        title = QLabel("LoL BP Coach")
        title.setObjectName("AppTitle")
        layout.addWidget(title)
        layout.addStretch()

        role_label = QLabel("位置")
        role_label.setObjectName("StatusText")
        layout.addWidget(role_label)
        self.role_buttons: dict[str, QPushButton] = {}
        for role, label in ROLES:
            button = QPushButton(label)
            button.setObjectName("RoleButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, selected=role: self.change_role(selected))
            self.role_buttons[role] = button
            layout.addWidget(button)

        self.bp_status = QLabel("BP状态: 等待数据")
        self.bp_status.setObjectName("StatusText")
        self.role_status = QLabel("当前角色: 未选择")
        self.role_status.setObjectName("StatusText")
        self.connection_status = QLabel("未连接")
        self.connection_status.setObjectName("StatusText")
        layout.addWidget(self.bp_status)
        layout.addWidget(self.role_status)
        layout.addWidget(self.connection_status)
        return bar

    def _build_nav(self) -> QListWidget:
        self.nav_frame = QFrame()
        self.nav_frame.setObjectName("SideBar")
        layout = QVBoxLayout(self.nav_frame)
        layout.setContentsMargins(8, 8, 8, 8)

        nav = QListWidget()
        nav.setFixedWidth(160)
        for title, _ in self.pages:
            QListWidgetItem(title, nav)
        layout.addWidget(nav)
        return nav

    def poll_state(self):
        state = read_state()
        self.render(state)

    def render(self, state: dict):
        timestamp = int(state.get("timestamp") or 0)
        role = state.get("role") or state.get("target_role") or "未选择"
        ally = state.get("ally", []) or []
        enemy = state.get("enemy", []) or []

        if timestamp:
            updated = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
            self.connection_status.setText(f"已连接 / {updated}")
        else:
            self.connection_status.setText("未连接")

        if ally or enemy:
            self.bp_status.setText(f"BP状态: 己方 {len(ally)} / 敌方 {len(enemy)}")
        else:
            self.bp_status.setText("BP状态: 等待数据")
        self.role_status.setText(f"当前角色: {role}")
        for role_id, button in self.role_buttons.items():
            button.setChecked(role_id == role)

        for _, page in self.pages:
            page.render(state)

    def change_role(self, role: str):
        state = read_state()
        state["role"] = role
        state["target_role"] = role
        state["timestamp"] = int(time.time())
        LIVE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LIVE_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

        draft = {}
        if LIVE_DRAFT_PATH.exists():
            try:
                draft = json.loads(LIVE_DRAFT_PATH.read_text(encoding="utf-8"))
            except Exception:
                draft = {}
        draft.update({"role": role, "target_role": role, "timestamp": state["timestamp"]})
        LIVE_DRAFT_PATH.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
        self.render(state)

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


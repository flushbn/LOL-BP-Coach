from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QTextEdit, QVBoxLayout, QWidget

from utils.champion_names import champion_display_name


class RecognitionPage(QWidget):
    """Read-only view of the recognition state written by the screenshot worker."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("BP 识别")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        hint = QLabel("请先在顶部选择位置并启动识别。识别结果会实时写入推荐、对线和战术页面。")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        status_frame = QFrame()
        status_frame.setObjectName("CoachPanel")
        status_layout = QGridLayout(status_frame)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setHorizontalSpacing(20)
        status_layout.setVerticalSpacing(8)

        self.role_value = self._add_status(status_layout, 0, "当前分路")
        self.phase_value = self._add_status(status_layout, 1, "识别阶段")
        self.message_value = self._add_status(status_layout, 2, "当前状态")
        status_layout.setColumnStretch(1, 1)
        layout.addWidget(status_frame)

        self.detected = QTextEdit()
        self.detected.setReadOnly(True)
        self.detected.setObjectName("CoachPanel")
        self.detected.setPlaceholderText("暂无识别结果")
        self.detected.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(self.detected, 1)

    @staticmethod
    def _add_status(layout: QGridLayout, row: int, title: str) -> QLabel:
        label = QLabel(title)
        label.setObjectName("MutedText")
        value = QLabel("等待识别")
        value.setObjectName("StatusText")
        value.setWordWrap(True)
        layout.addWidget(label, row, 0)
        layout.addWidget(value, row, 1)
        return value

    def render(self, state: dict):
        recognition = state.get("recognition", {}) or {}
        role = state.get("role") or state.get("target_role") or "未选择"
        phase = recognition.get("phase") or "waiting"
        message = recognition.get("message") or "等待识别"
        self.role_value.setText(str(role))
        self.phase_value.setText(str(phase))
        self.message_value.setText(str(message))

        sections = [
            ("己方已选", state.get("ally", [])),
            ("敌方已选", state.get("enemy", [])),
            ("禁用英雄", state.get("bans", [])),
        ]
        content = []
        for heading, champions in sections:
            names = [champion_display_name(item) for item in champions if item]
            content.append(f"{heading}\n" + ("、".join(names) if names else "暂无"))
        text = "\n\n".join(content)
        if self.detected.toPlainText() != text:
            self.detected.setPlainText(text)

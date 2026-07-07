from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from utils.champion_assets import champion_icon_path


class HeroDetailPanel(QFrame):
    closed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("HeroCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setFocusPolicy(Qt.StrongFocus)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.icon = QLabel("")
        self.icon.setFixedSize(72, 72)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setObjectName("HeroAvatar")
        top.addWidget(self.icon)

        name_box = QVBoxLayout()
        self.title = QLabel("英雄详情")
        self.title.setObjectName("PageTitle")
        self.subtitle = QLabel("点击推荐英雄或搜索英雄查看详情")
        self.subtitle.setObjectName("MutedText")
        self.subtitle.setWordWrap(True)
        name_box.addWidget(self.title)
        name_box.addWidget(self.subtitle)
        top.addLayout(name_box, 1)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.hide_panel)
        top.addWidget(close_btn)
        root.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)

        self.meta = self._section("版本数据")
        self.runes = self._section("符文推荐")
        self.builds = self._section("出装推荐")
        self.situational = self._section("阵容适配装备")
        self.lane = self._section("对线思路")
        self.power = self._section("强势期分析")
        self.matchups = self._section("克制 / 协同")

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def render_detail(self, context: dict):
        champion = context.get("champion", "")
        champion_cn = context.get("champion_cn") or champion
        self.title.setText(champion_cn)
        roles = " / ".join(context.get("roles", [])) or "未知位置"
        patch = context.get("patch", "")
        self.subtitle.setText(f"位置：{roles}　版本：{patch}")
        self._set_icon(champion, champion_cn)

        meta = context.get("meta", {}) or {}
        if meta:
            self.meta.setText(
                "\n".join(
                    [
                        f"胜率：{meta.get('winrate', meta.get('win_rate', '暂无'))}%",
                        f"登场率：{meta.get('pickrate', meta.get('pick_rate', '暂无'))}%",
                        f"禁用率：{meta.get('banrate', meta.get('ban_rate', '暂无'))}%",
                        f"梯级：{meta.get('tier', '暂无')}　样本：{meta.get('games', meta.get('picks', '暂无'))}",
                        f"来源：{self._source_label(meta.get('source', 'current_patch'))}",
                    ]
                )
            )
        else:
            self.meta.setText("暂无版本数据")

        build_recommendation = context.get("build_recommendation", {}) or {}
        self.runes.setText(self._format_runes(context.get("runes", [])))
        self.builds.setText(self._format_builds(context.get("builds", []), build_recommendation))
        self.situational.setText(self._format_situational(build_recommendation))
        self.lane.setText(self._format_lines(context.get("lane_plan", []), "暂无对线思路"))
        self.power.setText(self._format_lines(context.get("power_spikes", []), "暂无强势期分析"))

        counters = context.get("counters", [])
        synergies = context.get("synergies", [])
        parts = []
        if counters:
            parts.append("克制参考：\n" + "\n".join(f"• {item}" for item in counters))
        if synergies:
            parts.append("协同参考：\n" + "\n".join(f"• {item}" for item in synergies))
        self.matchups.setText("\n\n".join(parts) if parts else "暂无克制 / 协同数据")

        self.show()
        self.setFocus()

    def hide_panel(self):
        self.hide()
        self.closed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide_panel()
            return
        super().keyPressEvent(event)

    def _section(self, title: str) -> QLabel:
        label_title = QLabel(title)
        label_title.setStyleSheet("font-weight:700;color:#F2C94C;")
        self.content_layout.addWidget(label_title)
        label = QLabel("")
        label.setObjectName("CoachGrades")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.content_layout.addWidget(label)
        return label

    def _set_icon(self, champion: str, champion_cn: str):
        path = champion_icon_path(champion) or champion_icon_path(champion_cn)
        if path:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.icon.setText("")
                self.icon.setPixmap(
                    pixmap.scaled(self.icon.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                )
                return
        self.icon.clear()
        self.icon.setText(champion_cn[:2])

    @staticmethod
    def _format_runes(runes: list[dict]) -> str:
        if not runes:
            return "暂无符文推荐"
        lines = []
        for rune in runes:
            secondary = rune.get("secondary", "暂无")
            if isinstance(secondary, list):
                secondary = " / ".join(str(item) for item in secondary if item) or "暂无"
            rune_names = rune.get("runes", [])
            extra = ""
            if isinstance(rune_names, list) and rune_names:
                extra = "\n  小符文：" + " / ".join(str(item) for item in rune_names[1:4] if item)
            stats = []
            if rune.get("winrate") is not None:
                stats.append(f"胜率 {rune.get('winrate')}%")
            if rune.get("games"):
                stats.append(f"样本 {rune.get('games')}")
            reason = rune.get("reason", "")
            lines.append(
                f"• {rune.get('primary', '主系')}：{rune.get('keystone', '核心符文')}　副系：{secondary}"
                + extra
                + (f"\n  {' / '.join(stats)}" if stats else "")
                + (f"\n  原因：{reason}" if reason else "")
            )
        return "\n".join(lines)

    @staticmethod
    def _format_builds(builds: list[dict], build_recommendation: dict | None = None) -> str:
        if not builds:
            return "暂无出装推荐"
        lines = []
        starting = (build_recommendation or {}).get("starting_items", [])
        if starting:
            lines.append("出门装：" + " + ".join(starting))
        for build in builds:
            items = " → ".join(build.get("items", []))
            note = build.get("reason") or build.get("note", "")
            stats = []
            if build.get("winrate") is not None:
                stats.append(f"胜率 {build.get('winrate')}%")
            if build.get("games"):
                stats.append(f"样本 {build.get('games')}")
            if build.get("build_score"):
                stats.append(f"评分 {build.get('build_score')}")
            lines.append(
                f"• {items}"
                + (f"\n  {' / '.join(stats)}" if stats else "")
                + (f"\n  {note}" if note else "")
            )
        return "\n".join(lines)

    @staticmethod
    def _format_situational(build_recommendation: dict) -> str:
        if not build_recommendation:
            return "暂无阵容适配装备"
        lines = []
        item_path = build_recommendation.get("item_path", {}) or {}
        path_parts = []
        for key, label in (("first_item", "第一件"), ("second_item", "第二件"), ("third_item", "第三件")):
            names = item_path.get(key, [])
            if names:
                path_parts.append(f"{label}：" + " / ".join(names))
        if path_parts:
            lines.append("装备路线\n" + "\n".join(path_parts))
        situational = build_recommendation.get("situational", []) or []
        if situational:
            lines.append(
                "应对调整\n"
                + "\n".join(
                    f"• {' / '.join(item.get('items', []))}\n  {item.get('reason', '')}"
                    for item in situational
                )
            )
        return "\n\n".join(lines) if lines else "暂无阵容适配装备"

    @staticmethod
    def _format_lines(lines: list[str], fallback: str) -> str:
        if not lines:
            return fallback
        return "\n".join(f"• {line}" for line in lines)

    @staticmethod
    def _source_label(source: str) -> str:
        return {
            "lolalytics_live": "当前版本实时数据",
            "lolalytics_live_full": "当前版本实时数据",
            "lolalytics_live_on_demand": "当前版本实时数据（按需抓取）",
            "current_patch": "当前版本数据",
        }.get(str(source), str(source))

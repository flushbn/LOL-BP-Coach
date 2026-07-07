from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from analysis.patch_notes_engine import PatchNotesEngine
from utils.champion_names import champion_display_name


TYPE_LABELS = {
    "buff": "增强",
    "nerf": "削弱",
    "adjust": "调整",
}

TYPE_COLORS = {
    "buff": "#ff4d4f",
    "nerf": "#52c41a",
    "adjust": "#f2c94c",
}

TAG_LABELS = {
    "top": "上路",
    "jungle": "打野",
    "mid": "中路",
    "middle": "中路",
    "adc": "射手",
    "bot": "下路",
    "bottom": "下路",
    "support": "辅助",
    "utility": "功能性",
    "frontline": "前排",
    "engage": "开团",
    "peel": "保护",
    "burst": "爆发",
    "dps": "持续输出",
    "scaling": "成长",
    "late_game": "后期",
    "early_game": "前期",
    "snowball": "滚雪球",
    "duel": "单挑",
    "anti_dash": "反突进",
    "assassin": "刺客",
    "roam": "游走",
    "damage_over_time": "持续伤害",
    "gank": "抓人",
    "splitpush": "单带",
    "laning": "对线",
    "sustain": "续航",
    "practice": "练习工具",
}

ITEM_LABELS = {
    "Doran's Shield": "多兰之盾",
    "Doran's Blade": "多兰之刃",
    "Doran's Ring": "多兰之戒",
    "Eclipse": "星蚀",
}

SYSTEM_LABELS = {
    "Practice Tool Last Hit": "练习工具补刀模式",
}

TEXT_REPLACEMENTS = {
    "Kai'Sa": "卡莎",
    "KaiSa": "卡莎",
    "Kaisa": "卡莎",
    "Draven": "德莱文",
    "Aphelios": "厄斐琉斯",
    "Poppy": "波比",
    "Yasuo": "亚索",
    "Qiyana": "奇亚娜",
    "Doran's Shield": "多兰之盾",
    "Riot Patch": "官方公告版本",
    "Meta": "版本环境",
    "BP": "禁选推荐",
}


class PatchNotesPage(QWidget):
    def __init__(self):
        super().__init__()
        self.engine = PatchNotesEngine()
        self._last_patch = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        header = QFrame()
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel("版本更新")
        self.title.setObjectName("PageTitle")
        self.source = QLabel("")
        self.source.setObjectName("MutedText")
        self.refresh_btn = QPushButton("刷新公告")
        self.refresh_btn.clicked.connect(self.reload)
        header_layout.addWidget(self.title, 0, 0)
        header_layout.addWidget(self.source, 1, 0)
        header_layout.addWidget(self.refresh_btn, 0, 1, 2, 1, Qt.AlignRight)
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)

        self.hero_changes = self._section("英雄改动")
        self.item_changes = self._section("装备改动")
        self.rune_changes = self._section("符文改动")
        self.system_changes = self._section("系统改动")
        self.meta_impacts = self._section("版本环境影响分析")
        self.rising = self._section("强势英雄（上升）")
        self.falling = self._section("弱势英雄（下降）")

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.reload()

    def reload(self):
        self.engine = PatchNotesEngine()
        summary = self.engine.get_patch_summary()
        self._last_patch = summary.get("patch", "")
        riot_patch = summary.get("riot_patch") or self._last_patch
        self.title.setText(f"版本 {self._last_patch} 更新")
        self.source.setText(f"公告来源：拳头官方公告版本 {riot_patch}")

        self.hero_changes.setText(self._format_changes(summary.get("champion_changes", []), "champion"))
        self.item_changes.setText(self._format_changes(summary.get("item_changes", []), "item"))
        self.rune_changes.setText(self._format_changes(summary.get("rune_changes", []), "rune"))
        self.system_changes.setText(self._format_changes(summary.get("system_changes", []), "name"))
        self.meta_impacts.setText(self._format_lines(summary.get("meta_impacts", [])))
        self.rising.setText(self._format_trends(summary.get("rising", []), "▲"))
        self.falling.setText(self._format_trends(summary.get("falling", []), "▼"))

    def render(self, state: dict):
        patch = state.get("patch") or state.get("current_patch") or ""
        if patch and patch != self._last_patch:
            self.reload()

    def _section(self, title: str) -> QLabel:
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:15px;color:#E7EAF0;font-weight:700;")
        self.content_layout.addWidget(title_label)

        label = QLabel()
        label.setWordWrap(True)
        label.setObjectName("CoachGrades")
        label.setTextFormat(Qt.RichText)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.content_layout.addWidget(label)
        return label

    @staticmethod
    def _format_changes(changes: list[dict], name_key: str) -> str:
        if not changes:
            return '<span style="color:#AAB2C0;">暂无记录</span>'

        lines = []
        for change in changes:
            raw_name = change.get(name_key) or change.get("champion") or change.get("item") or change.get("name") or "未知"
            name = PatchNotesPage._display_name(raw_name, name_key)
            change_type = str(change.get("type", "adjust"))
            type_label = TYPE_LABELS.get(change_type, "调整")
            type_color = TYPE_COLORS.get(change_type, "#f2c94c")
            description = PatchNotesPage._localize_text(str(change.get("description", "")))
            tags = PatchNotesPage._format_tags(change.get("impact_tags", [])[:4])
            suffix = f' <span style="color:#AAB2C0;">（{tags}）</span>' if tags else ""
            lines.append(
                '• '
                f'<b>{escape(name)}</b>：'
                f'<span style="color:{type_color};font-weight:700;">{escape(type_label)}</span>'
                f' - {escape(description)}'
                f'{suffix}'
            )
        return "<br>".join(lines)

    @staticmethod
    def _format_lines(lines: list[str]) -> str:
        if not lines:
            return '<span style="color:#AAB2C0;">暂无影响分析</span>'
        return "<br>".join(f"• {escape(PatchNotesPage._localize_text(line))}" for line in lines)

    @staticmethod
    def _format_trends(rows: list[dict], marker: str) -> str:
        if not rows:
            return '<span style="color:#AAB2C0;">暂无趋势数据</span>'
        lines = []
        for row in rows[:10]:
            change_type = str(row.get("type", "adjust"))
            color = TYPE_COLORS.get(change_type, "#f2c94c")
            delta = row.get("delta")
            delta_text = f" {delta:+.1f}%" if isinstance(delta, (int, float)) else ""
            champion = champion_display_name(row.get("champion", "未知"))
            description = PatchNotesPage._localize_text(str(row.get("description", "")))
            lines.append(
                f'<span style="color:{color};font-weight:700;">{escape(marker)} {escape(champion)}{escape(delta_text)}</span>'
                f'：{escape(description)}'
            )
        return "<br>".join(lines)

    @staticmethod
    def _display_name(name: str, name_key: str) -> str:
        if name_key == "champion":
            return champion_display_name(name)
        if name_key == "item":
            return ITEM_LABELS.get(name, name)
        if name_key == "name":
            return SYSTEM_LABELS.get(name, name)
        return name

    @staticmethod
    def _format_tags(tags: list[str]) -> str:
        return " / ".join(TAG_LABELS.get(str(tag), str(tag)) for tag in tags)

    @staticmethod
    def _localize_text(text: str) -> str:
        result = text
        for old, new in sorted(TEXT_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
            result = result.replace(old, new)
        return result


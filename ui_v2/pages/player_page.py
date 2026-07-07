from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from analysis.player_analytics import MATCH_SESSIONS_PATH, PlayerAnalytics
from analysis.personalized_recommender import refresh_profile
from utils.champion_names import champion_display_name


ROOT = Path(__file__).resolve().parent.parent.parent
ROLE_OPTIONS = [
    ("TOP", "上路"),
    ("JUNGLE", "打野"),
    ("MID", "中路"),
    ("ADC", "射手"),
    ("SUPPORT", "辅助"),
]


class PlayerPage(QWidget):
    def __init__(self):
        super().__init__()
        self._analytics = PlayerAnalytics()
        self._state: dict = {}
        self._name_to_key = self._load_champion_aliases()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("我的数据")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.record_box = QGroupBox("记录本局")
        record_layout = QVBoxLayout(self.record_box)
        record_layout.setSpacing(8)

        form = QHBoxLayout()
        self.hero_input = QLineEdit()
        self.hero_input.setPlaceholderText("输入英雄名，例如：李青 / LeeSin / Ahri")
        form.addWidget(QLabel("英雄"))
        form.addWidget(self.hero_input, 1)

        self.role_combo = QComboBox()
        for role, label in ROLE_OPTIONS:
            self.role_combo.addItem(label, role)
        form.addWidget(QLabel("位置"))
        form.addWidget(self.role_combo)

        self.fill_current_button = QPushButton("填入识别英雄")
        self.fill_current_button.clicked.connect(self.fill_current_hero)
        form.addWidget(self.fill_current_button)
        record_layout.addLayout(form)

        actions = QHBoxLayout()
        self.win_button = QPushButton("记录胜利")
        self.win_button.clicked.connect(lambda: self.record_match("WIN"))
        self.loss_button = QPushButton("记录失败")
        self.loss_button.clicked.connect(lambda: self.record_match("LOSE"))
        self.refresh_button = QPushButton("刷新数据")
        self.refresh_button.clicked.connect(self.refresh_player_data)
        actions.addWidget(self.win_button)
        actions.addWidget(self.loss_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch()
        record_layout.addLayout(actions)

        self.record_status = QLabel("记录后会写入 data/match_sessions.json，并影响后续熟练度推荐。")
        self.record_status.setObjectName("MutedText")
        self.record_status.setWordWrap(True)
        record_layout.addWidget(self.record_status)
        layout.addWidget(self.record_box)

        self.summary = QLabel("暂无玩家数据")
        self.summary.setObjectName("CoachGrades")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["英雄", "场次", "胜率", "最近使用"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        self.refresh_player_data()

    def render(self, state: dict):
        self._state = state or {}
        role = self._state.get("role") or self._state.get("target_role")
        if role:
            index = self.role_combo.findData(role)
            if index >= 0:
                self.role_combo.setCurrentIndex(index)
        self.refresh_player_data()

    def fill_current_hero(self):
        ally = self._state.get("ally", []) or []
        if ally:
            self.hero_input.setText(champion_display_name(ally[-1]))
            self.record_status.setText(f"已填入己方最近识别英雄：{champion_display_name(ally[-1])}")
        else:
            self.record_status.setText("当前没有识别到己方英雄，请手动输入。")

    def record_match(self, result: str):
        raw_hero = self.hero_input.text().strip()
        hero = self._normalize_hero(raw_hero)
        if not hero:
            self.record_status.setText("请先输入英雄名，再记录胜负。")
            return

        session = {
            "timestamp": int(time.time()),
            "hero": hero,
            "position": self.role_combo.currentData() or "",
            "result": result,
        }
        sessions = self._load_sessions()
        sessions.append(session)
        MATCH_SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        MATCH_SESSIONS_PATH.write_text(
            json.dumps(sessions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        refresh_profile()
        self.refresh_player_data()
        result_text = "胜利" if result == "WIN" else "失败"
        self.record_status.setText(
            f"已记录：{champion_display_name(hero)} / {self.role_combo.currentText()} / {result_text}"
        )

    def refresh_player_data(self):
        self._analytics.refresh()
        overall = self._analytics.get_overall_stats()
        positions = self._analytics.get_position_analysis()
        trend = self._analytics.get_trend()
        insights = self._analytics.get_hero_insights()
        style = self._analytics.get_style()

        if overall.get("games", 0):
            best = positions.get("best", {})
            core = ", ".join(champion_display_name(item["champion"]) for item in insights.get("core", [])[:3]) or "暂无"
            caution = ", ".join(champion_display_name(item["champion"]) for item in insights.get("caution", [])[:3]) or "暂无"
            self.summary.setText(
                "\n".join([
                    f"总场次：{overall['games']}　总胜率：{overall['winrate']}%　最近30场：{overall['recent30_wr']}%",
                    f"最近7天：{overall['recent7d_wr']}%　状态趋势：{trend.get('trend', '暂无')}",
                    f"最佳位置：{best.get('pos') or '暂无'} {best.get('wr', 0)}%　风格：{style.get('style_description', '暂无')}",
                    f"核心英雄：{core}",
                    f"谨慎选择：{caution}",
                ])
            )
        else:
            self.summary.setText("暂无玩家数据。请先在上方记录一局胜负。")

        heroes = self._analytics.get_hero_pool(20)
        self.table.setRowCount(len(heroes))
        for row, hero in enumerate(heroes):
            values = [
                champion_display_name(hero.get("champion", "")),
                hero.get("games", ""),
                f"{hero.get('winrate', '')}%",
                self._format_time(hero.get("last_played", 0)),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()

    def _load_sessions(self) -> list[dict]:
        try:
            if not MATCH_SESSIONS_PATH.exists():
                return []
            raw = MATCH_SESSIONS_PATH.read_text(encoding="utf-8-sig")
            data = json.loads(raw) if raw.strip() else []
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _normalize_hero(self, text: str) -> str:
        if not text:
            return ""
        key = _compact(text)
        return self._name_to_key.get(key, text)

    def _load_champion_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        data_path = ROOT / "data" / "zh_CN" / "champion.json"
        try:
            payload = json.loads(data_path.read_text(encoding="utf-8"))
            for key, info in payload.get("data", {}).items():
                aliases[_compact(key)] = key
                aliases[_compact(info.get("name", ""))] = key
                aliases[_compact(info.get("title", ""))] = key
        except Exception:
            pass
        for alias, champion in {
            "leesin": "LeeSin",
            "lee sin": "LeeSin",
            "jarvaniv": "JarvanIV",
            "jarvan iv": "JarvanIV",
            "twistedfate": "TwistedFate",
            "twisted fate": "TwistedFate",
            "missfortune": "MissFortune",
            "miss fortune": "MissFortune",
            "wukong": "MonkeyKing",
            "monkeyking": "MonkeyKing",
        }.items():
            aliases[_compact(alias)] = champion
        return aliases

    @staticmethod
    def _format_time(timestamp: int | float) -> str:
        try:
            if not timestamp:
                return ""
            return datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d")
        except Exception:
            return ""


def _compact(text: str) -> str:
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())

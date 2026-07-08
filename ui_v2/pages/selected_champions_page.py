from __future__ import annotations

import json
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QApplication,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from analysis.build_recommendation import BuildRecommendationEngine
from analysis.hero_detail_context import HeroDetailContextBuilder
from analysis.lolalytics_client import LolalyticsClient
from analysis.rune_recommendation import RuneRecommendationEngine
from ui_v2.components.hero_detail_panel import HeroDetailPanel
from ui_v2.components.hero_search_bar import HeroSearchBar
from utils.champion_assets import champion_icon_path, champion_key
from utils.champion_names import champion_display_name
from utils.game_terms_zh import item_zh, items_zh, rune_zh, runes_zh


ROOT = Path(__file__).resolve().parent.parent.parent
ROLE_TO_LABEL = {
    "TOP": "上路",
    "JUNGLE": "打野",
    "MID": "中路",
    "MIDDLE": "中路",
    "ADC": "射手",
    "BOTTOM": "射手",
    "SUPPORT": "辅助",
    "UTILITY": "辅助",
}
ROLE_ALIASES = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "MID": "MID",
    "MIDDLE": "MID",
    "ADC": "ADC",
    "BOTTOM": "ADC",
    "SUPPORT": "SUPPORT",
    "UTILITY": "SUPPORT",
    "top": "TOP",
    "jungle": "JUNGLE",
    "mid": "MID",
    "middle": "MID",
    "adc": "ADC",
    "bottom": "ADC",
    "support": "SUPPORT",
    "utility": "SUPPORT",
}


class _LoadoutSignals(QObject):
    loaded = Signal(str, dict)


class SelectedChampionCard(QFrame):
    clicked = Signal(str)

    def __init__(self):
        super().__init__()
        self._champion = ""
        self.setObjectName("HeroCard")
        self.setMinimumHeight(188)
        self.setCursor(Qt.PointingHandCursor)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(12)

        self.avatar = QLabel("")
        self.avatar.setFixedSize(56, 56)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setObjectName("HeroAvatar")
        root.addWidget(self.avatar)

        box = QVBoxLayout()
        box.setSpacing(6)
        self.title = QLabel("")
        self.title.setObjectName("HeroName")
        self.runes = QLabel("符文：等待加载")
        self.runes.setObjectName("HeroTags")
        self.runes.setWordWrap(True)
        self.core = QLabel("核心装：等待加载")
        self.core.setObjectName("HeroTags")
        self.core.setWordWrap(True)
        self.situational = QLabel("调整：等待加载")
        self.situational.setObjectName("MutedText")
        self.situational.setWordWrap(True)
        box.addWidget(self.title)
        box.addWidget(self.runes)
        box.addWidget(self.core)
        box.addWidget(self.situational)
        root.addLayout(box, 1)

    def render_base(self, champion: str, index: int, role: str):
        key = champion_key(champion)
        self._champion = key
        name = champion_display_name(key)
        self.title.setText(f"{index}. {name or key}　{ROLE_TO_LABEL.get(role, role or '未知位置')}")
        self._set_avatar(key, name)
        self.runes.setText("符文：加载中，不影响推荐页")
        self.core.setText("核心装：加载中")
        self.situational.setText("调整：根据敌方阵容计算中")

    def render_loadout(self, payload: dict):
        rune = payload.get("rune", {}) or {}
        build = payload.get("build", {}) or {}

        primary = rune_zh(rune.get("primary", ""))
        keystone = rune_zh(rune.get("keystone", ""))
        primary_runes = [item for item in (rune.get("runes", []) or []) if item]
        primary_minors = " / ".join(runes_zh(primary_runes[1:4])) or "暂无"
        secondary_tree = rune_zh(rune.get("secondary_tree", ""))
        secondary = " / ".join(runes_zh(rune.get("secondary", []))) or "暂无"
        stat_shards = " / ".join(runes_zh(rune.get("stat_shards", []))) or "暂无"
        tree_text = primary or "主系"
        secondary_text = f"{secondary_tree}：" if secondary_tree else "副系："
        self.runes.setText(
            f"符文：{tree_text} / {keystone}\n"
            f"主系：{primary_minors}\n"
            f"{secondary_text}{secondary}\n"
            f"小属性：{stat_shards}"
        )

        core = (build.get("core_build", []) or [{}])[0]
        core_items = " → ".join(items_zh(core.get("items", []))) or "暂无"
        stats = []
        if core.get("winrate") is not None:
            stats.append(f"胜率 {core.get('winrate')}%")
        if core.get("games"):
            stats.append(f"样本 {core.get('games')}")
        self.core.setText("核心装：" + core_items + (f"（{' / '.join(stats)}）" if stats else ""))

        situational = build.get("situational", []) or []
        if situational:
            first = situational[0]
            items = " / ".join(items_zh(first.get("items", [])))
            self.situational.setText(f"调整：{items}\n原因：{first.get('reason', '')}")
        else:
            self.situational.setText("调整：暂无阵容适配建议")

    def render_error(self):
        self.runes.setText("符文：暂无在线数据")
        self.core.setText("核心装：暂无在线数据")
        self.situational.setText("调整：网络失败时仍可先按推荐页完成 BP")

    def _set_avatar(self, key: str, display_name: str):
        icon_path = champion_icon_path(key) or champion_icon_path(display_name)
        if icon_path:
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                self.avatar.setText("")
                self.avatar.setPixmap(
                    pixmap.scaled(self.avatar.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                )
                return
        self.avatar.clear()
        self.avatar.setText((display_name or key or "?")[:2])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._champion:
            self.clicked.emit(self._champion)
            return
        super().mousePressEvent(event)


class SelectedChampionsPage(QWidget):
    def __init__(self):
        super().__init__()
        self._signature = ""
        self._loading_signature = ""
        self._last_state: dict = {}
        self._manual_champions: list[str] = []
        self._cards: dict[str, SelectedChampionCard] = {}
        self._loadouts: dict[str, dict] = {}
        self._roles_by_champion: dict[str, str] = {}
        self._champion_data = self._load_json(ROOT / "champion_data.json")
        self._role_data = self._load_json(ROOT / "data" / "role_data.json")
        self._meta_data = self._load_json(ROOT / "data" / "16.13" / "meta_data.json")
        self._detail_builder = HeroDetailContextBuilder()
        self._signals = _LoadoutSignals()
        self._signals.loaded.connect(self._on_loaded)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget{background:transparent;border:none;}")
        root.addWidget(self.stack, 1)

        self.list_page = QWidget()
        layout = QVBoxLayout(self.list_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("已选英雄")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        hint = QLabel("符文和出装放在这里后台加载，避免拖慢英雄推荐页；已选英雄即使从推荐列表过滤掉，也能在这里查看。")
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        search_row = QHBoxLayout()
        self.search = HeroSearchBar()
        self.search.setPlaceholderText("手动添加已选英雄：输入中文名或英文名，回车添加")
        self.search.hero_selected.connect(self.add_manual_champion)
        search_row.addWidget(self.search, 1)
        clear_button = QPushButton("清空手动")
        clear_button.clicked.connect(self.clear_manual_champions)
        search_row.addWidget(clear_button)
        layout.addLayout(search_row)

        self.status = QLabel("等待识别己方已选英雄")
        self.status.setObjectName("CoachGrades")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{border:none;background:transparent}")
        self.container = QWidget()
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(10)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)

        self.detail = HeroDetailPanel()
        self.detail.closed.connect(self._restore_list)
        self.stack.addWidget(self.list_page)
        self.stack.addWidget(self.detail)
        self.stack.setCurrentWidget(self.list_page)

    def render(self, state: dict):
        self._last_state = state or {}
        ally = self._combined_champions(state)
        enemy = [champion_key(item) for item in (state.get("enemy", []) or []) if champion_key(item)]
        role = str(state.get("role") or state.get("target_role") or "")
        roles_by_champion = self._resolve_team_roles(ally, role)
        signature = "|".join(ally) + "::" + "|".join(enemy) + "::" + "|".join(
            roles_by_champion.get(champion, "") for champion in ally
        )
        if signature == self._signature:
            return
        self._signature = signature
        self._roles_by_champion = roles_by_champion
        self._render_cards(ally, roles_by_champion)
        if not ally:
            self.status.setText("等待识别己方已选英雄")
            return
        self.status.setText(f"已识别己方 {len(ally)} 个英雄，正在后台加载符文和出装...")
        self._start_loading(signature, ally, enemy, roles_by_champion)

    def add_manual_champion(self, champion: str):
        key = champion_key(champion)
        if not key:
            self.status.setText("未找到该英雄，请换中文名或英文名再试。")
            return
        if key not in self._manual_champions:
            self._manual_champions.append(key)
        self.search.clear()
        self._signature = ""
        self.render(self._last_state or {})
        self.status.setText(f"已手动添加：{champion_display_name(key)}")

    def clear_manual_champions(self):
        self._manual_champions = []
        self._signature = ""
        self.render(self._last_state or {})

    def _combined_champions(self, state: dict) -> list[str]:
        detected = [champion_key(item) for item in ((state or {}).get("ally", []) or []) if champion_key(item)]
        return list(dict.fromkeys(detected + self._manual_champions))

    def _render_cards(self, ally: list[str], roles_by_champion: dict[str, str]):
        self._clear_layout()
        self._cards = {}
        for index, champion in enumerate(ally, start=1):
            card = SelectedChampionCard()
            card.render_base(champion, index, roles_by_champion.get(champion, ""))
            card.clicked.connect(self.open_detail)
            self._cards[champion] = card
            self.card_layout.addWidget(card)
        self.card_layout.addStretch()
        self._loadouts = {champion: payload for champion, payload in self._loadouts.items() if champion in ally}

    def _start_loading(self, signature: str, ally: list[str], enemy: list[str], roles_by_champion: dict[str, str]):
        if signature == self._loading_signature:
            return
        self._loading_signature = signature

        def worker():
            try:
                client = LolalyticsClient(patch="16.13")
                build_engine = BuildRecommendationEngine(client)
                rune_engine = RuneRecommendationEngine(client)
                for champion in ally:
                    champion_role = roles_by_champion.get(champion, "")
                    payload = {
                        "rune": rune_engine.recommend(champion, champion_role, enemy),
                        "build": build_engine.recommend(champion, champion_role, enemy),
                    }
                    self._signals.loaded.emit(champion, payload)
            except Exception:
                for champion in ally:
                    self._signals.loaded.emit(champion, {"error": True})

        threading.Thread(target=worker, daemon=True).start()

    def _on_loaded(self, champion: str, payload: dict):
        self._loadouts[champion] = payload
        card = self._cards.get(champion)
        if not card:
            return
        if payload.get("error"):
            card.render_error()
        else:
            card.render_loadout(payload)
        self.status.setText("符文和出装加载完成，可在本页慢慢查看。")

    def open_detail(self, champion: str):
        key = champion_key(champion)
        if not key:
            return
        app = QApplication.instance()
        if app is not None:
            app.setProperty("last_viewed_champion", key)
        context = self._detail_builder.build(
            key,
            current_state={**self._last_state, "role": self._roles_by_champion.get(key, "")},
            include_online=False,
            loadout_payload=self._loadouts.get(key),
        )
        self.detail.render_detail(context)
        self.stack.setCurrentWidget(self.detail)

    def _restore_list(self):
        self.stack.setCurrentWidget(self.list_page)
        self.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.stack.currentWidget() == self.detail:
            self.detail.hide_panel()
            return
        super().keyPressEvent(event)

    def _clear_layout(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _resolve_team_roles(self, champions: list[str], fallback_role: str = "") -> dict[str, str]:
        return {
            champion: self._primary_role(champion, fallback_role)
            for champion in champions
        }

    def _primary_role(self, champion: str, fallback_role: str = "") -> str:
        key = champion if champion in self._champion_data else champion_key(champion)
        scores: dict[str, float] = {}

        role_payload = self._role_data.get(key, {})
        for role, value in role_payload.items():
            normalized = ROLE_ALIASES.get(str(role), "")
            if normalized:
                scores[normalized] = max(scores.get(normalized, 0.0), float(value or 0))

        meta_roles = self._meta_data.get("champions", {}).get(key, {}).get("roles", {})
        for role, payload in meta_roles.items():
            normalized = ROLE_ALIASES.get(str(role), "")
            if not normalized:
                continue
            pickrate = self._safe_float(payload.get("pickrate", payload.get("pick_rate", 0)))
            games = self._safe_float(payload.get("games", 0))
            scores[normalized] = max(scores.get(normalized, 0.0), pickrate * 10 + min(games / 1000, 20))

        for index, role in enumerate(self._champion_data.get(key, {}).get("roles", [])):
            normalized = ROLE_ALIASES.get(str(role), "")
            if normalized:
                scores[normalized] = max(scores.get(normalized, 0.0), 80 - index * 12)

        if scores:
            return max(scores.items(), key=lambda item: item[1])[0]
        return ROLE_ALIASES.get(str(fallback_role), str(fallback_role or "").upper())

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _load_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
        except Exception:
            return {}

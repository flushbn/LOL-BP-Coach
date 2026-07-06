import json, time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
MATCH_SESSIONS_PATH = ROOT / "data" / "match_sessions.json"
PLAYER_PROFILE_PATH = ROOT / "data" / "player_profile.json"

# Champion archetype classification
ARCHETYPE_MAP = {
    "LeeSin": "节奏型", "Vi": "节奏型", "XinZhao": "节奏型", "JarvanIV": "节奏型",
    "Nidalee": "刷野型", "Graves": "刷野型", "Karthus": "刷野型", "MasterYi": "刷野型", "BelVeth": "刷野型",
    "Sejuani": "开团型", "Zac": "开团型", "Amumu": "开团型", "Rammus": "开团型",
    "Malphite": "坦克型", "Ornn": "坦克型", "Sion": "坦克型", "ChoGath": "坦克型",
    "Zed": "刺客型", "Akali": "刺客型", "Talon": "刺客型", "KhaZix": "刺客型", "Rengar": "刺客型",
    "Darius": "战士型", "Sett": "战士型", "Aatrox": "战士型", "Renekton": "战士型",
    "Ahri": "法师型", "Syndra": "法师型", "Viktor": "法师型", "Orianna": "法师型",
    "Janna": "软辅型", "Sona": "软辅型", "Lulu": "软辅型", "Milio": "软辅型", "Nami": "软辅型",
    "Leona": "硬辅型", "Nautilus": "硬辅型", "Thresh": "硬辅型", "Alistar": "硬辅型", "Rell": "硬辅型",
}

def _load_sessions() -> List[Dict]:
    try:
        if not MATCH_SESSIONS_PATH.exists():
            return []
        raw = MATCH_SESSIONS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else []
        return data if isinstance(data, list) else []
    except Exception:
        return []

class PlayerAnalytics:
    def __init__(self):
        self._sessions: List[Dict] = _load_sessions()

    def refresh(self):
        self._sessions = _load_sessions()

    # === 1. Overall Stats ===
    def get_overall_stats(self) -> Dict:
        total = len(self._sessions)
        wins = sum(1 for s in self._sessions if s.get("result") == "WIN")
        wr = round(wins / total * 100, 1) if total > 0 else 0.0

        # Recent 30 games
        recent30 = self._sessions[-30:] if total >= 30 else self._sessions
        wins30 = sum(1 for s in recent30 if s.get("result") == "WIN")
        wr30 = round(wins30 / len(recent30) * 100, 1) if recent30 else 0.0

        # Recent 7 days
        now = time.time()
        week_ago = now - 7 * 86400
        week_games = [s for s in self._sessions if s.get("timestamp", 0) >= week_ago]
        wins_w = sum(1 for s in week_games if s.get("result") == "WIN")
        wr_w = round(wins_w / len(week_games) * 100, 1) if week_games else 0.0

        return {
            "games": total,
            "wins": wins,
            "winrate": wr,
            "recent30_wr": wr30,
            "recent7d_wr": wr_w,
        }

    # === 2. Hero Pool ===
    def get_hero_pool(self, top_n: int = 10) -> List[Dict]:
        heroes: Dict[str, Dict] = {}
        for s in self._sessions:
            h = s.get("hero", "")
            if not h:
                continue
            if h not in heroes:
                heroes[h] = {"games": 0, "wins": 0, "last_played": 0}
            heroes[h]["games"] += 1
            if s.get("result") == "WIN":
                heroes[h]["wins"] += 1
            ts = s.get("timestamp", 0)
            if ts > heroes[h]["last_played"]:
                heroes[h]["last_played"] = ts

        pool = []
        for h, d in heroes.items():
            wr = round(d["wins"] / d["games"] * 100, 1) if d["games"] > 0 else 0.0
            pool.append({
                "champion": h,
                "games": d["games"],
                "wins": d["wins"],
                "winrate": wr,
                "last_played": d["last_played"],
            })

        pool.sort(key=lambda x: -x["games"])
        return pool[:top_n]

    # === 3. Position Analysis ===
    def get_position_analysis(self) -> Dict:
        positions: Dict[str, Dict] = {}
        for s in self._sessions:
            p = s.get("position", "")
            if not p:
                continue
            if p not in positions:
                positions[p] = {"games": 0, "wins": 0}
            positions[p]["games"] += 1
            if s.get("result") == "WIN":
                positions[p]["wins"] += 1

        results = {}
        best = {"pos": "", "wr": 0.0}
        worst = {"pos": "", "wr": 100.0}
        for p, d in positions.items():
            wr = round(d["wins"] / d["games"] * 100, 1) if d["games"] > 0 else 0.0
            results[p] = {"games": d["games"], "wins": d["wins"], "winrate": wr}
            if d["games"] >= 3:  # minimum sample
                if wr > best["wr"]:
                    best = {"pos": p, "wr": wr}
                if wr < worst["wr"]:
                    worst = {"pos": p, "wr": wr}

        return {
            "positions": results,
            "best": best,
            "worst": worst if worst["pos"] else {"pos": "", "wr": 0.0},
        }

    # === 4. Trend Analysis ===
    def get_trend(self) -> Dict:
        total = len(self._sessions)
        segments = [10, 20, 30]
        result = {}
        for n in segments:
            seg = self._sessions[-n:] if total >= n else self._sessions
            wins = sum(1 for s in seg if s.get("result") == "WIN")
            wr = round(wins / len(seg) * 100, 1) if seg else 0.0
            result[f"last{n}"] = {"games": len(seg), "wins": wins, "winrate": wr}

        # Trend judgment: compare last10 vs last30
        last10_wr = result.get("last10", {}).get("winrate", 0)
        last30_wr = result.get("last30", {}).get("winrate", 0)
        if last10_wr >= last30_wr + 5:
            trend = "状态上升"
        elif last10_wr <= last30_wr - 5:
            trend = "状态下降"
        else:
            trend = "状态稳定"

        result["trend"] = trend
        return result

    # === 5. Hero Recommendation ===
    def get_hero_insights(self) -> Dict:
        heroes = self.get_hero_pool(50)
        core = []
        caution = []
        for h in heroes:
            if h["games"] >= 10 and h["winrate"] >= 60:
                core.append({**h, "label": "核心英雄"})
            elif h["games"] >= 10 and h["winrate"] <= 40:
                caution.append({**h, "label": "谨慎选择"})
            elif h["games"] >= 5 and h["winrate"] >= 65:
                core.append({**h, "label": "高胜率英雄"})
        core.sort(key=lambda x: -x["winrate"])
        caution.sort(key=lambda x: x["winrate"])
        return {"core": core[:5], "caution": caution[:5]}

    # === 6. Style Analysis ===
    def get_style(self) -> Dict:
        arch_counts: Dict[str, int] = {}
        arch_wins: Dict[str, int] = {}
        for s in self._sessions:
            h = s.get("hero", "")
            arch = ARCHETYPE_MAP.get(h, "其他")
            arch_counts[arch] = arch_counts.get(arch, 0) + 1
            if s.get("result") == "WIN":
                arch_wins[arch] = arch_wins.get(arch, 0) + 1

        sorted_archs = sorted(arch_counts.items(), key=lambda x: -x[1])
        primary = sorted_archs[0][0] if sorted_archs else "未识别"

        # Get position -> style mapping
        pos = self.get_position_analysis()
        best_pos = pos["best"]["pos"]
        if primary in ("节奏型", "刷野型", "开团型"):
            style_desc = f"偏{primary}{best_pos}"
        elif primary in ("刺客型", "战士型"):
            style_desc = f"偏{primary}"
        elif primary in ("法师型",):
            style_desc = f"偏{primary}中单"
        elif primary in ("软辅型", "硬辅型"):
            style_desc = f"偏{primary}"
        else:
            style_desc = primary

        return {
            "primary_style": primary,
            "style_description": style_desc,
            "archetypes": [{"name": a, "count": c} for a, c in sorted_archs[:5]],
            "best_position": best_pos,
        }

    # === 7. Player Insight (for recommendation engine) ===
    def get_player_insight(self) -> Dict:
        pool = self.get_hero_pool(50)
        core = [h["champion"] for h in pool if h["games"] >= 10 and h["winrate"] >= 55]
        weak = [h["champion"] for h in pool if h["games"] >= 5 and h["winrate"] <= 40]
        favorites = [h["champion"] for h in pool[:5]]
        return {
            "favorite_heroes": favorites,
            "core_pool": core,
            "weak_pool": weak,
        }

# Singleton
_analytics: Optional[PlayerAnalytics] = None

def get_analytics() -> PlayerAnalytics:
    global _analytics
    if _analytics is None:
        _analytics = PlayerAnalytics()
    return _analytics

def get_player_insight() -> Dict:
    return get_analytics().get_player_insight()


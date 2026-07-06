"""Player Profile — track player performance history."""
import json, time
from pathlib import Path
from typing import Dict, Optional, List

class PlayerProfile:
    def __init__(self, profile_path=None, sessions_path=None):
        base = Path(__file__).resolve().parent.parent
        self._profile_path = profile_path or (base / "data" / "player_profile.json")
        self._sessions_path = sessions_path or (base / "data" / "match_sessions.json")
        self._profile = {}
        self.load()

    def load(self):
        try:
            if self._profile_path.exists():
                self._profile = json.loads(self._profile_path.read_text(encoding="utf-8"))
            else:
                self._profile = {}
        except:
            self._profile = {}

    def save(self):
        self._profile_path.parent.mkdir(parents=True, exist_ok=True)
        self._profile_path.write_text(json.dumps(self._profile, ensure_ascii=False, indent=2), encoding="utf-8")

    def import_from_sessions(self, sessions_path=None):
        sp = sessions_path or self._sessions_path
        try:
            if not sp.exists():
                return
            sessions = json.loads(sp.read_text(encoding="utf-8"))
        except:
            return
        agg = {}
        now = int(time.time())
        for s in sessions:
            hero = s.get("hero", "")
            if not hero:
                continue
            if hero not in agg:
                agg[hero] = {"games": 0, "wins": 0, "last_played": 0}
            agg[hero]["games"] += 1
            if s.get("result", "").upper() == "WIN":
                agg[hero]["wins"] += 1
            ts = s.get("timestamp", 0)
            if ts > agg[hero]["last_played"]:
                agg[hero]["last_played"] = ts
        for champ, data in agg.items():
            if champ not in self._profile:
                self._profile[champ] = {}
            self._profile[champ]["games"] = self._profile[champ].get("games", 0) + data["games"]
            self._profile[champ]["wins"] = self._profile[champ].get("wins", 0) + data["wins"]
            if data["last_played"] > self._profile[champ].get("last_played", 0):
                self._profile[champ]["last_played"] = data["last_played"]
        self.save()

    def get_comfort(self, champion, min_games=3):
        info = self._profile.get(champion, {})
        games = info.get("games", 0)
        wins = info.get("wins", 0)
        last_played = info.get("last_played", 0)
        if games < min_games:
            return {"comfort_bonus": 0, "comfort_reason": "", "games": games, "winrate": 0.0}
        winrate = round(wins / games * 100, 1) if games > 0 else 0.0
        if games >= 100: gs = 40
        elif games >= 50: gs = 35
        elif games >= 30: gs = 30
        elif games >= 20: gs = 25
        elif games >= 10: gs = 20
        elif games >= 5: gs = 15
        else: gs = 10
        if winrate >= 65: ws = 40
        elif winrate >= 60: ws = 35
        elif winrate >= 55: ws = 30
        elif winrate >= 50: ws = 20
        elif winrate >= 45: ws = 10
        elif winrate >= 40: ws = 0
        else: ws = -10
        days_ago = (time.time() - last_played) / 86400 if last_played > 0 else 999
        if days_ago <= 7: rs = 20
        elif days_ago <= 14: rs = 15
        elif days_ago <= 30: rs = 10
        elif days_ago <= 90: rs = 5
        else: rs = 0
        total = gs + ws + rs
        if total >= 80: bonus, reason = 5, "你的高胜率英雄"
        elif total >= 60: bonus, reason = 4, "你的高胜率英雄"
        elif total >= 45: bonus, reason = 3, "熟练度较高"
        elif total >= 30: bonus, reason = 2, "最近常用英雄"
        elif total >= 15: bonus, reason = 1, "有一定熟练度"
        elif total >= 0: bonus, reason = 0, ""
        elif total >= -5: bonus, reason = -1, "近期胜率偏低"
        else: bonus, reason = -2, "熟练度不足"
        return {"comfort_bonus": bonus, "comfort_reason": reason, "games": games, "winrate": winrate}

    def get_all_comfort(self):
        results = []
        for champ in self._profile:
            info = self.get_comfort(champ)
            if info["games"] >= 1:
                results.append({"champion": champ, "games": info["games"],
                    "winrate": info["winrate"], "bonus": info["comfort_bonus"],
                    "reason": info["comfort_reason"]})
        results.sort(key=lambda x: (-x["bonus"], -x["games"]))
        return results

    @property
    def profile(self):
        return self._profile

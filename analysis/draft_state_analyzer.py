from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class DraftStateAnalyzer:
    def __init__(self):
        self._profiles = {}
        try:
            path = ROOT / "data" / "champion_draft_profile.json"
            with path.open("r", encoding="utf-8") as handle:
                self._profiles = json.load(handle)
        except Exception:
            pass

    def analyze(self, ally_count, enemy_count) -> dict:
        slot = ally_count + enemy_count + 1
        is_blind = slot <= 2
        is_counter = slot >= 7
        is_last = slot >= 10
        phase = "blind" if is_blind else ("counter" if is_counter else "flex")
        return {"phase": phase, "slot": slot, "is_blind": is_blind, "is_counter": is_counter, "is_last": is_last}

    def get_draft_score(self, champ, draft_state):
        profile = self._profiles.get(champ, {"blind_pick": 5, "counter_pick": 5})
        if draft_state["is_blind"]:
            raw = profile.get("blind_pick", 5) - 5
        elif draft_state["is_counter"]:
            raw = profile.get("counter_pick", 5) - 5
        else:
            return 0
        bonus = round(raw * 0.5)
        return max(-3, min(3, bonus))

    def get_draft_reason(self, champ, draft_state):
        if draft_state["is_blind"]:
            return "先手位，英雄稳定且不易被针对"
        if draft_state["is_last"]:
            return "最后康特位，Counter价值最大化"
        if draft_state["is_counter"]:
            return "后手位，更容易发挥针对价值"
        return ""

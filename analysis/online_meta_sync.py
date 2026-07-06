from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.lolalytics_client import LolalyticsClient

REPORT_PATH = ROOT / "reports" / "meta_sync_v1_report.md"
ROLE_MAP = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MID": "middle",
    "ADC": "bottom",
    "SUPPORT": "support",
}
CHAMPION_ROLE_MAP = {
    "top": "TOP",
    "jungle": "JUNGLE",
    "mid": "MID",
    "middle": "MID",
    "adc": "ADC",
    "bottom": "ADC",
    "support": "SUPPORT",
    "utility": "SUPPORT",
}
ROLE_DATA_MAP = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "MIDDLE": "MID",
    "BOTTOM": "ADC",
    "UTILITY": "SUPPORT",
}
REQUIRED_BY_ROLE = {
    "TOP": ["Malphite"],
    "JUNGLE": ["LeeSin"],
    "MID": ["Yasuo"],
    "ADC": ["Kaisa"],
    "SUPPORT": ["Nautilus"],
}


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def canonical_name(name: str) -> str:
    return "".join(ch for ch in str(name) if ch.isalnum())


class OnlineMetaSync:
    def __init__(self, patch: str = "16.13", tier: str = "emerald", limit_per_role: int = 20):
        self.patch = patch
        self.tier = tier
        self.limit_per_role = limit_per_role
        self.client = LolalyticsClient(patch=patch)
        self.output_dir = ROOT / "data" / patch
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.known_champions = self._load_known_champions()

    def build_all(self) -> dict[str, Any]:
        started = time.time()
        meta = self.build_meta()
        counters = self.build_counters(meta)
        synergy = self.build_synergy(meta, counters)

        self._write_json("meta_data.json", meta)
        self._write_json("counter_data.json", counters)
        self._write_json("synergy_data.json", synergy)
        self._write_report(meta, counters, synergy, elapsed=time.time() - started)
        return {
            "patch": self.patch,
            "meta_roles": len(meta["roles"]),
            "meta_champions": len(meta["champions"]),
            "counter_champions": len(counters["champions"]),
            "synergy_champions": len(synergy["champions"]),
            "output_dir": str(self.output_dir),
        }

    def build_full_meta(
        self,
        progress: Callable[[int, str], None] | None = None,
        include_offrole_threshold: int = 10,
    ) -> dict[str, Any]:
        """Fetch current-patch Lolalytics meta for every known champion.

        This updates meta only. Full Counter/Synergy would require tens of
        thousands of matchup requests and remains a separate, narrower sync.
        """
        progress = progress or (lambda value, message: None)
        started = time.time()
        champion_roles = self._load_champion_roles(include_offrole_threshold)
        total = sum(len(roles) for roles in champion_roles.values()) or 1
        done = 0

        roles: dict[str, dict[str, Any]] = {role: {} for role in ROLE_MAP}
        champions: dict[str, Any] = {}
        failed: list[dict[str, str]] = []

        for champion, role_list in sorted(champion_roles.items()):
            for role in role_list:
                lane = ROLE_MAP.get(role)
                if not lane:
                    continue
                stats = self.client.get_champion_stats(champion, lane=lane, tier=self.tier)
                done += 1
                progress(
                    min(95, round(done / total * 95)),
                    f"同步 16.13 实时数据: {champion} {role} ({done}/{total})",
                )
                if not stats:
                    failed.append({"champion": champion, "role": role})
                    continue

                entry = self._meta_entry(stats)
                entry["champion"] = champion
                entry["display_name"] = champion
                entry["role"] = role
                entry["source"] = "lolalytics_live"
                roles.setdefault(role, {})[champion] = entry

                champ_entry = champions.setdefault(champion, {"roles": {}, "best_role": role, "best_meta_score": -1})
                champ_entry["roles"][role] = entry
                if entry["meta_score"] >= champ_entry.get("best_meta_score", -1):
                    champ_entry["best_role"] = role
                    champ_entry["best_meta_score"] = entry["meta_score"]

        meta = {
            "patch": self.patch,
            "source": "lolalytics_live_full",
            "tier": self.tier,
            "generated_at": int(time.time()),
            "roles": roles,
            "champions": champions,
            "failed": failed,
            "coverage": {
                "known_champions": len(champion_roles),
                "synced_champions": len(champions),
                "synced_role_entries": sum(len(role_data) for role_data in roles.values()),
                "failed_role_entries": len(failed),
            },
        }
        self._write_json("meta_data.json", meta)
        self._write_full_meta_report(meta, elapsed=time.time() - started)
        return {"patch": self.patch, "output_dir": str(self.output_dir), **meta["coverage"]}

    def build_full_detail_data(
        self,
        meta: dict[str, Any] | None = None,
        progress: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        progress = progress or (lambda value, message: None)
        started = time.time()
        meta = meta or self._read_json("meta_data.json")
        if not meta.get("champions"):
            meta = self.build_full_meta(progress=lambda value, message: progress(round(value * 0.45), message))

        counters = self.build_full_counters(meta, progress=lambda value, message: progress(45 + round(value * 0.35), message))
        synergy = self.build_full_synergy(meta)
        self._write_json("counter_data.json", counters)
        self._write_json("synergy_data.json", synergy)
        self._write_full_detail_report(meta, counters, synergy, elapsed=time.time() - started)
        progress(100, "全英雄克制 / 协同数据已完成")
        return {
            "patch": self.patch,
            "output_dir": str(self.output_dir),
            "counter_champions": len(counters.get("champions", {})),
            "counter_pairs": sum(len(pairs) for pairs in counters.get("champions", {}).values()),
            "synergy_champions": len(synergy.get("champions", {})),
            "synergy_pairs": sum(len(pairs) for pairs in synergy.get("champions", {}).values()),
        }

    def build_full_counters(
        self,
        meta: dict[str, Any],
        progress: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        progress = progress or (lambda value, message: None)
        champions = sorted(meta.get("champions", {}).keys() or self._load_champion_roles().keys())
        total = len(champions) or 1
        result: dict[str, dict[str, Any]] = {}
        failed: list[dict[str, str]] = []

        for index, champion in enumerate(champions, 1):
            role = self._best_role_for_champion(champion, meta)
            lane = ROLE_MAP.get(role, "middle")
            progress(round(index / total * 100), f"更新克制数据: {champion} {role} ({index}/{total})")
            rows = self.client.get_counters(champion, lane=lane, tier=self.tier) or []
            pairs: dict[str, Any] = {}
            for row in rows:
                opponent = self._resolve_champion(row.get("champion", "")) or self._resolve_counter_name(row.get("champion", ""))
                if not opponent or opponent == champion:
                    continue
                delta = float(row.get("delta", 0.0) or 0.0)
                pairs[opponent] = {
                    "role": role,
                    "winrate_delta": round(delta, 2),
                    "counter_score": round(clamp(50 + delta * 5), 2),
                    "games": int(row.get("games", 0) or 0),
                    "source": "lolalytics_counters",
                }
            if not pairs:
                pairs = self._build_counter_matchup_fallback(champion, role, lane, meta)
            if not pairs:
                failed.append({"champion": champion, "role": role})
            result[champion] = pairs

        return {
            "patch": self.patch,
            "source": "lolalytics_counters_full",
            "tier": self.tier,
            "generated_at": int(time.time()),
            "coverage": {
                "champions": len(champions),
                "synced_champions": len([champion for champion, pairs in result.items() if pairs]),
                "pairs": sum(len(pairs) for pairs in result.values()),
                "failed": len(failed),
            },
            "failed": failed,
            "champions": result,
        }

    def _build_counter_matchup_fallback(
        self,
        champion: str,
        role: str,
        lane: str,
        meta: dict[str, Any],
    ) -> dict[str, Any]:
        pairs: dict[str, Any] = {}
        opponents = sorted(
            meta.get("roles", {}).get(role, {}).items(),
            key=lambda item: (
                float(item[1].get("games", 0) or 0),
                float(item[1].get("pickrate", 0) or 0),
            ),
            reverse=True,
        )
        for opponent, _ in opponents[:20]:
            if opponent == champion:
                continue
            matchup = self.client.get_matchup(champion, opponent, lane=lane, tier=self.tier)
            if not matchup:
                continue
            delta = float(matchup.get("delta", 0.0) or 0.0)
            games = int(matchup.get("games", 0) or 0)
            pairs[opponent] = {
                "role": role,
                "winrate_delta": round(delta, 2),
                "counter_score": round(clamp(50 + delta * 5), 2),
                "games": games,
                "source": "lolalytics_matchup_fallback",
            }
        return pairs

    def build_full_synergy(self, meta: dict[str, Any]) -> dict[str, Any]:
        champion_data = self._read_json_from_path(ROOT / "champion_data.json")
        champions = sorted(set(meta.get("champions", {}).keys()) | set(champion_data.keys()))
        result: dict[str, dict[str, Any]] = {}
        for champion in champions:
            candidates = self._synergy_candidate_pool(champion, meta, champion_data)
            scored = []
            for ally in candidates:
                if ally == champion:
                    continue
                score, reason = self._tag_synergy(champion, ally, champion_data)
                if score <= 52:
                    continue
                score = round(min(82.0, score + self._meta_bonus(ally, meta)), 2)
                scored.append((ally, score, reason))
            scored.sort(key=lambda item: item[1], reverse=True)
            result[champion] = {
                ally: {
                    "synergy_score": score,
                    "sample": "tag_inferred",
                    "reason": reason,
                    "source": "tag_inferred_full",
                }
                for ally, score, reason in scored[:8]
            }
        return {
            "patch": self.patch,
            "source": "tag_inferred_full",
            "generated_at": int(time.time()),
            "coverage": {
                "champions": len(champions),
                "synced_champions": len([champion for champion, pairs in result.items() if pairs]),
                "pairs": sum(len(pairs) for pairs in result.values()),
            },
            "champions": result,
        }

    def build_meta(self) -> dict[str, Any]:
        roles: dict[str, dict[str, Any]] = {}
        champions: dict[str, Any] = {}
        for role, lane in ROLE_MAP.items():
            role_data: dict[str, Any] = {}
            tierlist = self.client.get_tierlist(lane=lane, tier=self.tier, limit=self.limit_per_role * 5) or []
            ordered_champions = []
            for item in tierlist:
                display_name = item.get("name", "")
                champion = self._resolve_champion(display_name)
                if not champion:
                    continue
                if champion not in ordered_champions:
                    ordered_champions.append(champion)
                if len(ordered_champions) >= self.limit_per_role:
                    break
            for required in REQUIRED_BY_ROLE.get(role, []):
                if required not in ordered_champions:
                    ordered_champions.append(required)
            for champion in ordered_champions:
                display_name = champion
                stats = self.client.get_champion_stats(champion, lane=lane, tier=self.tier)
                if not stats:
                    stats = {
                        "winrate": 50.0,
                        "pickrate": 0.0,
                        "banrate": 0.0,
                        "tier": item.get("tier", "Unknown"),
                        "games": 0,
                    }
                entry = self._meta_entry(stats)
                entry["champion"] = champion
                entry["display_name"] = display_name
                entry["role"] = role
                role_data[champion] = entry

                champ_entry = champions.setdefault(champion, {"roles": {}, "best_role": role, "best_meta_score": 0})
                champ_entry["roles"][role] = entry
                if entry["meta_score"] >= champ_entry["best_meta_score"]:
                    champ_entry["best_role"] = role
                    champ_entry["best_meta_score"] = entry["meta_score"]
            roles[role] = role_data

        return {
            "patch": self.patch,
            "source": "lolalytics",
            "tier": self.tier,
            "generated_at": int(time.time()),
            "roles": roles,
            "champions": champions,
        }

    def _load_known_champions(self) -> dict[str, str]:
        candidates = [
            ROOT / "data" / "zh_CN" / "champion.json",
            ROOT / "champion_data.json",
        ]
        known: dict[str, str] = {}
        for path in candidates:
            try:
                if not path.exists():
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
                champion_data = data.get("data", data)
                for champion_id, info in champion_data.items():
                    known[canonical_name(champion_id).lower()] = champion_id
                    if isinstance(info, dict):
                        for key in ("name", "title", "id"):
                            value = info.get(key)
                            if value:
                                known[canonical_name(value).lower()] = champion_id
            except Exception:
                continue
        return known

    def _load_champion_roles(self, include_offrole_threshold: int = 10) -> dict[str, list[str]]:
        champion_roles: dict[str, set[str]] = {}

        champion_path = ROOT / "champion_data.json"
        try:
            raw = json.loads(champion_path.read_text(encoding="utf-8")) if champion_path.exists() else {}
            for champion, payload in raw.items():
                for role in payload.get("roles", []):
                    mapped = CHAMPION_ROLE_MAP.get(str(role).lower())
                    if mapped:
                        champion_roles.setdefault(champion, set()).add(mapped)
        except Exception:
            pass

        role_path = ROOT / "data" / "role_data.json"
        try:
            raw_roles = json.loads(role_path.read_text(encoding="utf-8")) if role_path.exists() else {}
            for champion, role_payload in raw_roles.items():
                for riot_role, pct in role_payload.items():
                    mapped = ROLE_DATA_MAP.get(riot_role)
                    if mapped and float(pct or 0) >= include_offrole_threshold:
                        champion_roles.setdefault(champion, set()).add(mapped)
        except Exception:
            pass

        for champion in set(self.known_champions.values()):
            champion_roles.setdefault(champion, set())

        for champion, roles in list(champion_roles.items()):
            if not roles:
                roles.add("MID")

        return {champion: sorted(roles) for champion, roles in champion_roles.items()}

    def _resolve_champion(self, name: str) -> str:
        key = canonical_name(name).lower()
        return self.known_champions.get(key, "")

    def _resolve_counter_name(self, name: str) -> str:
        key = canonical_name(str(name).replace("&#39;", "").replace("&amp;", "and")).lower()
        aliases = {
            "wukong": "MonkeyKing",
            "monkeyking": "MonkeyKing",
            "tahmkench": "TahmKench",
            "aurelionsol": "AurelionSol",
            "jarvaniv": "JarvanIV",
            "leesin": "LeeSin",
            "xinzhao": "XinZhao",
            "masteryi": "MasterYi",
            "missfortune": "MissFortune",
            "twistedfate": "TwistedFate",
            "drmundo": "DrMundo",
            "kogmaw": "KogMaw",
            "reksai": "RekSai",
            "velkoz": "Velkoz",
            "chogath": "Chogath",
            "ksante": "KSante",
        }
        return aliases.get(key, self.known_champions.get(key, ""))

    def _best_role_for_champion(self, champion: str, meta: dict[str, Any]) -> str:
        champ_meta = meta.get("champions", {}).get(champion, {})
        best_role = champ_meta.get("best_role")
        if best_role in ROLE_MAP:
            return best_role
        role_entries = champ_meta.get("roles", {})
        if role_entries:
            return max(
                role_entries.items(),
                key=lambda item: (
                    float(item[1].get("games", 0) or 0),
                    float(item[1].get("pickrate", 0) or 0),
                ),
            )[0]
        roles = self._load_champion_roles().get(champion, [])
        return roles[0] if roles else "MID"

    def _synergy_candidate_pool(self, champion: str, meta: dict[str, Any], champion_data: dict[str, Any]) -> list[str]:
        role = self._best_role_for_champion(champion, meta)
        preferred = {
            "TOP": ["JUNGLE", "MID", "ADC", "SUPPORT"],
            "JUNGLE": ["MID", "SUPPORT", "TOP", "ADC"],
            "MID": ["JUNGLE", "SUPPORT", "TOP", "ADC"],
            "ADC": ["SUPPORT", "JUNGLE", "MID"],
            "SUPPORT": ["ADC", "JUNGLE", "MID"],
        }
        roles = preferred.get(role, ["JUNGLE", "MID", "SUPPORT", "ADC", "TOP"])
        candidates: list[str] = []
        for target_role in roles:
            role_rows = sorted(
                meta.get("roles", {}).get(target_role, {}).items(),
                key=lambda item: (
                    float(item[1].get("games", 0) or 0),
                    float(item[1].get("pickrate", 0) or 0),
                ),
                reverse=True,
            )
            candidates.extend(ally for ally, _ in role_rows[:40] if ally != champion)
        for ally, payload in champion_data.items():
            ally_roles = {
                CHAMPION_ROLE_MAP.get(str(role_name).lower())
                for role_name in payload.get("roles", [])
            }
            if ally != champion and ally_roles.intersection(roles):
                candidates.append(ally)
        return list(dict.fromkeys(candidates))

    def _tag_synergy(self, champion: str, ally: str, champion_data: dict[str, Any]) -> tuple[float, str]:
        tags = set(self._champion_payload(champion, champion_data).get("tags", []))
        ally_tags = set(self._champion_payload(ally, champion_data).get("tags", []))
        score = 50.0
        reasons: list[tuple[float, str]] = []
        if self._has_any(tags, "engage", "frontline", "tank", "cc") and self._has_any(ally_tags, "burst", "mage", "assassin", "dps", "marksman"):
            reasons.append((10, "先手控制 + 输出跟进"))
        if self._has_any(ally_tags, "engage", "frontline", "tank", "cc") and self._has_any(tags, "burst", "mage", "assassin", "dps", "marksman"):
            reasons.append((10, "控制链 + 爆发衔接"))
        if self._has_any(tags, "frontline", "tank", "fighter") and self._has_any(ally_tags, "marksman", "dps", "scaling"):
            reasons.append((8, "前排吸收 + 后排持续输出"))
        if self._has_any(ally_tags, "frontline", "tank", "fighter") and self._has_any(tags, "marksman", "dps", "scaling"):
            reasons.append((8, "前排保护 + 持续输出"))
        if self._has_any(tags, "support", "protect", "peel") and self._has_any(ally_tags, "marksman", "dps", "assassin"):
            reasons.append((7, "保护核心 + 输出空间"))
        if self._has_any(ally_tags, "support", "protect", "peel") and self._has_any(tags, "marksman", "dps", "assassin"):
            reasons.append((7, "保护核心 + 输出空间"))
        if ("ap" in tags and "ad" in ally_tags) or ("ad" in tags and "ap" in ally_tags):
            reasons.append((5, "伤害类型互补"))
        if self._has_any(tags, "engage", "assassin", "fighter") and self._has_any(ally_tags, "engage", "assassin", "fighter"):
            reasons.append((4, "进场节奏一致"))
        if not reasons:
            return score, "阵容标签一般"
        return min(78.0, score + sum(value for value, _ in reasons)), max(reasons, key=lambda item: item[0])[1]

    def _meta_bonus(self, champion: str, meta: dict[str, Any]) -> float:
        payload = meta.get("champions", {}).get(champion, {})
        return min(4.0, float(payload.get("best_meta_score", 0) or 0) / 15.0)

    @staticmethod
    def _champion_payload(champion: str, champion_data: dict[str, Any]) -> dict[str, Any]:
        aliases = {
            "FiddleSticks": "Fiddlesticks",
            "Fiddlesticks": "Fiddlesticks",
            "MonkeyKing": "MonkeyKing",
        }
        return champion_data.get(champion) or champion_data.get(aliases.get(champion, champion), {})

    @staticmethod
    def _has_any(tags: set[str], *names: str) -> bool:
        return any(name in tags for name in names)

    def build_counters(self, meta: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, dict[str, Any]] = {}
        for role, lane in ROLE_MAP.items():
            champions = list(meta["roles"].get(role, {}).keys())[: self.limit_per_role]
            for champion in champions:
                result.setdefault(champion, {})
                for opponent in champions:
                    if champion == opponent or opponent in result.get(champion, {}):
                        continue
                    matchup = self.client.get_matchup(champion, opponent, lane=lane, tier=self.tier)
                    delta = 0.0
                    games = 0
                    if matchup:
                        delta = float(matchup.get("delta", 0.0) or 0.0)
                        games = int(matchup.get("games", 0) or 0)
                    score = self._counter_score(delta, games)
                    reverse_score = self._counter_score(-delta, games)
                    result.setdefault(champion, {})[opponent] = {
                        "role": role,
                        "winrate_delta": round(delta, 2),
                        "counter_score": score,
                        "games": games,
                    }
                    result.setdefault(opponent, {})[champion] = {
                        "role": role,
                        "winrate_delta": round(-delta, 2),
                        "counter_score": reverse_score,
                        "games": games,
                    }
        return {
            "patch": self.patch,
            "source": "lolalytics_matchup",
            "generated_at": int(time.time()),
            "champions": result,
        }

    def build_synergy(self, meta: dict[str, Any], counters: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, dict[str, Any]] = {}
        jungle = list(meta["roles"].get("JUNGLE", {}).keys())[: self.limit_per_role]
        support = list(meta["roles"].get("SUPPORT", {}).keys())[: self.limit_per_role]
        for jungler in jungle:
            for support_champ in support:
                j_meta = meta["roles"]["JUNGLE"].get(jungler, {})
                s_meta = meta["roles"]["SUPPORT"].get(support_champ, {})
                expected = (float(j_meta.get("winrate", 50)) + float(s_meta.get("winrate", 50))) / 2
                pressure = self._shared_counter_pressure(jungler, support_champ, counters)
                inferred_together = expected + pressure
                synergy_delta = inferred_together - expected
                score = round(clamp(50 + synergy_delta * 5), 2)
                payload = {
                    "roles": ["JUNGLE", "SUPPORT"],
                    "expected_winrate": round(expected, 2),
                    "inferred_together_winrate": round(inferred_together, 2),
                    "synergy_score": score,
                    "sample": "pattern_inferred",
                }
                result.setdefault(jungler, {})[support_champ] = payload
                result.setdefault(support_champ, {})[jungler] = payload
        return {
            "patch": self.patch,
            "source": "lolalytics_matchup_pattern",
            "generated_at": int(time.time()),
            "champions": result,
        }

    def _meta_entry(self, stats: dict[str, Any]) -> dict[str, Any]:
        winrate = float(stats.get("winrate", 50.0) or 50.0)
        pickrate = float(stats.get("pickrate", 0.0) or 0.0)
        banrate = float(stats.get("banrate", 0.0) or 0.0)
        games = int(stats.get("games", 0) or 0)
        raw_score = winrate * 0.5 + pickrate * 0.3 + banrate * 0.2
        confidence = self._sample_confidence(games)
        meta_score = clamp(raw_score * confidence + 50 * (1 - confidence))
        return {
            "winrate": round(winrate, 2),
            "pickrate": round(pickrate, 2),
            "banrate": round(banrate, 2),
            "tier": stats.get("tier", "Unknown"),
            "games": games,
            "sample_confidence": confidence,
            "meta_score": round(meta_score, 2),
        }

    def _counter_score(self, delta: float, games: int) -> float:
        confidence = self._sample_confidence(games)
        adjusted_delta = delta * confidence
        return round(clamp(50 + adjusted_delta * 5), 2)

    def _sample_confidence(self, games: int) -> float:
        if games <= 0:
            return 0.0
        if games < 500:
            return max(0.25, games / 500 * 0.5)
        if games < 1500:
            return 0.75
        return 1.0

    def _shared_counter_pressure(self, a: str, b: str, counters: dict[str, Any]) -> float:
        a_pairs = counters.get("champions", {}).get(a, {})
        b_pairs = counters.get("champions", {}).get(b, {})
        shared = set(a_pairs).intersection(b_pairs)
        if not shared:
            return 0.0
        deltas = []
        for enemy in shared:
            a_delta = float(a_pairs[enemy].get("winrate_delta", 0) or 0)
            b_delta = float(b_pairs[enemy].get("winrate_delta", 0) or 0)
            deltas.append((a_delta + b_delta) / 2)
        if not deltas:
            return 0.0
        return clamp(statistics.mean(deltas), -5, 5)

    def _write_json(self, name: str, payload: dict[str, Any]):
        path = self.output_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_json(self, name: str) -> dict[str, Any]:
        return self._read_json_from_path(self.output_dir / name)

    @staticmethod
    def _read_json_from_path(path: Path) -> dict[str, Any]:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _write_report(self, meta: dict[str, Any], counters: dict[str, Any], synergy: dict[str, Any], elapsed: float):
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        all_meta = []
        for role, role_data in meta["roles"].items():
            for champion, entry in role_data.items():
                all_meta.append((champion, role, entry))
        all_meta.sort(key=lambda item: item[2].get("meta_score", 0), reverse=True)

        top_meta_lines = [
            f"| {i} | {champion} | {role} | {entry['meta_score']} | {entry['winrate']} | {entry['pickrate']} | {entry['games']} |"
            for i, (champion, role, entry) in enumerate(all_meta[:20], 1)
        ]

        top_role = list(meta["roles"].get("TOP", {}).keys())
        counter_lines = []
        if top_role:
            sample = top_role[0]
            pairs = counters["champions"].get(sample, {})
            for enemy, data in list(pairs.items())[:10]:
                counter_lines.append(f"| {sample} | {enemy} | {data['winrate_delta']} | {data['counter_score']} | {data['games']} |")

        synergy_lines = []
        jungle = next(iter(synergy["champions"].keys()), "")
        if jungle:
            for partner, data in list(synergy["champions"].get(jungle, {}).items())[:10]:
                synergy_lines.append(f"| {jungle} | {partner} | {data['synergy_score']} | {data['expected_winrate']} |")

        meta_scores = [entry["meta_score"] for _, _, entry in all_meta]
        counter_scores = [
            pair["counter_score"]
            for pairs in counters["champions"].values()
            for pair in pairs.values()
        ]
        synergy_scores = [
            pair["synergy_score"]
            for pairs in synergy["champions"].values()
            for pair in pairs.values()
        ]

        report = [
            "# Online Meta Sync V1 Report",
            "",
            f"- Patch: {self.patch}",
            "- Source: Lolalytics via analysis/lolalytics_client.py",
            f"- Elapsed: {elapsed:.1f}s",
            f"- Output: data/{self.patch}/",
            "",
            "## Top 20 Meta",
            "",
            "| # | Champion | Role | Meta | WR | PR | Games |",
            "|---|---|---|---:|---:|---:|---:|",
            *top_meta_lines,
            "",
            "## Counter Sample (Top Lane)",
            "",
            "| Champion | Opponent | Delta | Counter Score | Games |",
            "|---|---|---:|---:|---:|",
            *(counter_lines or ["| N/A | N/A | 0 | 50 | 0 |"]),
            "",
            "## Synergy Sample (Jungle + Support)",
            "",
            "| Jungler | Support | Synergy Score | Expected WR |",
            "|---|---|---:|---:|",
            *(synergy_lines or ["| N/A | N/A | 50 | 50 |"]),
            "",
            "## Data Distribution",
            "",
            f"- Meta count: {len(meta_scores)}, min={min(meta_scores) if meta_scores else 0}, max={max(meta_scores) if meta_scores else 0}",
            f"- Counter count: {len(counter_scores)}, min={min(counter_scores) if counter_scores else 0}, max={max(counter_scores) if counter_scores else 0}",
            f"- Synergy count: {len(synergy_scores)}, min={min(synergy_scores) if synergy_scores else 0}, max={max(synergy_scores) if synergy_scores else 0}",
            "",
            "## Quality Controls",
            "",
            "- Missing data defaults to 50-point neutral scoring.",
            "- Matchups with games < 500 are down-weighted.",
            "- All scores are clamped to 0-100.",
            "- Counter data is written bidirectionally.",
        ]
        REPORT_PATH.write_text("\n".join(report), encoding="utf-8")

    def _write_full_meta_report(self, meta: dict[str, Any], elapsed: float):
        report_path = ROOT / "reports" / "full_meta_sync_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        coverage = meta.get("coverage", {})
        lines = [
            "# Full Hero Meta Sync Report",
            "",
            f"- Patch: {meta.get('patch')}",
            f"- Source: {meta.get('source')}",
            f"- Tier: {meta.get('tier')}",
            f"- Known champions: {coverage.get('known_champions')}",
            f"- Synced champions: {coverage.get('synced_champions')}",
            f"- Synced role entries: {coverage.get('synced_role_entries')}",
            f"- Failed role entries: {coverage.get('failed_role_entries')}",
            f"- Elapsed seconds: {elapsed:.1f}",
            "",
            "## Failed Entries",
        ]
        failed = meta.get("failed", [])
        if failed:
            for item in failed[:300]:
                lines.append(f"- {item.get('champion')} {item.get('role')}")
        else:
            lines.append("- None")
        report_path.write_text("\n".join(lines), encoding="utf-8")

    def _write_full_detail_report(
        self,
        meta: dict[str, Any],
        counters: dict[str, Any],
        synergy: dict[str, Any],
        elapsed: float,
    ):
        report_path = ROOT / "reports" / "full_detail_data_sync_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        counter_coverage = counters.get("coverage", {})
        synergy_coverage = synergy.get("coverage", {})
        sample_champions = ["Annie", "MonkeyKing", "LeeSin", "Yasuo", "Kaisa", "Yuumi"]
        lines = [
            "# Full Hero Detail Data Sync Report",
            "",
            f"- Patch: {self.patch}",
            f"- Tier: {self.tier}",
            f"- Elapsed seconds: {elapsed:.1f}",
            f"- Output: data/{self.patch}/counter_data.json",
            f"- Output: data/{self.patch}/synergy_data.json",
            "",
            "## Coverage",
            "",
            f"- Meta champions: {len(meta.get('champions', {}))}",
            f"- Counter champions: {counter_coverage.get('synced_champions')} / {counter_coverage.get('champions')}",
            f"- Counter pairs: {counter_coverage.get('pairs')}",
            f"- Counter failed: {counter_coverage.get('failed')}",
            f"- Synergy champions: {synergy_coverage.get('synced_champions')} / {synergy_coverage.get('champions')}",
            f"- Synergy pairs: {synergy_coverage.get('pairs')}",
            "",
            "## Samples",
            "",
        ]
        for champion in sample_champions:
            counter_pairs = counters.get("champions", {}).get(champion, {})
            synergy_pairs = synergy.get("champions", {}).get(champion, {})
            lines.append(f"### {champion}")
            if counter_pairs:
                top_counters = sorted(
                    counter_pairs.items(),
                    key=lambda item: float(item[1].get("winrate_delta", 0) or 0),
                    reverse=True,
                )[:5]
                for opponent, payload in top_counters:
                    lines.append(f"- Counter: {opponent} delta={payload.get('winrate_delta')} score={payload.get('counter_score')}")
            else:
                lines.append("- Counter: N/A")
            if synergy_pairs:
                top_synergy = sorted(
                    synergy_pairs.items(),
                    key=lambda item: float(item[1].get("synergy_score", 0) or 0),
                    reverse=True,
                )[:5]
                for ally, payload in top_synergy:
                    lines.append(f"- Synergy: {ally} score={payload.get('synergy_score')} reason={payload.get('reason')}")
            else:
                lines.append("- Synergy: N/A")
            lines.append("")
        report_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    sync = OnlineMetaSync()
    result = sync.build_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


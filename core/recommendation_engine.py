import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHAMPION_DATA_PATH = PROJECT_ROOT / "champion_data.json"

# Tag -> Dimension weight mapping (0-10)
# Each existing champion tag contributes to one or more dimensions.
TAG_WEIGHTS: Dict[str, Dict[str, int]] = {
    "frontline":   {"frontline": 8, "teamfight": 5, "peel": 2},
    "engage":      {"engage": 8, "teamfight": 6, "frontline": 2},
    "cc":          {"teamfight": 5, "pick": 5, "peel": 3},
    "peel":        {"peel": 8, "teamfight": 3},
    "poke":        {"poke": 9, "dps": 2, "lategame": 2},
    "burst":       {"burst": 9, "pick": 3},
    "dps":         {"dps": 9, "lategame": 5, "teamfight": 4},
    "assassin":    {"burst": 7, "mobility": 8, "pick": 4, "earlygame": 3},
    "mage":        {"burst": 6, "poke": 5, "teamfight": 4, "lategame": 4},
    "marksman":    {"dps": 9, "lategame": 7, "teamfight": 5, "splitpush": 3},
    "tank":        {"frontline": 9, "engage": 5, "teamfight": 5, "peel": 3},
    "fighter":     {"frontline": 5, "splitpush": 6, "dps": 4, "teamfight": 3},
    "sustain":     {"peel": 4, "teamfight": 3},
    "enchanter":   {"peel": 7, "teamfight": 3, "mobility": 3},
    "ap":          {"burst": 3, "poke": 3, "lategame": 3},
    "ad":          {"dps": 4, "splitpush": 3, "earlygame": 2},
}

# Adjustments for specific champions (overrides or additions to tag-based weights)
SPECIAL_WEIGHTS: Dict[str, Dict[str, int]] = {
    "Kassadin":       {"mobility": 8, "lategame": 9, "earlygame": 1, "burst": 7, "splitpush": 5},
    "Kayle":          {"lategame": 10, "earlygame": 1, "dps": 8, "splitpush": 4},
    "Nasus":          {"lategame": 8, "earlygame": 2, "splitpush": 7, "frontline": 5},
    "Vayne":          {"lategame": 9, "earlygame": 2, "dps": 9, "splitpush": 5, "mobility": 4},
    "Jax":            {"lategame": 8, "splitpush": 8, "duel": 9, "mobility": 3},
    "Fiora":          {"splitpush": 9, "lategame": 7, "duel": 9, "mobility": 4},
    "Tryndamere":     {"splitpush": 9, "lategame": 5, "earlygame": 3, "frontline": 3},
    "Zed":            {"earlygame": 6, "burst": 8, "mobility": 8, "splitpush": 5},
    "Talon":          {"earlygame": 7, "burst": 8, "mobility": 8, "splitpush": 6},
    "Pantheon":       {"earlygame": 9, "lategame": 3, "pick": 6, "engage": 7},
    "Draven":         {"earlygame": 7, "burst": 7, "lategame": 4},
    "Caitlyn":        {"earlygame": 7, "lategame": 5, "poke": 8, "pick": 4},
    "LeeSin":         {"earlygame": 8, "lategame": 4, "mobility": 7, "teamfight": 4},
    "Elise":          {"earlygame": 8, "lategame": 3, "pick": 5},
    "Nidalee":        {"earlygame": 8, "lategame": 3, "poke": 7, "mobility": 7},
    "RekSai":         {"earlygame": 7, "lategame": 3, "pick": 5},
    "XinZhao":        {"earlygame": 7, "lategame": 3, "engage": 6},
    "JarvanIV":       {"earlygame": 6, "engage": 7, "teamfight": 5, "frontline": 5},
    "Orianna":        {"teamfight": 8, "lategame": 6, "burst": 6, "peel": 5},
    "Amumu":          {"teamfight": 8, "engage": 7, "cc": 8, "frontline": 6},
    "Malphite":       {"teamfight": 8, "engage": 8, "frontline": 7},
    "Wukong":         {"teamfight": 7, "engage": 6, "burst": 5},
    "Kennen":         {"teamfight": 8, "engage": 7, "burst": 6},
    "Yasuo":          {"teamfight": 6, "dps": 6, "splitpush": 5, "mobility": 5},
    "Katarina":       {"teamfight": 8, "burst": 8, "mobility": 6},
    "Fiddlesticks":   {"teamfight": 8, "burst": 7, "pick": 5},
    "Blitzcrank":     {"pick": 9, "engage": 7, "frontline": 5},
    "Thresh":         {"pick": 8, "peel": 6, "engage": 5, "teamfight": 5},
    "Nautilus":       {"pick": 8, "engage": 7, "frontline": 6},
    "Pyke":           {"pick": 7, "mobility": 7, "burst": 5, "earlygame": 5},
    "Ashe":           {"pick": 6, "lategame": 5, "dps": 7, "engage": 4},
    "TwistedFate":    {"pick": 7, "splitpush": 4, "mobility": 3, "earlygame": 4},
    "Sion":           {"splitpush": 6, "frontline": 8, "engage": 5, "teamfight": 5},
    "Tryndamere":     {"splitpush": 9, "frontline": 3, "duel": 9},
    "Gwen":           {"splitpush": 7, "lategame": 6, "dps": 7, "frontline": 4},
}

# All dimension names in display order
DIMENSIONS = [
    "frontline", "engage", "peel", "poke", "burst", "dps",
    "mobility", "teamfight", "pick", "splitpush", "earlygame", "lategame",
]

# Dimensions to check for "missing" detection
CRITICAL_DIMENSIONS = ["frontline", "engage", "cc", "ap"]


class TeamAnalyzer:
    """Analyzes team compositions from recognized BP data."""

    def __init__(self, champion_data_path: Optional[Path] = None):
        path = champion_data_path or CHAMPION_DATA_PATH
        if not path.exists():
            raise FileNotFoundError(f"Champion data not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            self._champion_data = json.load(f)

        # Chinese-to-English name mapping
        self._cn_to_en: Dict[str, str] = {}
        try:
            dt_path = PROJECT_ROOT / "data" / "zh_CN" / "champion.json"
            if dt_path.exists():
                with open(dt_path, "r", encoding="utf-8") as f:
                    dt = json.load(f)
                for eng_key, info in dt.get("data", {}).items():
                    self._cn_to_en[info["name"]] = eng_key
        except Exception:
            pass

    def normalize_names(self, names: List[str]) -> List[str]:
        """Convert Chinese names to English keys if needed."""
        result = []
        for name in names:
            if name in self._champion_data:
                result.append(name)
            elif name in self._cn_to_en:
                result.append(self._cn_to_en[name])
            else:
                # Case-insensitive fallback
                found = False
                for key in self._champion_data:
                    if key.lower() == name.lower():
                        result.append(key)
                        found = True
                        break
                if not found:
                    result.append(name)
        return result

    def _get_champion(self, name: str) -> dict:
        """Get champion data, returning empty data if not found."""
        if name in self._champion_data:
            return self._champion_data[name]
        for key in self._champion_data:
            if key.lower() == name.lower():
                return self._champion_data[key]
        return {"roles": [], "tags": []}

    def _compute_champion_dimensions(self, name: str) -> Dict[str, int]:
        """Compute all 12 dimension weights for a single champion."""
        champ = self._get_champion(name)
        tags = champ.get("tags", [])

        dims: Dict[str, int] = {d: 0 for d in DIMENSIONS}

        # Accumulate weights from tags
        for tag in tags:
            if tag in TAG_WEIGHTS:
                for dim, weight in TAG_WEIGHTS[tag].items():
                    if weight > dims[dim]:
                        dims[dim] = weight

        # Apply special overrides
        if name in SPECIAL_WEIGHTS:
            for dim, weight in SPECIAL_WEIGHTS[name].items():
                if dim in dims and weight > dims[dim]:
                    dims[dim] = weight

        # Cap at 10
        for dim in dims:
            if dims[dim] > 10:
                dims[dim] = 10

        return dims

    def _score_team(self, names: List[str]) -> Dict[str, int]:
        """Calculate all 12 dimension scores for a team (0-10 scale)."""
        names = self.normalize_names(names)
        if not names:
            return {d: 0 for d in DIMENSIONS}

        total_dims: Dict[str, int] = {d: 0 for d in DIMENSIONS}
        for name in names:
            cdim = self._compute_champion_dimensions(name)
            for dim in DIMENSIONS:
                total_dims[dim] += cdim[dim]

        # Average across team size
        team_size = len(names)
        avg_dims: Dict[str, int] = {}
        for dim in DIMENSIONS:
            avg_dims[dim] = round(total_dims[dim] / team_size)

        return avg_dims

    def _detect_missing(self, names: List[str]) -> List[str]:
        """Detect which critical dimensions the team is missing."""
        dims = self._score_team(names)
        # Also compute old-style tag-based counts for cc and ap checks
        names = self.normalize_names(names)
        has_cc = False
        has_ap = False
        for name in names:
            champ = self._get_champion(name)
            tags = champ.get("tags", [])
            if "cc" in tags:
                has_cc = True
            if "ap" in tags:
                has_ap = True

        missing = []
        if dims["frontline"] <= 2:
            missing.append("frontline")
        if not has_ap:
            missing.append("ap")
        if dims["engage"] <= 2:
            missing.append("engage")
        if not has_cc:
            missing.append("cc")
        return sorted(missing)

    def analyze(
        self,
        ally_picks: List[str],
        enemy_picks: List[str],
    ) -> dict:
        """Full team composition analysis with 12 dimensions."""
        ally_scores = self._score_team(ally_picks)
        enemy_scores = self._score_team(enemy_picks)

        return {
            "ally": ally_scores,
            "enemy": enemy_scores,
            "ally_missing": self._detect_missing(ally_picks),
            "enemy_missing": self._detect_missing(enemy_picks),
        }

    def describe_game_state(
        self,
        ally_picks: List[str],
        enemy_picks: List[str],
    ) -> Dict[str, str]:
        """Generate brief natural language descriptions of the game state."""
        ally_scores = self._score_team(ally_picks)
        enemy_scores = self._score_team(enemy_picks)
        ally_missing = self._detect_missing(ally_picks)

        # Ally description
        ally_parts = []
        if ally_scores.get("engage", 0) >= 7:
            ally_parts.append("strong engage")
        if ally_scores.get("frontline", 0) >= 7:
            ally_parts.append("tanky frontline")
        if ally_scores.get("poke", 0) >= 6:
            ally_parts.append("good poke")
        if ally_scores.get("burst", 0) >= 7:
            ally_parts.append("high burst")
        if ally_scores.get("dps", 0) >= 7:
            ally_parts.append("sustained DPS")
        if ally_scores.get("peel", 0) >= 6:
            ally_parts.append("good peel")

        # Enemy description - focus on threats
        enemy_parts = []
        enemy_dash_count = 0
        for e in enemy_picks:
            if e in ("Yasuo","Yone","LeeSin","Riven","Irelia","Akali","BelVeth","Kayn","Camille","Rengar","Nidalee","Tristana","KhaZix","Zed","LeBlanc","Ekko","Fizz","Katarina"):
                enemy_dash_count += 1

        ap_count = 0
        ap_set = {"Ahri","Annie","Anivia","AurelionSol","Azir","Brand","Cassiopeia","Diana","Ekko","Elise","Evelynn","Fiddlesticks","Fizz","Galio","Gragas","Heimerdinger","Hwei","Karma","Karthus","Kassadin","Katarina","Kayle","Kennen","KogMaw","Leblanc","Lissandra","Lulu","Lux","Malzahar","Maokai","Mordekaiser","Morgana","Nami","Neeko","Nidalee","Orianna","Qiyana","Rakan","Rumble","Ryze","Seraphine","Shaco","Sona","Soraka","Swain","Syndra","Taliyah","Teemo","TwistedFate","Veigar","VelKoz","Vex","Viktor","Vladimir","Xerath","Yuumi","Zac","Ziggs","Zilean","Zoe","Zyra"}
        for e in enemy_picks:
            if e in ap_set:
                ap_count += 1

        if enemy_dash_count >= 4:
            enemy_parts.append(f"heavy dive ({enemy_dash_count} dashers)")
        elif enemy_dash_count >= 2:
            enemy_parts.append("mobile comp")
        if ap_count >= 4:
            enemy_parts.append(f"AP heavy ({ap_count} mages)")
        cc_count = sum(1 for e in enemy_picks if e in ("Amumu","Annie","Ashe","Blitzcrank","Braum","Leona","Malphite","Maokai","Nautilus","Ornn","Pyke","Rell","Rakan","Sejuani","Shen","Skarner","Swain","Thresh","Vi","Warwick","Zac","Nunu","Lissandra","TwistedFate","Varus","Ahri","Neeko"))
        if cc_count >= 4:
            enemy_parts.append(f"CC heavy ({cc_count} hard CC)")
        if enemy_scores.get("engage", 0) >= 7 and "dive" not in str(enemy_parts):
            enemy_parts.append("strong initiators")
        if enemy_scores.get("poke", 0) >= 7:
            enemy_parts.append("heavy poke")
        if not enemy_parts:
            if enemy_scores.get("frontline", 0) >= 7:
                enemy_parts.append("frontline heavy")
            elif enemy_scores.get("burst", 0) >= 7:
                enemy_parts.append("burst oriented")
            else:
                enemy_parts.append("balanced comp")

        # Ally description as Chinese-like summary
        if ally_parts:
            ally_desc = "Team: " + ", ".join(ally_parts)
        else:
            ally_desc = "Team: balanced"
        if ally_missing:
            ally_desc += " | needs: " + ", ".join(ally_missing[:3])

        # Enemy description
        enemy_desc = "Enemy: " + ", ".join(enemy_parts)

        # Brief suggestion based on threats
        suggestion = ""
        if enemy_dash_count >= 3:
            suggestion += "Poppy or Vex strong vs dashes. "
        if ap_count >= 3:
            suggestion += "Kassadin or Galio counters AP stack. "
        if cc_count >= 4:
            suggestion += "Morgana or Sivir good vs CC. "
        if ally_missing:
            for m in ally_missing:
                if m == "frontline":
                    suggestion += "Need tank. "
                elif m == "engage":
                    suggestion += "Need engage. "
                elif m == "peel":
                    suggestion += "Need peel. "

        return {
            "ally_summary": ally_desc,
            "enemy_summary": enemy_desc,
            "suggestion": suggestion.strip(),
            "ally_scores": ally_scores,
            "enemy_scores": enemy_scores,
        }



def print_analysis(
    summary: Dict[str, List[str]],
    analyzer: Optional["TeamAnalyzer"] = None,
) -> None:
    """Print formatted team analysis from a BP summary dict."""
    if analyzer is None:
        analyzer = TeamAnalyzer()
    result = analyzer.analyze(
        ally_picks=summary.get("ally_picks", []),
        enemy_picks=summary.get("enemy_picks", []),
    )

    display_names = {
        "frontline": "\u524d\u6392",
        "engage": "\u5f00\u56e2",
        "peel": "\u4fdd\u62a4",
        "poke": "\u8037\u6bdb",
        "burst": "\u7206\u53d1",
        "dps": "\u6301\u7eed\u4f24\u5bb3",
        "mobility": "\u673a\u52a8\u6027",
        "teamfight": "\u56e2\u6218",
        "pick": "\u5355\u6293",
        "splitpush": "\u5206\u63a8",
        "earlygame": "\u524d\u671f",
        "lategame": "\u540e\u671f",
    }

    print()
    print("=" * 54)
    print("\u9635\u5bb9\u5206\u6790")
    print("=" * 54)

    for side_name, side_key, side_missing in [
        ("\u5df1\u65b9", "ally", "ally_missing"),
        ("\u654c\u65b9", "enemy", "enemy_missing"),
    ]:
        print(f"\n[{side_name}]")
        s = result[side_key]
        for dim in DIMENSIONS:
            label = display_names.get(dim, dim)
            bar = "\u2588" * s[dim] + "\u2591" * (10 - s[dim])
            print(f"  {label:6s} {bar} {s[dim]}/10")

        missing = result[side_missing]
        if missing:
            names_cn = [display_names.get(m, m) for m in missing]
            print(f"  \u7f3a\u5931: {', '.join(names_cn)}")
        else:
            print(f"  \u7f3a\u5931: \u65e0\u4e25\u91cd\u7f3a\u9879")

    print("=" * 54)
    print()


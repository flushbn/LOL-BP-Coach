"""MechanicInsightLayer V1."""

from typing import List, Dict

SYLAS_TARGETS = {"Malphite","Amumu","Orianna","Hecarim","Nocturne","Ahri","Neeko","Wukong"}

POPPY_DASH_TARGETS = {"Yasuo","Yone","LeeSin","Riven","Irelia","Akali","BelVeth","Kayn","Camille","Rengar","Nidalee","Tristana","KhaZix"}

AP_CHAMPIONS = {"Ahri","Annie","Anivia","AurelionSol","Azir","Brand","Cassiopeia","Diana","Ekko","Elise","Evelynn","Fiddlesticks","Fizz","Galio","Gragas","Heimerdinger","Hwei","Karma","Karthus","Kassadin","Katarina","Kayle","Kennen","KogMaw","Leblanc","Lissandra","Lulu","Lux","Malzahar","Maokai","Mordekaiser","Morgana","Nami","Neeko","Nidalee","Orianna","Qiyana","Rakan","Rumble","Ryze","Seraphine","Shaco","Sona","Soraka","Swain","Syndra","Taliyah","Teemo","TwistedFate","Veigar","VelKoz","Vex","Viktor","Vladimir","Xerath","Yuumi","Zac","Ziggs","Zilean","Zoe","Zyra"}

VEX_MOBILE_TARGETS = POPPY_DASH_TARGETS | {"Zed","LeBlanc","Ekko","Fizz","Katarina"}

HARD_CC_CHAMPIONS = {"Amumu","Annie","Ashe","Blitzcrank","Braum","Leona","Malphite","Maokai","Morgana","Nautilus","Ornn","Pyke","Rell","Rakan","Sejuani","Shen","Skarner","Swain","Thresh","Vi","Warwick","Zac","Nunu","Lissandra","TwistedFate","Varus","Ahri","Neeko"}

class MechanicAnalyzer:
    @staticmethod
    def get_bonus(champ: str, enemy_picks: List[str]) -> int:
        bonus = 0
        if champ == "Sylas":
            hits = sum(1 for e in enemy_picks if e in SYLAS_TARGETS)
            bonus = min(hits, 5)
        elif champ == "Poppy":
            dashers = sum(1 for e in enemy_picks if e in POPPY_DASH_TARGETS)
            if dashers >= 5: bonus = 5
            elif dashers >= 4: bonus = 4
            elif dashers >= 3: bonus = 3
        elif champ == "Kassadin":
            ap_count = sum(1 for e in enemy_picks if e in AP_CHAMPIONS)
            if ap_count >= 4: bonus = 5
            elif ap_count >= 3: bonus = 3
        elif champ == "Vex":
            mobile = sum(1 for e in enemy_picks if e in VEX_MOBILE_TARGETS)
            if mobile >= 5: bonus = 4
            elif mobile >= 3: bonus = 2
        elif champ == "Morgana":
            cc_count = sum(1 for e in enemy_picks if e in HARD_CC_CHAMPIONS)
            if cc_count >= 5: bonus = 5
            elif cc_count >= 3: bonus = 3
        return min(bonus, 5)

    @staticmethod
    def get_trigger_info(champ: str, enemy_picks: List[str]) -> Dict:
        bonus = MechanicAnalyzer.get_bonus(champ, enemy_picks)
        rules = []
        if champ == "Sylas":
            hits = [e for e in enemy_picks if e in SYLAS_TARGETS]
            if hits: rules.append({"rule": "Sylas ult steal", "hits": hits, "bonus": min(len(hits),5)})
        elif champ == "Poppy":
            hits = [e for e in enemy_picks if e in POPPY_DASH_TARGETS]
            if hits: rules.append({"rule": "Poppy dash counter", "hits": hits, "bonus": bonus})
        elif champ == "Kassadin":
            hits = [e for e in enemy_picks if e in AP_CHAMPIONS]
            if hits: rules.append({"rule": "Kassadin vs AP", "hits": hits, "bonus": bonus})
        elif champ == "Vex":
            hits = [e for e in enemy_picks if e in VEX_MOBILE_TARGETS]
            if hits: rules.append({"rule": "Vex vs mobility", "hits": hits, "bonus": bonus})
        elif champ == "Morgana":
            hits = [e for e in enemy_picks if e in HARD_CC_CHAMPIONS]
            if hits: rules.append({"rule": "Morgana vs CC", "hits": hits, "bonus": bonus})
        return {"bonus": bonus, "rules": rules}


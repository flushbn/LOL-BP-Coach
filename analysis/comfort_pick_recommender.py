from pathlib import Path
import json

class ComfortPickRecommender:
    """Filters recommendations through user's favorite champion pool."""
    def __init__(self, user_profile_path=None):
        if user_profile_path is None:
            user_profile_path = Path(__file__).parent.parent / "config" / "user_profile.json"
        self._favorites = []
        self._min_score = 70
        try:
            with open(str(user_profile_path),"r",encoding="utf-8") as f:
                profile = json.load(f)
                self._favorites = profile.get("favorite_champions",[])
        except:
            # Default: empty favorites
            self._favorites = []

    def has_favorites(self):
        return len(self._favorites)>0

    def filter(self, recommendations):
        """From full recs, only keep favorites scoring above threshold."""
        result = []
        fav_set = set(self._favorites)
        for r in recommendations:
            if r["champion"] in fav_set and r["final_score"]>=self._min_score:
                result.append(r)
        return result[:3]



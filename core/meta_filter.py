from typing import List, Tuple

from core.meta_analyzer import MetaAnalyzer


class MetaFilter:
    """Filter champion pool by current-patch role viability."""

    def __init__(self, viability_threshold: int = 50):
        self.analyzer = MetaAnalyzer()
        self.threshold = viability_threshold

    def is_viable(self, champion_name: str, role: str | None = None) -> bool:
        return self.analyzer.get_viability(champion_name, role) >= self.threshold

    def filter(self, champions: List[str], role: str | None = None) -> List[Tuple[str, int]]:
        return [
            (champion, self.analyzer.get_viability(champion, role))
            for champion in champions
            if self.is_viable(champion, role)
        ]

    def set_threshold(self, threshold: int) -> None:
        self.threshold = max(0, min(100, threshold))

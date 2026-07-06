from core.meta_analyzer import MetaAnalyzer
from typing import List, Tuple


class MetaFilter:
    """Filter champion pool by viability."""

    def __init__(self, viability_threshold: int = 50):
        self.analyzer = MetaAnalyzer()
        self.threshold = viability_threshold

    def is_viable(self, champion_name: str) -> bool:
        return self.analyzer.get_viability(champion_name) >= self.threshold

    def filter(self, champions: List[str]) -> List[Tuple[str, int]]:
        """Filter and return viable champions with their viability scores."""
        return [
            (c, self.analyzer.get_viability(c))
            for c in champions
            if self.is_viable(c)
        ]

    def set_threshold(self, threshold: int) -> None:
        self.threshold = max(0, min(100, threshold))


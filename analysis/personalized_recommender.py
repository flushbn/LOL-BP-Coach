"""Personalized Recommender V1 — comfort_bonus from player history."""

from pathlib import Path
from typing import Optional
from analysis.player_profile import PlayerProfile

_profile_instance: Optional[PlayerProfile] = None

def _get_profile() -> PlayerProfile:
    global _profile_instance
    if _profile_instance is None:
        _profile_instance = PlayerProfile()
        # Auto-import from sessions on first access
        _profile_instance.import_from_sessions()
    return _profile_instance

def get_comfort_bonus(champion: str, min_games: int = 3) -> dict:
    """Get comfort bonus for a champion.

    Returns:
        {"comfort_bonus": -5~+5, "comfort_reason": str, "games": int, "winrate": float}
    """
    profile = _get_profile()
    return profile.get_comfort(champion, min_games=min_games)

def get_all_comfort() -> list:
    """Get comfort data for all known champions."""
    profile = _get_profile()
    return profile.get_all_comfort()

def refresh_profile():
    """Force re-import from match sessions."""
    global _profile_instance
    _profile_instance = PlayerProfile()
    _profile_instance.import_from_sessions()

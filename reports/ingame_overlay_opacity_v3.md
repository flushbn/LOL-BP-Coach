# In-game Overlay Opacity V3

## Change

The in-game tactical overlay now applies transparency only to its background surfaces. Text, icons, and action labels remain fully opaque.

## Behavior

- The `背景透明度` slider controls the alpha of the root, title bar, cards, and buttons.
- The Qt window opacity remains fixed at `1.0`.
- The overlay retains `WA_TranslucentBackground`, so the game remains visible behind its background layers.
- Existing V2 settings are migrated to a readable 90% background setting.

## Scope

This changes only `ui_v2/in_game/tactical_overlay.py`. Recognition, recommendations, data loading, and the desktop UI are unaffected.

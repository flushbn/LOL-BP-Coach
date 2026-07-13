# In-Game Tactical Readability V2

## Tactical Text

- The in-game compact view now shows the main tempo, one key lane, and at most two action items.
- The desktop coach page limits tactical advice to three concise lines.
- The lane and macro pages keep only the key lane action, two summary items, and one resource or risk reminder.

## Overlay

- The transparency slider now controls actual window opacity from 65% to 100%.
- Legacy backdrop brightness settings are migrated to a readable 90% window opacity.
- The overlay uses Qt topmost flags and reapplies Windows `HWND_TOPMOST` every 1.5 seconds without activating the window.
- True exclusive fullscreen can still block normal desktop overlays at the graphics-driver level; LoL borderless/windowed fullscreen is the supported mode.

## Validation

- Compact overlay output is capped at four lines.
- Desktop coach and macro summaries are capped at three to four lines.
- Offscreen tests verified the topmost flag and 74% real window opacity.

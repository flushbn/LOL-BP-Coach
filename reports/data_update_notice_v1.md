# Data Update Notice V1

## Behavior

1. The client checks Data Dragon for the latest League patch shortly after startup.
2. The check runs in a background Qt thread and does not delay BP recognition or UI startup.
3. When the local patch differs from the online patch, a visible top-bar notice shows both versions.
4. The notice includes an **Update Now** button that opens the Data Update Center.
5. Completing a data update triggers another automatic version check. The notice hides when versions match.
6. If the network check fails, the client keeps using local data without showing a false update warning.

## Validation

- Simulated local `16.13` and online `16.14`: outdated status detected.
- UI test: notice displayed, update button navigated to the update page, matching status hid the notice.

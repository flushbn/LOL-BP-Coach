# Recommendation Data Quality Fix V1

## Scope

- Patch: 16.13
- Data source: Lolalytics + Data Dragon
- Validation date: 2026-07-13

## Fixed

1. Meta now reads the selected role entry instead of a champion's best role.
2. Counter now reads only the selected role and treats absent data as neutral.
3. Counter rows without a parsed game count keep only 35% of their directional signal.
4. Lane bonus with an unknown or low sample is capped through confidence scaling and marked as pending verification.
5. FiddleSticks/Fiddlesticks duplicates were merged in all 16.13 Meta, Counter, and Synergy files.
6. Role indexes were rebuilt from the 16.13 Meta file: 173 unique champions and 261 active role entries.
7. Enemy picks are excluded by the recommendation engine even when a caller does not pass them as bans.
8. Legacy flat Lolalytics cache fallback was removed to prevent cross-patch cache reuse.

## Validation

| Scenario | Result |
|---|---|
| Top vs Yasuo | Sett, Darius, Malphite remain valid TOP candidates |
| Mid vs Zed | Malzahar, Ahri, Vex remain valid MID candidates |
| ADC vs KaiSa | KaiSa is excluded; Ashe and Jhin lead the result |
| Support vs Nautilus | Thresh, Seraphine, Leona remain valid SUPPORT candidates |

## Remaining Data Limit

The existing 16.13 Counter cache contains no parsed game counts for most rows. It is still used as a weak directional signal, not as decisive evidence. Future online refreshes now attempt to parse game counts from the Counter page; rows below 500 games remain down-weighted.

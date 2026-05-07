# ChirpWise Commercial Source Coverage

Generated: `2026-05-07T11:36:22.305558+00:00`

Scope: current North America/ABA taxonomy table in `data/app/birdtrainer.sqlite3`.

Rule: count only no-email/no-new-license sources whose metadata says commercial use and derivatives are allowed. Xeno-canto, NPS, and Commons exact metadata matches are treated as strict candidates. iNaturalist research-grade exact taxon matches are counted separately because audio should still be manually listened to before shipping.

## Summary

- Total species: 1161
- Strict no-email commercial-safe species: 626 (53.92%)
- Species covered if manual-QC iNaturalist candidates are accepted: 804 (69.25%)
- Manual-QC candidate species: 178
- Still missing after all mapped no-email sources: 357 (30.75%)

## By Source

| Source | Species |
| --- | ---: |
| xeno-canto | 541 |
| missing | 357 |
| iNaturalist | 178 |
| Wikimedia Commons | 77 |
| National Park Service | 8 |

## By Tier

| Tier | Species |
| --- | ---: |
| strict_safe_ab | 488 |
| missing | 357 |
| candidate_safe_research_grade | 178 |
| strict_safe_commons_exact | 77 |
| strict_safe_any_quality | 53 |
| strict_safe_public_domain | 8 |

## Files

- `commercial-source-coverage.csv`: row-by-row species map
- `commercial-source-coverage.json`: machine-readable summary and rows

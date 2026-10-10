# Assumptions and acceptance checks

## Declared parameters (Part H)
| Name | Value | Meaning |
|---|---|---|
| TAU | 0.5 | a segment is *concerning* if risk > TAU |
| R | 40 m | sustained assessed-good metres needed to break a concerning run |
| DELTA | 10 m | bucket size for the continuity search (concerning metres rounded up) |
| DETOUR_FACTOR | 1.4 | time budget = fastest eligible time x 1.4 |
| UNKNOWN_DEFAULT | 0.70 | pessimism value for a missing field (heuristic, not a statistic) |
| STALE_AFTER_H / MAX_STALE_ADD | 12 h / 0.15 | staleness penalty ramp |
| Walk speed | 1.25 m/s | used for all walk times |
| CAMPUS_MEMBER_ACCESS | True | OSM `access=private` campus roads are treated as walkable for campus members; `access=no` / `foot=no` excluded |

Unknown (`no_data`) segments count as concerning for continuity and never break a run.
Weights in `app/config.py` are a documented heuristic, not learned.

## Geography
Overpass / osmnx downloads failed from the build sandbox (504s, connection resets), so OSM data was fetched from
the OSM main API as 9 bbox tiles (`data/osm_tiles/`), filtered to walkable ways in `app/osm_build.py`, projected to
EPSG:32646 (UTM 46N), saved as GraphML (`data/iitg.graphml`), and split into ~30 m metric fragments (`data/segments.json`).
Result: 1966 segments, 6 components, largest holds 1737 of 1916 nodes. No edges are invented to join components;
the API snaps start/end only inside the largest component.

## Acceptance checks (Part E)
| # | Check | Status | Where |
|---|---|---|---|
| 1 | Scenario regenerates identically from its seed | PASS | tests/test_data.py |
| 2 | Counterexample: calmest != fastest, separated by continuity | PASS | tests/test_router.py |
| 3 | Budget enforced | PASS | tests/test_router.py |
| 4 | Subdivision invariance | PASS | tests/test_router.py |
| 5 | All-missing segment = 1.0 / coverage 0 / no_data | PASS | tests/test_router.py |
| 6 | Unknown never breaks a stretch | PASS | tests/test_router.py |
| 7 | Unreachable OD explicit, no invented edge | PASS | tests/test_router.py |
| 8 | Unverified no-op; verify reroutes; repair restores; rollback works | PASS | tests/test_loop.py |
| 9 | One-field swap via observation table, no routing code edited | PASS | tests/test_loop.py |
| 10 | Idempotency | PASS | tests/test_loop.py |
| 11 | Midnight trip uses correct scenario date | PASS | tests/test_loop.py |
| 12 | Closed edge never routed | PASS | tests/test_router.py |
| 13 | LLM failure keeps manual categories and text | PASS | tests/test_loop.py |
| 14 | Catalog consistency | PASS | tests/test_data.py |

## Known limitations of the router as built
- The product-graph search forbids immediate U-turns on the same edge. If the optimal walk still revisits a node,
  L is stepped upward until a simple path is found and the card is labelled "not proven optimal".
- Balanced (exposure-minimising) is best among explored states, not exact.
- Measured on the IITG graph: 0.01 to 1.0 s per full plan() over 10 random OD pairs (single run each).
- A verified report applies to every ~30 m fragment of the same physical OSM edge.

## Demo OD pair (cached)
Start 26.1872635, 91.6957466 -> End 26.18951, 91.7002911, departure 22:00.
Fastest 12.3 min / longest stretch 571 m; Calmest 14.5 min / longest stretch 83 m.

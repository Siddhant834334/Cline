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
- Calmest: L* is an upper bound on the optimum among U-turn-free walks; the bucketing is conservative, so the reported longest stretch is never under-stated.
- Bucket merging can retain a dominated state: states whose exact (c, g) differ but share a bucket key are merged, and
  the search keeps whichever arrives first by (time, exposure), not the one with the better continuation, so L* may be
  larger than the true optimum (never smaller).
- The product-graph search forbids immediate U-turns on the same edge. If the optimal walk still revisits a node,
  L is stepped upward until a simple path is found and the card is labelled "not proven optimal".
- Balanced (exposure-minimising) is best among explored states, not exact.
- Measured on the IITG graph: 0.01 to 1.0 s per full plan() over 10 random OD pairs (single run each).
- A verified report applies to every ~30 m fragment of the same physical OSM edge.

## Demo OD pairs (`data/demo_pairs.json`, served at `GET /api/demo_pairs`)
Written by `python scripts/demo_gate.py` from the committed scenario (v1, seed 20251010), departure 22:00,
detour budget 1.4x. The longest-stretch values are outputs of that synthetic scenario, not measurements of real streets.

| Pair | Start (lat, lng) | End (lat, lng) | Fastest: time / longest stretch | Calmest: time / longest stretch |
|---|---|---|---|---|
| 1 | 26.1871278, 91.6887413 | 26.1870157, 91.6957447 | 13.9 min / 415.1 m | 18.8 min / 27.7 m |
| 2 | 26.1860109, 91.6915224 | 26.1865201, 91.6957410 | 12.0 min / 476.1 m | 13.7 min / 172.5 m |
| 3 | 26.1948883, 91.6950284 | 26.1892643, 91.7003392 | 14.8 min / 325.8 m | 19.2 min / 29.8 m |
| 4 | 26.1961325, 91.6963604 | 26.1908275, 91.6958018 | 12.7 min / 325.8 m | 15.5 min / 53.3 m |
| 5 | 26.1907354, 91.6868731 | 26.1914732, 91.6913222 | 13.1 min / 200.4 m | 17.3 min / 54.1 m |

The five pairs are the largest reductions found in the sample. They are selected, not typical.

## Measured aggregate (same gate run)
Of 40 OD pairs with an 8-15 minute fastest walk (sample seed 4242), 28 had no calmer route within the budget,
7 improved by under 100 m and 5 by 100 m or more. Restricted to the 16 pairs whose fastest route carries a >= 200 m
stretch, 5 improved by 100 m or more (31.2%); the other 11 had no calmer route.

Concerning share by departure hour: 18:00 21.6%, 20:00 22.7%, 22:00 25.4%, 01:00 37.7%.

Gate checks: hour-22 concerning share must lie in 18-28%; the dark-subset >= 100 m share is compared against a
**recorded baseline** of 30%, not a target. The script exits non-zero if either check fails.

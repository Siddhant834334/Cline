# Cline log

Built with Cline on branch `cline/xcmt1nh7`.

- Block 0: scaffold, SQL schema (B1), config with Part H parameters.
- Block 2: scoring (C2) and product-graph router (C3). Gate tests written first (counterexample, budget, subdivision, unreachable).
- Block 1: Overpass/osmnx downloads failed from the sandbox (504s, resets). Switched to OSM main API tiles plus our own graph builder. Seeded narrow-observation generator and catalog.
- Real-graph finding: the optimal product-graph walk often doubled back. Fixed by forbidding same-edge U-turns, plus a labelled simple-path relaxation.
- Block 4: report lifecycle (draft / accepted / verified / fixed / rejected, rollback), expiring events, idempotency, live -> replay -> manual extraction. End-to-end loop test.
- Block 3: Leaflet UI, segment drawer, reviewer portal, provenance page.

Cline SDK spike: **not yet run.**

# Fear-Free Night Navigator

Walking routes on the **real IIT Guwahati road network** that minimise the *longest continuous concerning stretch*
within a time budget. **Street conditions are synthetic.** Nothing here establishes real night-time safety.

## Run locally
```bash
pip install -r requirements.txt
python -m app.generate       # seeded synthetic observations into data/fnn.db
uvicorn app.main:app --port 8000
pytest -q
```

Optional: `python -m app.osm_build` rebuilds the geography (`data/iitg.graphml`, `data/segments.json`) from the
raw OSM tiles in `data/osm_tiles/`. Both outputs are committed, so this is only needed if you change the tiles or the
walkability filter. Re-run `python -m app.generate` afterwards.

- http://localhost:8000: map. Click start, then end. Click any road for its per-field drawer and to report a problem.
- `/portal`: reviewer portal. Token from `FNN_REVIEWER_TOKEN` (default `demo-reviewer-token`). **Demo auth only.**
- `/provenance`: dependency ledger. The actual source of every v1 condition value is `synthetic_generator`.

Ticket agent (optional): `cd app/agent_node && npm install` (Node >= 22) plus `ANTHROPIC_API_KEY`. Tickets are then
drafted by a Cline SDK agent with zero tools; without it they fall back to a direct LLM call, then a template.
The `drafted_by` field says which path produced each ticket.

Live report extraction: set `ANTHROPIC_API_KEY`. Without it, the demo Hinglish sentence uses a cached response shown with a
`REPLAY (cached response)` badge; any other text falls back to manual categories.

## How routing works
- **Fastest**: Dijkstra on walk time. Defines the budget B = time x 1.4.
- **Calmest**: product graph over (node, concerning-metres bucket, good-metres bucket). Binary search on the bound L,
  with feasibility = min-time path within B. L* is an upper bound on the optimum among U-turn-free walks; the bucketing is conservative, so the reported longest stretch is never under-stated.
- **Balanced**: minimises concerning metres under the L* bound and budget. Best among generated candidates, not exact.
- Unknown segments are pessimistic, count as concerning and never break a stretch.

## Real / simulated / not implemented
- Real: OSM geography, the route mathematics, and the report -> authenticated review -> expiring event -> reroute loop.
- Simulated: every baseline condition value.
- Not implemented: anti-concentration, reporter reputation, outlier detection, automatic dead-lamp detection,
  loitering inference (removed permanently), native telemetry, bus/cab chains, exact exposure minimisation,
  any pilot or authority cooperation.

Parameters and acceptance-check status: [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md). Every decision that departed from or filled gaps in the build spec: [`docs/DECISIONS.md`](docs/DECISIONS.md).

Geography (c) OpenStreetMap contributors, ODbL.

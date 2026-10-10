# Decisions log

Every decision taken during the build that departed from `BUILD_SPEC_FINAL.md` or filled a gap in it:
what was chosen, why, and what it means for our claims. Every number below is a chosen setting, except
where it is explicitly labelled as an output measured by running our own code. No chosen parameter has been
validated against the real world.

---

## 1. Scenario tuning: synthetic conditions were adjusted after the first run

**What we did.** After the first generator run, we raised the zone baselines for `lighting_level` and
`activity_level` and reduced the late-night decay of `activity_level`, then regenerated. We did this because more
than half of all segments were concerning, and most routes we sampled had no distinct Calmest card.

| Parameter | First run | Committed (`data/scenario_v1.json`) |
|---|---|---|
| lighting baseline: academic / hostel / residential / periphery / lakeside | 0.80 / 0.70 / 0.55 / 0.25 / 0.35 | 0.85 / 0.80 / 0.70 / 0.45 / 0.50 |
| activity baseline: academic / hostel / residential / periphery / lakeside | 0.60 / 0.80 / 0.40 / 0.15 / 0.30 | 0.60 / 0.80 / 0.55 / 0.30 / 0.40 |
| late-night activity decay | 0.50 | 0.35 |

The first-run values were never committed to git. They are reconstructed from the first generator draft.
Regenerating with them gives 54.9% concerning segments at 22:00, the figure observed during the build.

**These are chosen parameters of a synthetic scenario, not measurements.** They describe no real street on the
IITG campus. Route results from this build must never be presented as anything other than behaviour under a
scenario we selected.

**Concerning share in the committed scenario.** These figures come from running our own code on the committed
scenario, with TAU = 0.5 and `no_data` segments counted as concerning:

| Departure | Concerning segments | Concerning length | `no_data` segments |
|---|---|---|---|
| 18:00 | 45.7% | 45.7% | 39 of 1,966 |
| 20:00 | 47.9% | 47.7% | 39 of 1,966 |
| 22:00 | 50.5% | 50.2% | 39 of 1,966 |
| 01:00 | 55.6% | 55.4% | 39 of 1,966 |

The same procedure on the first-run scenario gives 50.1% / 51.7% / 54.9% / 63.1% at the same hours.

Stated plainly:
- The tuning lowered the concerning share by 4–8 percentage points. The committed scenario is still about half
  concerning at 22:00, and more than half at 01:00.
- The tuning was done in the same pass as removing the 600 m L cap (section 2), and before the U-turn fix
  (section 3). Their effects on Calmest-card availability were not measured separately, so the tuning alone
  should not be credited with producing distinct Calmest cards.

**Implication.** Every route number in the demo (for example fastest longest stretch 571 m, calmest 83 m) is an
output of this selected scenario. Different scenario parameters would give different routes and numbers.

---

## 2. The 600 m cap on L was removed

- **Spec:** cap L at 600 m (C3 settings).
- **Chosen:** the binary search runs up to the fastest route's own longest stretch, with no cap. `L_CAP_M = 600`
  in `app/config.py` and the `l_cap` argument of `plan()` still exist but are unused.
- **Why:** on the real graph, many fastest routes have a longest stretch above 600 m (one sampled route had
  1,255 m). With the cap, those routes got no Calmest card at all.
- **Implication:** the spec's bound of 305 states per node no longer holds. Measured timings were 0.01–1.0 s
  per `plan()` call over 10 random OD pairs, one run each. That is a small sample, not a performance guarantee.

## 3. U-turn block and the "not proven optimal" relaxation

- **Spec:** if the returned walk repeats a node, report it and fall back to the next-best candidate.
- **Chosen:**
  - The product-graph search may not leave a node along the same edge it arrived on (no immediate U-turn).
  - If the walk at the optimal bound L\* still repeats a node, L is raised one DELTA at a time until a simple
    path is found. That card's claim then reads "optimal walk revisited a node at bound X m; next feasible
    simple route shown (not proven optimal)".
- **Why:** on the real graph, the optimal walk often doubled back along an edge to reset the run counter, so
  most Calmest cards were being discarded.
- **Implication:** the unlabelled exactness claim is narrower than in the spec. It is "exact to DELTA among
  walks without immediate U-turns", not over all walks. Labelled cards claim no optimality, and the stepped
  search is not proven to find the best simple path.

## 4. `CAMPUS_MEMBER_ACCESS = True`

- **Chosen:** OSM ways tagged `access=private` count as walkable. `access=no` and `foot=no` (on ways and on
  barrier nodes) stay excluded.
- **Why:** most IITG internal roads carry `access=private`. Excluding them split the network into 28 components
  with a largest of 427 nodes. Including them gives 6 components, the largest holding 1,737 of 1,916 nodes.
- **Implication:** routes assume a walker who is allowed on private campus roads. They are not valid for the
  general public, and actual campus access rules were not checked.

## 5. Verified reports apply to the whole parent OSM edge

- **Chosen:** on verify, the condition event covers every ~30 m fragment of the same physical OSM edge as the
  reported segment (`physical_edge_fragments` in `app/reports.py`), not only the one reported fragment.
- **Why:** an outage on a single fragment did not change the demo route.
- **Implication:** the extent of an event is a product assumption. On a long OSM edge, one report can cover
  hundreds of metres. The portal gives the reviewer no way to change the extent. The internal function accepts
  explicit `segment_ids`, but no endpoint exposes it.

---

## Gaps in the spec filled during the build

### 6. Map source
- **Chosen:** OSM main API (`api.openstreetmap.org`), 9 bbox tiles saved in `data/osm_tiles/`, and our own
  builder `app/osm_build.py`, projecting to EPSG:32646.
- **Why:** osmnx/Overpass failed from the build sandbox (certificate errors, a broken status endpoint, 504s,
  connection resets).
- **Implication:** the walkability filter is our code, not osmnx's `walk` filter, so the graph may differ from
  an osmnx build. The bbox (26.1795–26.2010 N, 91.6830–91.7060 E) is our estimate of the campus extent.

### 7. Risk weights
- **Chosen:** lighting 0.30, activity 0.20, sightline 0.15, walkability 0.10, open POI distance 0.10,
  dog reports 0.10, waterlogging 0.05.
- **Why:** the spec required non-negative weights summing to 1 but gave no values.
- **Implication:** a heuristic. The weights are not learned and not validated.

### 8. Report categories and expiry windows
| Category | Effect | Expiry |
|---|---|---|
| `lamp_outage` | lighting_level set to 0.0 | 72 h |
| `path_blocked` | edge closed | 48 h |
| `construction` | walkability set to 0.1 | 168 h |
| `dog_pack` | dog_report_risk set to 0.9 | 24 h |
| `waterlogging` | waterlogging set to 0.9 | 24 h |

- **Why:** the spec named event types but no categories, values or windows.
- **Implication:** all values and windows are product assumptions.

### 9. AI provider and model
- **Chosen:** Anthropic Messages API called with stdlib `urllib`; model `claude-3-5-haiku-latest`
  (overridable with `FNN_MODEL`); key from `ANTHROPIC_API_KEY`.
- **Why:** the spec named no provider. Chosen without confirmation from the team.
- **Implication:** live extraction is untested, because no key was available during the build. The tests
  exercise only the replay and manual paths.

### 10. Catalog primary key
- **Chosen:** `(field, proposed_method)` instead of `field`.
- **Why:** the B2 table has two rows each for `lighting_level` and `canopy_occlusion`, which a `field` key
  cannot hold.
- **Implication:** departs from the B1 SQL.

### 11. Unverified reports excluded from scoring
- **Chosen:** observation rows with `source='community_report'`, including the generator's deliberately
  contradictory reports, are stored but excluded from scoring.
- **Why:** the spec rule that nothing changes routing without reviewer verification.
- **Implication:** the contradictions exist only in the database. The segment drawer does not show them.

### 12. Source precedence
- **Chosen:** `reviewed_observation` > `scenario_event` > `synthetic_generator`, with ties broken by the latest
  `observed_at`. Active verified condition events override all of them.
- **Why:** a rule was needed for acceptance check 9 (one-field swap).
- **Implication:** a design choice. It is not weighted by evidence quality.

### 13. Staleness from the oldest field timestamp
- **Chosen:** segment age is taken from the oldest `observed_at` among its fields.
- **Why:** the C2 formula uses a single `_observed_at` without saying which field supplies it.
- **Implication:** conservative. One stale field makes the whole segment count as stale.

### 14. Night hours 18:00–05:00
- **Chosen:** observations are generated only for hours 18–23 and 0–5. A departure before 12:00 maps to the
  previous evening's scenario date.
- **Why:** needed for acceptance check 11 (a trip crossing midnight).
- **Implication:** departures from 06:00 to 17:00 find no observations and score every segment as `no_data`.

### 15. Reject endpoint
- **Chosen:** added `POST /api/review/reject` (accepted → rejected), behind the same reviewer auth.
- **Why:** the spec lists a `rejected` state but no transition into it.
- **Implication:** an API endpoint not in the spec.

### 16. Reason codes, including `PASSES_EVENT`
- **Chosen:** `FASTEST`, `SHORTER_LONGEST_STRETCH`, `LESS_CONCERNING_EXPOSURE`, `CONTAINS_NO_DATA`,
  `AVOIDS_EVENT:<id>`, `PASSES_EVENT:<id>`. `AVOIDS_EVENT` is found by planning the same request again with
  events ignored and comparing each card's edges with the matching card from that plan.
- **Why:** the spec required a reason code naming the verified event but defined no code set.
- **Implication:** with active events, each request is planned twice. `PASSES_EVENT` is our addition.
  `AVOIDS_EVENT` means the event lies on the event-free version of that card and not on this one. It does not
  prove the event alone caused the change.

### 17. Counterexample fixture numbers
- **Chosen:** route A is 60 m good, 90 m concerning, 60 m good (210 m). Route B is three 30 m concerning
  stretches separated by 50 m good stretches, then 30 m good (220 m). Both have 90 m concerning in total.
- **Why:** the spec described the counterexample but gave no numbers.
- **Implication:** the numbers are ours, chosen so that A is fastest and B wins on continuity.

### 18. Session cap
- **Chosen:** 20 submissions per session id, counted in memory.
- **Why:** the spec required a per-session cap without a value.
- **Implication:** the count resets on server restart, and the client supplies the session id. Weak, as the
  spec acknowledges.

### 19. Reviewer token
- **Chosen:** bearer token read from `FNN_REVIEWER_TOKEN`, with default `demo-reviewer-token`.
- **Why:** the spec said "bearer token in env" without a fallback.
- **Implication:** the default token is public in this repository. Demo auth only: set the env var for any
  run other people can reach.

### 20. Dedup share
- **Chosen:** two cards merge when their shared length exceeds 85% of the shorter route.
- **Why:** the spec said "shared length > 85%" without a denominator.
- **Implication:** measuring against the shorter route merges cards more readily than measuring against the
  longer one.

---

Parameters and acceptance-check results: [`ASSUMPTIONS.md`](ASSUMPTIONS.md). TAU, R, DELTA, DETOUR_FACTOR,
UNKNOWN_DEFAULT and the staleness ramp are configured values in `app/config.py`. None has been validated.

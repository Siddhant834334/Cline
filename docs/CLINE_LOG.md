# Cline log

Built with Cline on branch `cline/xcmt1nh7`.

- Block 0: scaffold, SQL schema (B1), config with Part H parameters.
- Block 2: scoring (C2) and product-graph router (C3). Gate tests written first (counterexample, budget, subdivision, unreachable).
- Block 1: Overpass/osmnx downloads failed from the sandbox (504s, resets). Switched to OSM main API tiles plus our own graph builder. Seeded narrow-observation generator and catalog.
- Real-graph finding: the optimal product-graph walk often doubled back. Fixed by forbidding same-edge U-turns, plus a labelled simple-path relaxation.
- Block 4: report lifecycle (draft / accepted / verified / fixed / rejected, rollback), expiring events, idempotency, live -> replay -> manual extraction. End-to-end loop test.
- Block 3: Leaflet UI, segment drawer, reviewer portal, provenance page.

## Cline SDK spike (Block 0, 15-minute hard stop)

- Started 10:45:18 UTC, stopped 10:46 UTC (well inside 15 minutes).
- Package: `@cline/sdk` **0.0.92** ("user-facing alias for @cline/core"), pinned in `spikes/cline_sdk/package.json`.
  Installed together with `@cline/core`, `@cline/agents`, `@cline/llms`, `@cline/shared` 0.0.92.
- Runtime requirement: `engines.node >= 22`. Sandbox has Node v24.21.0, npm 11.19.0. Install succeeded.
- Script: `spikes/cline_sdk/spike.mjs`, outside `app/`. One `Agent` with `providerId: "anthropic"`, zero tools,
  `agent.run("ping")`.
- **Outcome: FAILED.** `status: "failed"`, error "Anthropic API key is missing". No LLM API key exists in the build
  environment, so no model call was made. The SDK itself imported, constructed the agent and ran its loop up to the
  provider call.
- Note: `agent.run()` resolves, it does not throw, on failure. A first version of the script read only `outputText`
  and wrongly printed `ok: true`. The committed script checks `status` and `error`.
- Decision at the time: the spike did not pass, so the ticket flow was first built in fallback mode (one direct LLM
  call, `drafted_by: "cline-authored module (SDK integration not run)"`).

### Re-run: PASSED (team, with a real key)

- The team re-ran `spikes/cline_sdk/spike.mjs` with a real `ANTHROPIC_API_KEY` and it returned `ok: true`. That script
  checks `status` and `error`, not just `outputText`, so `ok: true` means a completed model call.
- This pass was observed by the team, not in the Cline build sandbox, which still has no API key. The sandbox result
  above is unchanged and remains a fail.
- Consequence: ticket drafting moved out of fallback mode. `app/agent_node/index.mjs` runs a Cline SDK `Agent` with
  zero tools; `app/ticket.py` calls it as a subprocess. See `DECISIONS.md` section 21.
- To retry: `cd spikes/cline_sdk && npm install && ANTHROPIC_API_KEY=... node spike.mjs` (exit 0 = pass).

# Dashboard Ops Strip — Design

**Date:** 2026-07-18
**Status:** Approved (staff-eng review passed; all three nits adopted —
`STALE_MS` named once beside `POLL_MS`, api cell driven off the existing
`state.error` with no second error flag, client-clock-skew caveat noted in a
code comment where age is computed)
**Branch:** `dashboard-ops-strip` → PR into `main`
**Issues:** #20 (this work); #19 (the `/stats` contract it reads); #10
(observability convention it advances)

## Goal

Give the dashboard a small operational corner — queue depth, aggregate
freshness, api reachability — so one screen shows product *and* platform
health. This is the on-camera evidence surface for the demo's failure beat
([demo.md](../../demo.md)): when the worker dies mid-traffic, queue depth
climbs and aggregate age turns visibly red, in real time, on video.

## Scope of this PR

- `services/dashboard/` only: fetch `GET /api/stats` on the existing poll,
  render a strip under the header, extend the fixture.
- Not in scope: api changes (`/stats` shipped in #19, contract source for
  this work), the worker (doesn't exist yet — `last_aggregate_ms: null` is
  therefore a first-class day-one state), the platform status page (#10's
  operator-facing page; this strip is the *user-facing* glance).

## Contract read (shipped, #19)

`GET /api/stats` → `{queue_depth: int, last_aggregate_ms: int | null}` —
site-independent, so fetched once per poll tick alongside `/sites`, through
the same `get()` seam (404 → fallback `null` → the strip renders "no data
yet", same degradation rule as every other section).

## Design

**Three cells, evidence not diagnosis.** The strip shows `api: ok/unreachable`,
`queue: <depth>`, `aggregates: <age> ago`. It deliberately does *not* say
"worker down" — depth alone can also mean the worker is alive but drowning;
interpretation belongs to the [runbook](../../runbook.md), which the demo
follows on screen. The strip's job is to make the raw signals impossible to
miss.

- **api** — this tick's fetch outcome (the existing `state.error`). Red dot +
  "unreachable" when polls fail; complements the banner so the strip reads
  complete on its own.
- **queue** — the depth number, tabular numerals, no color threshold.
  Rejected alternative: coloring depth against an absolute threshold — any
  cutoff is load-dependent and arbitrary (20/s demo load vs 1,000/s target);
  a climbing number next to a reddening age cell is the honest visual.
- **aggregates** — `last_aggregate_ms` rendered as age ("3s ago"), green dot
  when fresh, **red when older than 30s**, muted "none yet" when `null`.

**Staleness threshold: 30s.** Poll is 5s, so 30s ≈ six missed refreshes — no
flicker at steady state (the future worker drains continuously at ~33× ingest,
so under load the newest folded event tracks now within seconds), and red
lands well inside the demo's 75-second failure beat. Named caveat:
`last_aggregate_ms` is *event time*, so a system with zero traffic also ages
into red. The cell states age honestly; red means "nothing folded in 30s",
which is meaningful exactly when there's load — the only time you care.
Rejected alternative: a worker wall-clock heartbeat field — truthful about
liveness even when idle, but it's a contract addition for a service that
doesn't exist yet; deferred with an issue, trigger being idle-staleness
confusing a real operator.

**Rendering: one more `render*()` function.** `state.stats` joins the state
object; `renderOps()` joins `render()`. Strip markup is a slim full-width bar
between header and banner. Two CSS custom properties added (`--ok`, `--bad`)
alongside the existing `--warning`, tuned for both light and dark schemes.
No new code paths, no framework, consistent with the dashboard's
one-state-object / whole-section-render design.

**Fixture:** `"/stats"` entry with a nonzero depth and a past
`last_aggregate_ms`. Because fixture timestamps are fixed in the past, the
fixture page permanently shows the *stale/red* state — which makes
`?fixture=1` the standing visual verification of the failure rendering, no
worker-kill needed.

## Faults (Gate 2)

- **api down:** poll fails → api cell red + existing banner; last-known depth
  and age stay rendered (banner already marks data as possibly stale).
- **`/stats` absent (older api):** 404 → `null` → all three cells "no data
  yet"-style muted; dashboard still works, per the contract rule.
- **Worker never started / just booted:** `last_aggregate_ms: null` →
  "none yet", muted — indistinguishable from fresh boot, by design.
- Load: one extra GET per poll tick per user (~200 req/s at 1,000 users) onto
  an endpoint that is a `count(*)` on a small SQLite table — inside the api's
  measured ~9,300 QPS headroom.

## Verification ("done" as commands)

```sh
make up
curl -fsS localhost:8081/api/stats            # → {"queue_depth":0,"last_aggregate_ms":null}
# browser: localhost:8081/           → strip renders: api ok · queue 0 · aggregates none yet
# browser: localhost:8081/?fixture=1 → strip renders the stale/red state from fixture
python3 tools/loadgen.py --rate 20 &          # no worker yet: depth climbs on the strip
make check
```

---

*Listed in [docs/superpowers/README.md](../README.md); canon: [CLAUDE.md](../../../CLAUDE.md).*

# Dashboard Service — Design

**Date:** 2026-07-18
**Status:** Approved (staff-eng review passed; both nits adopted — stale-data
banner wording, fixture-sync discipline noted in the PR)
**Branch:** `dashboard` → PR into `main`
**Issues:** #11 (service); read-API contract to be filed for the api owner

## Goal

Land the static frontend from OBJECTIVE.md: per site, top pages by volume,
p75 LCP trend, and active experiments — plain HTML + JS calling the api.
Advances the "platform + three services" deliverable. Built in parallel with
the api (another agent) and ahead of the worker, so its **read contract is
the coordination artifact**: this spec defines it, an issue hands it to the
api owner, and the dashboard renders honestly when endpoints or data are
missing.

## Scope of this PR

- `services/dashboard/` — nginx serving static files + proxying `/api/` to
  the api service; satisfies the service contract (healthcheck, stdout logs,
  owned host port 8081).
- An issue proposing the read contract below to the api owner.
- Not in scope: the read endpoints themselves (api), aggregates (worker),
  the platform status page (#10 — a different page for a different audience).

## The read contract (proposed, negotiated via issue)

All under `/api/` (dashboard-relative; nginx strips the prefix):

| Endpoint | Returns |
|---|---|
| `GET /api/sites` | `["demo", ...]` — sites with data or config |
| `GET /api/sites/{site_id}/pages` | `[{page_url, count, p75_ms, last_seen_ms}]`, sorted by `count` desc, top 20 |
| `GET /api/sites/{site_id}/trend` | `[{bucket_start_ms, p75_ms}]`, time-ascending — *shape only*; bucket width is the worker's decision, the dashboard renders whatever points arrive |
| `GET /api/config/{site_id}` | already exists per OBJECTIVE.md (`experiments`, `sampling_rate`) |

Contract rules: fields are added, never repurposed; absent endpoint (404/502)
and empty array are both first-class renders ("no data yet"), so the
dashboard ships before its data sources and degrades the same way when they
fail later — one behavior, two causes, zero special cases.

## Design

**Serving: nginx:alpine, no build step.** Static `index.html` + one ES
module + one stylesheet, copied into the image. `/healthz` is a static `200`
location. Rejected alternative: a framework + bundler (React/Vite) — a
toolchain and build artifacts to operate for one page of tables and a
sparkline; over-engineering per the grading lens.

**Same-origin proxy, not CORS.** nginx proxies `/api/` → `http://api:8080/`
over the compose network. The browser sees one origin; the api needs no CORS
headers; the api's location is stated once, in the dashboard's nginx config
(it's the dashboard's dependency, so the dashboard owns the pointer).
Rejected alternative: CORS — smears the api's origin into browser JS *and*
CORS middleware into the api, two services changed instead of one file, plus
preflight traffic.

**Rendering: one `render(state)` function.** State = `{sites, site, pages,
trend, config, error}`. Poll every 5s (config every 60s), re-render whole
sections — no framework, no partial-DOM bookkeeping. The p75 trend is an
inline SVG sparkline (no chart library; nothing external — images are
self-contained).

**Fixture mode: `?fixture=1`** loads a committed `fixture.json` instead of
`/api/` — the "done" command for rendering before real data exists, and the
recording fallback. One `if` at the fetch seam, not a parallel code path.

## Faults (Gate 2)

- **api down:** proxy returns 502 → error banner + last-rendered data kept;
  the banner states data may be stale, so frozen numbers are never mistaken
  for live ones. Polling continues (recovers by itself).
- **Endpoints not yet implemented / no data:** "no data yet" empty states —
  indistinguishable from a fresh boot, by design.
- **State:** the dashboard holds none — pure derived view over api responses;
  refresh rebuilds everything. Nothing to back up, nothing in the runbook.
- Load: 1,000 concurrent users × (poll every 5s × 3 requests) ≈ 600 req/s of
  static+proxy traffic — nginx territory; api read QPS is the api's concern
  (measured headroom ~9,300 QPS in the benchmark report).

## Risks / open questions

- **Contract acceptance:** the api owner may reshape endpoints; the fixture
  and `render(state)` isolate the blast radius to one fetch layer.
- **Trend data doesn't exist until the worker lands** (rolling aggregates
  have no time dimension yet). The trend section renders its empty state
  until then — dashboard is not the blocker.

## Verification ("done" as commands)

```sh
make up
curl -fsS -o /dev/null -w '%{http_code}\n' localhost:8081/healthz   # → 200
curl -fsS localhost:8081/ | grep -q perfmon                          # page serves
# browser: localhost:8081/?fixture=1 renders tables + sparkline from fixture
# browser: localhost:8081/ renders empty states (api absent) without errors
make smoke && make check
```

---

*Listed in [docs/superpowers/README.md](../README.md); canon: [CLAUDE.md](../../../CLAUDE.md).*

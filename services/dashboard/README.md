# dashboard

Static frontend on host port 8081: per-site top pages by volume, p75 LCP
trend, active experiments. Plain HTML + one ES module + inline SVG — no
framework, no build step. nginx serves the files and proxies `/api/` to the
api service (same-origin; the api's address is stated only in
[nginx.conf](nginx.conf)).

- Reads the api contract proposed in issue #15; absent endpoints (404/502)
  and empty data both render as "no data yet", so this service works before
  and during api/worker rollout.
- `localhost:8081/?fixture=1` renders from the committed
  [fixture.json](fixture.json) — the contract's executable example, and the
  pre-data verification path. It must change in the same commit as any
  contract change.
- Holds no state: pure derived view; refresh rebuilds everything.
- Ops strip (issue #20) under the header reads `GET /api/stats`: api
  reachability, queue depth, aggregate age (red past 30s). Evidence, not
  diagnosis — interpreting the signals is the
  [runbook](../../docs/runbook.md)'s job. In fixture mode the timestamps are
  past, so `?fixture=1` permanently shows the stale/red state — the standing
  visual check of the failure rendering.

Spec: [2026-07-18-dashboard-design.md](../../docs/superpowers/specs/2026-07-18-dashboard-design.md).

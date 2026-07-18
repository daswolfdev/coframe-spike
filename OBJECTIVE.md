# OBJECTIVE — Platform Engineer Take-Home

**This document is the source of truth for what this repo is for. Every decision
gets judged against it.**

## Scenario

First platform engineer at a 5-engineer startup building a web performance
monitoring product (JS SDK on customer sites reports LCP/page/session events;
customers view a dashboard and configure A/B tests). Today: one VPS, SSH,
`screen`, `tail -f`, no deploys/rollback/staging. Deliver the **minimum platform**
(weeks 1–2 of the job) so the team stops SSHing into prod — plus minimal versions
of the three services it runs.

## What's being evaluated

**Judgment, taste, and operability — not code volume.** "Minimum viable" is ours
to define, and that scoping decision is itself graded: **over-engineered and
under-built are both wrong answers.** The apps are the substrate, not the
deliverable (no four-hour CSS sessions). AI tool use is assumed; self-managed
time is part of the signal — report hours honestly.

## Hard constraints

1. **Runs entirely on a laptop.** Single command (`make up` or equivalent) brings
   everything up, deployed and observable.
2. **Fourth service addable in <15 minutes, without platform changes.**
   Design and *document* the pathway — we do **not** actually add the service,
   just prove the abstraction fits by writing docs a stranger could follow.
3. **Viable scaling pathway to 1,000 events/s and 1,000 concurrent users** —
   demonstrated/argued, not necessarily load-tested, and **nothing beyond that**
   (no planet-scale design).

## The three services (kept small; simplify freely)

1. **Python API (FastAPI)** —
   `POST /events` (JSON: `site_id, page_url, lcp_ms, timestamp, session_id`)
   pushes onto a queue; `GET /config/{site_id}` returns SDK config (experiments,
   sampling rate) from an in-memory map or SQLite.
2. **Go worker** — consumes the queue; rolling aggregates per
   `(site_id, page_url)`: event count, p75 LCP, last-seen. Persists to a store
   of our choice (Postgres/Redis/SQLite all fine).
3. **Frontend** — static dashboard calling the API: top pages by volume per
   site, p75 LCP trend, active experiments. Plain HTML + JS is fine.

The queue between API and worker is an architectural choice — pick one and
justify it in the design doc. Stack is open: pick what you'd actually want to
operate at a 5-person company.

## Deliverables checklist

- [ ] Platform + three services, up with one command, observable
- [ ] 5-min screen recording (non-negotiable): deploy a service, show
      observability, induce a failure, recover from it — linked from README
- [ ] `docs/design.md`: per-service shape (inputs/outputs/where state lives);
      stack choices with one rejected alternative per major component; the one
      decision we're least confident about; what we deliberately didn't build
      and what would trigger building it
- [ ] One-page **user guide** — how the team uses the platform day-to-day
- [ ] One-page **runbook** — for the failure demonstrated in the recording
- [ ] All docs under `/docs` as markdown; public GitHub repo; commit naturally
- [ ] Honest report of hours spent

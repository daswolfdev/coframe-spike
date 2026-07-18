// Package loop runs the worker's claim → fold → flush → ack cycle and
// the startup recovery that makes it effectively-once. Error policy is
// crash-only: any tick error is returned to main, which exits nonzero;
// compose restarts us and recovery is the single, tested repair path.
package loop

import (
	"context"
	"math"
	"time"

	"perfmon/worker/internal/aggregate"
	"perfmon/worker/internal/queue"
)

type Loop struct {
	q     *queue.Queue
	agg   *aggregate.Store
	limit int
	next  int64 // next batch id; monotonic, resumes from agg.db
	stats *Stats
}

// New recovers any in-flight batch from a previous process, then
// positions the batch-id sequence after the last applied batch.
func New(q *queue.Queue, agg *aggregate.Store, limit int) (*Loop, error) {
	l := &Loop{q: q, agg: agg, limit: limit, stats: NewStats(time.Now())}
	if err := l.recover(); err != nil {
		return nil, err
	}
	last, err := agg.LastBatchID()
	if err != nil {
		return nil, err
	}
	l.next = last + 1
	return l, nil
}

// recover resolves claims left by a crash — one outcome per row of the
// design's crash table: applied → finish the ack; not applied → unclaim
// for redelivery.
func (l *Loop) recover() error {
	ids, err := l.q.InFlight()
	if err != nil {
		return err
	}
	for _, id := range ids {
		applied, err := l.agg.Applied(id)
		if err != nil {
			return err
		}
		if applied {
			err = l.q.Ack(id)
		} else {
			err = l.q.Unclaim(id)
		}
		if err != nil {
			return err
		}
	}
	return nil
}

// Tick processes at most one batch, returning how many events it
// consumed. now is the fold's arrival time (bucket boundary).
func (l *Loop) Tick(now time.Time) (int, error) {
	start := time.Now()
	events, err := l.q.Claim(l.next, l.limit)
	if err != nil {
		return 0, err
	}
	if len(events) == 0 {
		l.stats.SawTick(now)
		return 0, nil
	}
	if err := l.agg.Apply(l.next, toSamples(events), now); err != nil {
		return 0, err
	}
	if err := l.q.Ack(l.next); err != nil {
		return 0, err
	}
	l.next++
	l.stats.SawFlush(now, len(events), time.Since(start))
	l.stats.SawTick(now)
	return len(events), nil
}

// toSamples is the queue→aggregate boundary: the contract's REAL lcp_ms
// rounds to whole milliseconds, all the histogram's ≈5% bins can see.
func toSamples(events []queue.Event) []aggregate.Sample {
	samples := make([]aggregate.Sample, len(events))
	for i, e := range events {
		samples[i] = aggregate.Sample{
			SiteID:  e.SiteID,
			PageURL: e.PageURL,
			LCPms:   int64(math.Round(e.LCPms)),
		}
	}
	return samples
}

// Run polls until ctx ends. The first tick error returns immediately
// (crash-only — no in-process retry logic to get wrong).
func (l *Loop) Run(ctx context.Context, poll time.Duration) error {
	t := time.NewTicker(poll)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return nil
		case <-t.C:
			if _, err := l.Tick(time.Now()); err != nil {
				return err
			}
		}
	}
}

// StatsSnapshot serves /stats: counters plus live queue depth.
func (l *Loop) StatsSnapshot() (Snapshot, error) {
	depth, err := l.q.Depth()
	if err != nil {
		return Snapshot{}, err
	}
	return l.stats.Snapshot(depth), nil
}

// Healthy serves /healthz: a tick (even an empty one) completed recently.
func (l *Loop) Healthy(now time.Time) bool {
	return l.stats.TickWithin(now, 5*time.Second)
}

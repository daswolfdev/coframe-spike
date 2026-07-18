package loop

import (
	"path/filepath"
	"testing"
	"time"

	"perfmon/worker/internal/aggregate"
	"perfmon/worker/internal/queue"
)

type fixture struct {
	queuePath, aggPath string
	q                  *queue.Queue
	agg                *aggregate.Store
}

func newFixture(t *testing.T) *fixture {
	t.Helper()
	dir := t.TempDir()
	f := &fixture{
		queuePath: filepath.Join(dir, "queue.db"),
		aggPath:   filepath.Join(dir, "agg.db"),
	}
	f.open(t)
	return f
}

func (f *fixture) open(t *testing.T) {
	t.Helper()
	var err error
	if f.q, err = queue.Open(f.queuePath); err != nil {
		t.Fatal(err)
	}
	if f.agg, err = aggregate.Open(f.aggPath); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { f.q.Close(); f.agg.Close() })
}

// reopen simulates a process restart: close both handles, open fresh ones.
func (f *fixture) reopen(t *testing.T) {
	t.Helper()
	f.q.Close()
	f.agg.Close()
	f.open(t)
}

func (f *fixture) enqueue(t *testing.T, n int) {
	t.Helper()
	for i := range n {
		err := f.q.Enqueue(queue.Event{
			SiteID: "site-1", PageURL: "/p", LCPms: float64(1000 + i),
			TSms: 1700000000000, SessionID: "s1", ReceivedAtMs: 1700000000000,
		})
		if err != nil {
			t.Fatal(err)
		}
	}
}

func (f *fixture) currentCount(t *testing.T) int64 {
	t.Helper()
	count, _, err := f.agg.Current("site-1", "/p")
	if err != nil {
		t.Fatal(err)
	}
	return count
}

func TestTickProcessesBatchOnce(t *testing.T) {
	f := newFixture(t)
	f.enqueue(t, 5)

	l, err := New(f.q, f.agg, 2000)
	if err != nil {
		t.Fatal(err)
	}
	n, err := l.Tick(time.Now())
	if err != nil {
		t.Fatal(err)
	}
	if n != 5 {
		t.Fatalf("consumed %d, want 5", n)
	}
	if got := f.currentCount(t); got != 5 {
		t.Fatalf("current count = %d, want 5", got)
	}
	depth, err := f.q.Depth()
	if err != nil {
		t.Fatal(err)
	}
	if depth != 0 {
		t.Fatalf("depth = %d, want 0", depth)
	}
	// Second tick: nothing left.
	n, err = l.Tick(time.Now())
	if err != nil {
		t.Fatal(err)
	}
	if n != 0 {
		t.Fatalf("second tick consumed %d, want 0", n)
	}
}

// Crash table row 1: died after Claim, before Apply. Recovery must
// unclaim and the batch folds exactly once on redelivery.
func TestRecoverAfterClaimCrash(t *testing.T) {
	f := newFixture(t)
	f.enqueue(t, 4)

	if _, err := f.q.Claim(1, 2000); err != nil { // process died here
		t.Fatal(err)
	}
	f.reopen(t)

	l, err := New(f.q, f.agg, 2000)
	if err != nil {
		t.Fatal(err)
	}
	n, err := l.Tick(time.Now())
	if err != nil {
		t.Fatal(err)
	}
	if n != 4 {
		t.Fatalf("consumed %d after recovery, want 4", n)
	}
	if got := f.currentCount(t); got != 4 {
		t.Fatalf("current count = %d, want 4 (folded once)", got)
	}
}

// Crash table row 2: died after Apply, before Ack. Recovery must finish
// the ack; the batch must NOT double-count.
func TestRecoverAfterApplyCrash(t *testing.T) {
	f := newFixture(t)
	f.enqueue(t, 3)

	events, err := f.q.Claim(1, 2000)
	if err != nil {
		t.Fatal(err)
	}
	if err := f.agg.Apply(1, toSamples(events), time.Now()); err != nil { // died here
		t.Fatal(err)
	}
	f.reopen(t)

	l, err := New(f.q, f.agg, 2000)
	if err != nil {
		t.Fatal(err)
	}
	n, err := l.Tick(time.Now())
	if err != nil {
		t.Fatal(err)
	}
	if n != 0 {
		t.Fatalf("tick after recovery consumed %d, want 0", n)
	}
	if got := f.currentCount(t); got != 3 {
		t.Fatalf("current count = %d, want 3 (no double-fold)", got)
	}
	depth, err := f.q.Depth()
	if err != nil {
		t.Fatal(err)
	}
	if depth != 0 {
		t.Fatalf("depth = %d, want 0 (recovery finished the ack)", depth)
	}
}

// Crash table row 3: died after Ack — clean restart, batch ids continue.
func TestBatchIDsResumeAfterRestart(t *testing.T) {
	f := newFixture(t)
	f.enqueue(t, 2)

	l, err := New(f.q, f.agg, 2000)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := l.Tick(time.Now()); err != nil {
		t.Fatal(err)
	}
	f.reopen(t)

	l2, err := New(f.q, f.agg, 2000)
	if err != nil {
		t.Fatal(err)
	}
	f.enqueue(t, 2)
	if _, err := l2.Tick(time.Now()); err != nil {
		t.Fatal(err)
	}
	last, err := f.agg.LastBatchID()
	if err != nil {
		t.Fatal(err)
	}
	if last != 2 {
		t.Fatalf("LastBatchID = %d, want 2 (monotonic across restart)", last)
	}
}

func TestStatsSnapshot(t *testing.T) {
	f := newFixture(t)
	f.enqueue(t, 5)

	l, err := New(f.q, f.agg, 2000)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now()
	if _, err := l.Tick(now); err != nil {
		t.Fatal(err)
	}
	snap, err := l.StatsSnapshot()
	if err != nil {
		t.Fatal(err)
	}
	if snap.EventsConsumedTotal != 5 {
		t.Fatalf("events_consumed_total = %d, want 5", snap.EventsConsumedTotal)
	}
	if snap.BatchesApplied != 1 {
		t.Fatalf("batches_applied = %d, want 1", snap.BatchesApplied)
	}
	if snap.QueueDepth != 0 {
		t.Fatalf("queue_depth = %d, want 0", snap.QueueDepth)
	}
	// Failure mode this guards: last_flush regressing to epoch seconds —
	// every HTTP surface speaks ms (#61); seconds-scale values are ~1e9.
	if snap.LastFlushMs < now.UnixMilli()-int64(time.Minute/time.Millisecond) {
		t.Fatalf("last_flush_ms = %d, not ms-scale recent", snap.LastFlushMs)
	}
	if !l.Healthy(now) {
		t.Fatal("Healthy = false right after a tick")
	}
	if l.Healthy(now.Add(time.Minute)) {
		t.Fatal("Healthy = true a minute after the last tick")
	}
}

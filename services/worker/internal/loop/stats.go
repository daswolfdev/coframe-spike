package loop

import (
	"slices"
	"sync"
	"time"
)

const ringSize = 256

// Stats is the worker's operational counters. Written by the loop
// goroutine, read by HTTP handlers — hence the mutex.
type Stats struct {
	mu             sync.Mutex
	eventsConsumed uint64
	batchesApplied uint64
	lastTickUnix   int64
	lastFlushUnix  int64
	durs           [ringSize]time.Duration
	nDurs          int // total flushes recorded; ring index = nDurs % ringSize
}

// NewStats seeds lastTick with startup time so /healthz is green while
// the first tick is still pending.
func NewStats(now time.Time) *Stats {
	return &Stats{lastTickUnix: now.Unix()}
}

func (s *Stats) SawTick(now time.Time) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lastTickUnix = now.Unix()
}

func (s *Stats) SawFlush(now time.Time, events int, d time.Duration) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.eventsConsumed += uint64(events)
	s.batchesApplied++
	s.lastFlushUnix = now.Unix()
	s.durs[s.nDurs%ringSize] = d
	s.nDurs++
}

func (s *Stats) TickWithin(now time.Time, within time.Duration) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return now.Unix()-s.lastTickUnix <= int64(within.Seconds())
}

// Snapshot is the /stats JSON shape. Percentiles, never averages.
type Snapshot struct {
	EventsConsumedTotal uint64  `json:"events_consumed_total"`
	BatchesApplied      uint64  `json:"batches_applied"`
	QueueDepth          int64   `json:"queue_depth"`
	LastFlushUnix       int64   `json:"last_flush_unix"`
	FlushP50Ms          float64 `json:"flush_p50_ms"`
	FlushP95Ms          float64 `json:"flush_p95_ms"`
}

func (s *Stats) Snapshot(queueDepth int64) Snapshot {
	s.mu.Lock()
	defer s.mu.Unlock()
	n := min(s.nDurs, ringSize)
	sorted := make([]time.Duration, n)
	copy(sorted, s.durs[:n])
	slices.Sort(sorted)
	pct := func(p int) float64 {
		if n == 0 {
			return 0
		}
		return float64(sorted[(n-1)*p/100].Microseconds()) / 1000
	}
	return Snapshot{
		EventsConsumedTotal: s.eventsConsumed,
		BatchesApplied:      s.batchesApplied,
		QueueDepth:          queueDepth,
		LastFlushUnix:       s.lastFlushUnix,
		FlushP50Ms:          pct(50),
		FlushP95Ms:          pct(95),
	}
}

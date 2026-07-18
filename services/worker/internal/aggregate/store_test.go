package aggregate

import (
	"path/filepath"
	"testing"
	"time"
)

func openTest(t *testing.T) *Store {
	t.Helper()
	s, err := Open(filepath.Join(t.TempDir(), "agg.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { s.Close() })
	return s
}

func samples(n int, site, page string, lcp int64) []Sample {
	out := make([]Sample, n)
	for i := range out {
		out[i] = Sample{SiteID: site, PageURL: page, LCPms: lcp}
	}
	return out
}

// Reads go through the same SQL the dashboard's API will use — the
// schema is the contract, so tests assert against it directly.
func readCurrent(t *testing.T, s *Store, site, page string) (count, p75 int64) {
	t.Helper()
	err := s.db.QueryRow(
		`SELECT count, p75_ms FROM page_current WHERE site_id=? AND page_url=?`,
		site, page).Scan(&count, &p75)
	if err != nil {
		t.Fatal(err)
	}
	return count, p75
}

func TestApplyCreatesBucketAndCurrent(t *testing.T) {
	s := openTest(t)
	now := time.Unix(1_000_000_000, 0)

	err := s.Apply(1, append(samples(4, "site-1", "/a", 2500),
		samples(2, "site-1", "/b", 100)...), now)
	if err != nil {
		t.Fatal(err)
	}

	count, p75 := readCurrent(t, s, "site-1", "/a")
	if count != 4 {
		t.Fatalf("current count = %d, want 4", count)
	}
	if p75 < 2500 || p75 > 2650 {
		t.Fatalf("current p75 = %d, want ≈2500", p75)
	}

	var bucketCount int64
	err = s.db.QueryRow(
		`SELECT count FROM page_minute WHERE site_id=? AND page_url=? AND minute=?`,
		"site-1", "/a", now.Unix()/60).Scan(&bucketCount)
	if err != nil {
		t.Fatal(err)
	}
	if bucketCount != 4 {
		t.Fatalf("bucket count = %d, want 4", bucketCount)
	}

	applied, err := s.Applied(1)
	if err != nil {
		t.Fatal(err)
	}
	if !applied {
		t.Fatal("Applied(1) = false after Apply")
	}
	last, err := s.LastBatchID()
	if err != nil {
		t.Fatal(err)
	}
	if last != 1 {
		t.Fatalf("LastBatchID = %d, want 1", last)
	}
}

func TestApplyAccumulatesSameMinute(t *testing.T) {
	s := openTest(t)
	now := time.Unix(1_000_000_000, 0)

	if err := s.Apply(1, samples(3, "site-1", "/a", 1000), now); err != nil {
		t.Fatal(err)
	}
	if err := s.Apply(2, samples(2, "site-1", "/a", 1000), now.Add(5*time.Second)); err != nil {
		t.Fatal(err)
	}

	count, _ := readCurrent(t, s, "site-1", "/a")
	if count != 5 {
		t.Fatalf("current count = %d, want 5", count)
	}
	var bucketCount int64
	err := s.db.QueryRow(
		`SELECT count FROM page_minute WHERE site_id=? AND page_url=? AND minute=?`,
		"site-1", "/a", now.Unix()/60).Scan(&bucketCount)
	if err != nil {
		t.Fatal(err)
	}
	if bucketCount != 5 {
		t.Fatalf("bucket count = %d, want 5", bucketCount)
	}
}

// Failure mode this guards: page_current.p75 must reflect only the
// trailing 60 minutes, while count stays all-time.
func TestCurrentP75UsesTrailingWindowOnly(t *testing.T) {
	s := openTest(t)
	t0 := time.Unix(1_000_000_000, 0)

	if err := s.Apply(1, samples(100, "site-1", "/a", 100), t0); err != nil {
		t.Fatal(err)
	}
	if err := s.Apply(2, samples(10, "site-1", "/a", 5000), t0.Add(100*time.Minute)); err != nil {
		t.Fatal(err)
	}

	count, p75 := readCurrent(t, s, "site-1", "/a")
	if count != 110 {
		t.Fatalf("all-time count = %d, want 110", count)
	}
	// Old 100ms samples fell out of the window; only 5000ms remain.
	if p75 < 5000 || p75 > 5300 {
		t.Fatalf("trailing p75 = %d, want ≈5000", p75)
	}
}

// Failure mode this guards: the site trend must be a true percentile over
// ALL the site's pages — merged histograms, not per-page p75s averaged.
func TestApplySiteMinuteMergesAcrossPages(t *testing.T) {
	s := openTest(t)
	now := time.Unix(1_000_000_000, 0)

	err := s.Apply(1, append(samples(4, "site-1", "/a", 2500),
		samples(2, "site-1", "/b", 100)...), now)
	if err != nil {
		t.Fatal(err)
	}

	var count, p75 int64
	err = s.db.QueryRow(
		`SELECT count, p75_ms FROM site_minute WHERE site_id=? AND minute=?`,
		"site-1", now.Unix()/60).Scan(&count, &p75)
	if err != nil {
		t.Fatal(err)
	}
	if count != 6 {
		t.Fatalf("site bucket count = %d, want 6", count)
	}
	// 75th of {100,100,2500,2500,2500,2500} sits in the 2500 bin.
	if p75 < 2500 || p75 > 2650 {
		t.Fatalf("site bucket p75 = %d, want ≈2500", p75)
	}
}

// Same page across two batches in one minute: guards the double-count
// where the site fold reuses page hists already merged with their bucket.
func TestApplySiteMinuteAccumulatesSameMinute(t *testing.T) {
	s := openTest(t)
	now := time.Unix(1_000_000_000, 0)

	if err := s.Apply(1, samples(3, "site-1", "/a", 1000), now); err != nil {
		t.Fatal(err)
	}
	if err := s.Apply(2, samples(2, "site-1", "/a", 1000), now.Add(5*time.Second)); err != nil {
		t.Fatal(err)
	}

	var count int64
	err := s.db.QueryRow(
		`SELECT count FROM site_minute WHERE site_id=? AND minute=?`,
		"site-1", now.Unix()/60).Scan(&count)
	if err != nil {
		t.Fatal(err)
	}
	if count != 5 {
		t.Fatalf("site bucket count = %d, want 5", count)
	}
}

func TestAppliedBatchesPruned(t *testing.T) {
	s := openTest(t)
	now := time.Unix(1_000_000_000, 0)

	if err := s.Apply(1, samples(1, "s", "/p", 100), now); err != nil {
		t.Fatal(err)
	}
	if err := s.Apply(1002, samples(1, "s", "/p", 100), now); err != nil {
		t.Fatal(err)
	}
	applied, err := s.Applied(1)
	if err != nil {
		t.Fatal(err)
	}
	if applied {
		t.Fatal("batch 1 should be pruned (1002 - 1000 = 2 > 1)")
	}
}

func TestEmptyStore(t *testing.T) {
	s := openTest(t)
	last, err := s.LastBatchID()
	if err != nil {
		t.Fatal(err)
	}
	if last != 0 {
		t.Fatalf("LastBatchID on empty store = %d, want 0", last)
	}
	applied, err := s.Applied(1)
	if err != nil {
		t.Fatal(err)
	}
	if applied {
		t.Fatal("Applied(1) on empty store = true")
	}
}

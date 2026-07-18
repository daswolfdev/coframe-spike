package queue

import (
	"path/filepath"
	"testing"
)

func openTest(t *testing.T) *Queue {
	t.Helper()
	q, err := Open(filepath.Join(t.TempDir(), "queue.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { q.Close() })
	return q
}

func enqueueN(t *testing.T, q *Queue, n int) {
	t.Helper()
	for i := range n {
		err := q.Enqueue(Event{
			SiteID: "site-1", PageURL: "/p", LCPms: int64(1000 + i),
			SessionID: "s1", TS: 1700000000000,
		})
		if err != nil {
			t.Fatal(err)
		}
	}
}

func TestClaimAckLifecycle(t *testing.T) {
	q := openTest(t)
	enqueueN(t, q, 5)

	got, err := q.Claim(1, 3)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 3 {
		t.Fatalf("claimed %d, want 3", len(got))
	}
	if got[0].LCPms != 1000 {
		t.Fatalf("first claimed LCPms = %d, want 1000 (oldest first)", got[0].LCPms)
	}

	depth, err := q.Depth()
	if err != nil {
		t.Fatal(err)
	}
	if depth != 2 {
		t.Fatalf("depth = %d, want 2", depth)
	}

	inflight, err := q.InFlight()
	if err != nil {
		t.Fatal(err)
	}
	if len(inflight) != 1 || inflight[0] != 1 {
		t.Fatalf("inflight = %v, want [1]", inflight)
	}

	if err := q.Ack(1); err != nil {
		t.Fatal(err)
	}
	inflight, err = q.InFlight()
	if err != nil {
		t.Fatal(err)
	}
	if len(inflight) != 0 {
		t.Fatalf("inflight after ack = %v, want empty", inflight)
	}
}

func TestUnclaimRedelivers(t *testing.T) {
	q := openTest(t)
	enqueueN(t, q, 2)

	if _, err := q.Claim(7, 10); err != nil {
		t.Fatal(err)
	}
	if err := q.Unclaim(7); err != nil {
		t.Fatal(err)
	}
	got, err := q.Claim(8, 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 {
		t.Fatalf("re-claimed %d, want 2", len(got))
	}
}

func TestClaimEmpty(t *testing.T) {
	q := openTest(t)
	got, err := q.Claim(1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 0 {
		t.Fatalf("claimed %d from empty queue, want 0", len(got))
	}
}

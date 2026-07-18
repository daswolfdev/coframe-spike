package aggregate

import (
	"bytes"
	"testing"
)

func TestBinForBounds(t *testing.T) {
	cases := []struct {
		ms   int64
		want int
	}{
		{0, 0}, {50, 0}, {51, 0}, {30000, numBins - 1}, {100000, numBins - 1},
	}
	for _, c := range cases {
		if got := binFor(c.ms); got != c.want {
			t.Errorf("binFor(%d) = %d, want %d", c.ms, got, c.want)
		}
	}
}

func TestP75WithinResolution(t *testing.T) {
	var h Hist
	for range 100 {
		h.Add(2500)
	}
	got := h.P75()
	// Bin upper edge: within +5.1% of the true value, never below it.
	if got < 2500 || got > 2500*106/100 {
		t.Fatalf("P75 = %d, want within [2500, 2650]", got)
	}
}

func TestP75PicksRightBin(t *testing.T) {
	var h Hist
	for range 75 {
		h.Add(100)
	}
	for range 25 {
		h.Add(5000)
	}
	// Rank 75 of 100 lands in the 100ms bin.
	if got := h.P75(); got > 120 {
		t.Fatalf("P75 = %d, want ~100ms bin edge", got)
	}
}

func TestP75Empty(t *testing.T) {
	var h Hist
	if got := h.P75(); got != 0 {
		t.Fatalf("empty P75 = %d, want 0", got)
	}
}

func TestMerge(t *testing.T) {
	var a, b Hist
	for range 100 {
		a.Add(100)
	}
	for range 300 {
		b.Add(5000)
	}
	a.Merge(&b)
	if a.Count() != 400 {
		t.Fatalf("Count = %d, want 400", a.Count())
	}
	got := a.P75() // rank 300 of 400 lands in the 5000ms bin
	if got < 5000 || got > 5000*106/100 {
		t.Fatalf("merged P75 = %d, want within [5000, 5300]", got)
	}
}

func TestEncodeDecodeRoundTrip(t *testing.T) {
	var h Hist
	h.Add(100)
	h.Add(2500)
	h.Add(29000)
	b := h.Encode()
	if len(b) != BlobSize {
		t.Fatalf("blob len = %d, want %d", len(b), BlobSize)
	}
	h2, err := Decode(b)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(h2.Encode(), b) {
		t.Fatal("round trip mismatch")
	}
	if _, err := Decode(b[:10]); err == nil {
		t.Fatal("Decode of short blob should error")
	}
}

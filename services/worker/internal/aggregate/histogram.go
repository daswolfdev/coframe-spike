package aggregate

import (
	"encoding/binary"
	"fmt"
	"math"
)

// LCP histogram: numBins log-spaced bins spanning minMs..maxMs (≈5.1% per
// bin — plenty for a p75). Histograms merge by adding bins, which is the
// property page_current's trailing-window p75 depends on.
const (
	numBins = 128
	minMs   = 50.0
	maxMs   = 30000.0

	// BlobSize is the fixed on-disk encoding: numBins little-endian uint32s.
	BlobSize = numBins * 4
)

var binWidth = math.Log(maxMs/minMs) / numBins

// Hist is a value type; the zero value is an empty histogram.
type Hist [numBins]uint32

func binFor(ms int64) int {
	if float64(ms) <= minMs {
		return 0
	}
	b := int(math.Log(float64(ms)/minMs) / binWidth)
	if b >= numBins {
		b = numBins - 1
	}
	return b
}

// upperMs is a bin's upper edge — the value P75 reports.
func upperMs(bin int) int64 {
	return int64(math.Round(minMs * math.Exp(float64(bin+1)*binWidth)))
}

func (h *Hist) Add(ms int64) { h[binFor(ms)]++ }

func (h *Hist) Merge(o *Hist) {
	for i, c := range o {
		h[i] += c
	}
}

func (h *Hist) Count() uint64 {
	var n uint64
	for _, c := range h {
		n += uint64(c)
	}
	return n
}

// P75 returns the upper edge of the bin holding the 75th percentile, or 0
// for an empty histogram.
func (h *Hist) P75() int64 {
	total := h.Count()
	if total == 0 {
		return 0
	}
	rank := float64(total) * 0.75
	var cum float64
	for i, c := range h {
		cum += float64(c)
		if cum >= rank {
			return upperMs(i)
		}
	}
	return upperMs(numBins - 1)
}

func (h *Hist) Encode() []byte {
	b := make([]byte, BlobSize)
	for i, c := range h {
		binary.LittleEndian.PutUint32(b[i*4:], c)
	}
	return b
}

func Decode(b []byte) (*Hist, error) {
	if len(b) != BlobSize {
		return nil, fmt.Errorf("hist blob: got %d bytes, want %d", len(b), BlobSize)
	}
	var h Hist
	for i := range h {
		h[i] = binary.LittleEndian.Uint32(b[i*4:])
	}
	return &h, nil
}

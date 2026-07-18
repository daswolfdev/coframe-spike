"""Read side of the worker's LCP histogram encoding (functional core, no ctx).

Mirrors services/worker/internal/aggregate/histogram.go: 128 log-spaced
bins over 50-30000 ms, encoded as little-endian uint32s. The blob format
is part of the agg.db schema-as-contract (#11, #15) — change it in the
worker and here together.
"""

import math
import struct

NUM_BINS = 128
_MIN_MS = 50.0
_MAX_MS = 30000.0
_BIN_WIDTH = math.log(_MAX_MS / _MIN_MS) / NUM_BINS

Hist = tuple[int, ...]


def hist_decode(blob: bytes) -> Hist:
    if len(blob) != NUM_BINS * 4:
        msg = f"hist blob: got {len(blob)} bytes, want {NUM_BINS * 4}"
        raise ValueError(msg)
    return struct.unpack(f"<{NUM_BINS}I", blob)


def hist_merge(a: Hist, b: Hist) -> Hist:
    return tuple(x + y for x, y in zip(a, b, strict=True))


def hist_p75(h: Hist) -> int:
    """Upper edge of the bin holding the 75th percentile; 0 when empty."""
    total = sum(h)
    if total == 0:
        return 0
    rank = total * 0.75
    cum = 0
    for i, count in enumerate(h):
        cum += count
        if cum >= rank:
            return _upper_ms(i)
    return _upper_ms(NUM_BINS - 1)


def _upper_ms(bin_idx: int) -> int:
    # int(x + 0.5), not round(): Go's math.Round rounds half away from zero.
    return int(_MIN_MS * math.exp((bin_idx + 1) * _BIN_WIDTH) + 0.5)

"""The worker's histogram encoding, read side (api/hist.py).

Test vectors are derived by hand from the Go write side
(services/worker/internal/aggregate/histogram.go): 128 log-spaced bins
over 50-30000 ms, bin width ln(600)/128; a value v lands in bin
int(ln(v/50)/width) and p75 reports the bin's upper edge
round(50*exp((bin+1)*width)). So 100 ms -> bin 13, upper edge 101;
1000 ms -> bin 59, upper edge 1003.
"""

import struct

import pytest

from api.hist import hist_decode, hist_merge, hist_p75


def blob(bins: dict[int, int]) -> bytes:
    counts = [0] * 128
    for i, c in bins.items():
        counts[i] = c
    return struct.pack("<128I", *counts)


def test_decode_roundtrip() -> None:
    h = hist_decode(blob({13: 3, 59: 1}))
    assert h[13] == 3
    assert h[59] == 1
    assert sum(h) == 4


def test_decode_rejects_wrong_size() -> None:
    with pytest.raises(ValueError, match="hist blob"):
        hist_decode(b"\x00" * 12)


def test_p75_empty_is_zero() -> None:
    assert hist_p75(hist_decode(blob({}))) == 0


def test_p75_reports_bin_upper_edge() -> None:
    # rank = 4 * 0.75 = 3; cumulative count crosses 3 in bin 13.
    assert hist_p75(hist_decode(blob({13: 3, 59: 1}))) == 101
    assert hist_p75(hist_decode(blob({59: 4}))) == 1003


def test_merge_adds_bins() -> None:
    merged = hist_merge(hist_decode(blob({13: 3})), hist_decode(blob({13: 1, 59: 1})))
    assert merged[13] == 4
    assert merged[59] == 1

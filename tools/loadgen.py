#!/usr/bin/env python3
"""Demo load generator (#18): steady POST /events traffic with a sent-count.

Stdlib only, runs on stock macOS/Linux python3. The final sent-count is the
number the demo's recover beat checks against aggregated counts to prove no
events were lost (docs/demo.md).

    python3 tools/loadgen.py [--rate 20] [--api http://localhost:8000]

Ctrl-C stops it and prints the final count.
"""

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request

# Sites/pages mirror the api's config seed and the dashboard fixture, with a
# rough LCP baseline per page so p75s differ visibly on the dashboard.
PAGES = [
    ("demo", "/checkout", 2200),
    ("demo", "/", 1500),
    ("demo", "/product/battle-axe", 1900),
    ("demo", "/search", 2600),
    ("demo", "/cart", 1400),
    ("acme", "/landing", 1100),
]
WEIGHTS = [6, 5, 3, 2, 2, 1]


def send(api: str, sent: int) -> None:
    site, page, base_lcp = random.choices(PAGES, WEIGHTS)[0]
    event = {
        "site_id": site,
        "page_url": page,
        "lcp_ms": round(max(50.0, random.lognormvariate(0, 0.4) * base_lcp), 1),
        "timestamp": int(time.time() * 1000),
        "session_id": f"s-{sent % 500:03d}",  # ~500 rolling sessions
    }
    request = urllib.request.Request(
        f"{api}/events",
        data=json.dumps(event).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        response.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rate", type=float, default=20, help="events/s (default 20)")
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()

    sent = errors = 0
    interval = 1.0 / args.rate
    next_report = time.monotonic() + 1.0
    print(f"loadgen: {args.rate:g} events/s -> {args.api}/events (Ctrl-C to stop)")
    try:
        while True:
            started = time.monotonic()
            try:
                send(args.api, sent)
                sent += 1
            except (urllib.error.URLError, OSError) as exc:
                errors += 1
                print(f"loadgen: error ({exc}) sent={sent} errors={errors}")
            if time.monotonic() >= next_report:
                print(f"loadgen: sent={sent} errors={errors}")
                next_report += 1.0
            time.sleep(max(0.0, interval - (time.monotonic() - started)))
    except KeyboardInterrupt:
        print(f"\nloadgen: FINAL sent={sent} errors={errors}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

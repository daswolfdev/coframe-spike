"""Spike: can SQLite (WAL) carry the objective's load targets with zero other infra?

Targets: 1,000 events/s ingest; 1,000 concurrent dashboard users (~a few hundred QPS).
Phases:
  1. enqueue-only: single-row autocommit INSERTs (models per-HTTP-request enqueue)
  2. enqueue + concurrent batch-dequeue from a second PROCESS (models API + worker
     contending on the same queue.db file — the real write-lock risk)
  3. 32 reader threads querying aggregates while a writer batch-upserts
     (models dashboard reads during worker flushes)
"""
import os
import sqlite3
import statistics
import sys
import time
import threading
from multiprocessing import Process, Queue

# DB files go in the dir given as argv[1] — use a real disk, not tmpfs,
# or the fsync-ish parts of the measurement are against RAM.
DIR = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
QDB = os.path.join(DIR, "queue.db")
ADB = os.path.join(DIR, "agg.db")
DUR = 5.0

PAYLOAD = '{"site_id":"s1","page_url":"/checkout","lcp_ms":2100,"timestamp":1752800000,"session_id":"abc123"}'


def connect(path):
    c = sqlite3.connect(path, timeout=5.0, isolation_level=None)  # autocommit
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA busy_timeout=5000")
    return c


def fresh(path, schema):
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(path + suffix)
        except FileNotFoundError:
            pass
    c = connect(path)
    c.executescript(schema)
    c.close()


def enqueue_proc(dur, out):
    c = connect(QDB)
    n, lat = 0, []
    end = time.perf_counter() + dur
    while time.perf_counter() < end:
        t0 = time.perf_counter()
        c.execute("INSERT INTO events(payload) VALUES (?)", (PAYLOAD,))
        lat.append(time.perf_counter() - t0)
        n += 1
    p95 = statistics.quantiles(lat, n=100)[94] * 1000
    out.put(("enqueue", n, p95, max(lat) * 1000))


def dequeue_proc(dur, out):
    c = connect(QDB)
    drained = 0
    end = time.perf_counter() + dur
    while time.perf_counter() < end:
        c.execute("BEGIN IMMEDIATE")
        mx, cnt = c.execute(
            "SELECT max(id), count(*) FROM (SELECT id FROM events ORDER BY id LIMIT 2000)"
        ).fetchone()
        if mx is not None:
            c.execute("DELETE FROM events WHERE id <= ?", (mx,))
            drained += cnt
        c.execute("COMMIT")
        time.sleep(0.05)  # worker polls ~20x/s
    out.put(("dequeue", drained))


def phase1():
    fresh(QDB, "CREATE TABLE events(id INTEGER PRIMARY KEY, payload TEXT)")
    out = Queue()
    p = Process(target=enqueue_proc, args=(DUR, out))
    p.start(); p.join()
    _, n, p95, worst = out.get()
    print(f"phase1 enqueue-only        : {n / DUR:8.0f} inserts/s   p95 {p95:.2f}ms  max {worst:.1f}ms")


def phase2():
    fresh(QDB, "CREATE TABLE events(id INTEGER PRIMARY KEY, payload TEXT)")
    out = Queue()
    procs = [Process(target=enqueue_proc, args=(DUR, out)),
             Process(target=dequeue_proc, args=(DUR, out))]
    for p in procs: p.start()
    for p in procs: p.join()
    results = {}
    while not out.empty():
        r = out.get()
        results[r[0]] = r[1:]
    n, p95, worst = results["enqueue"]
    print(f"phase2 enqueue w/ dequeuer : {n / DUR:8.0f} inserts/s   p95 {p95:.2f}ms  max {worst:.1f}ms   drained {results['dequeue'][0] / DUR:.0f}/s")


def reader_thread(stop, counts, lats, i):
    c = connect(ADB)
    site = f"site{i % 20}"
    while not stop.is_set():
        t0 = time.perf_counter()
        c.execute(
            "SELECT page_url, cnt, p75 FROM agg WHERE site_id=? ORDER BY cnt DESC LIMIT 10",
            (site,),
        ).fetchall()
        lats.append(time.perf_counter() - t0)
        counts[i] += 1


def phase3():
    fresh(ADB, "CREATE TABLE agg(site_id TEXT, page_url TEXT, cnt INT, p75 REAL, last_seen INT, PRIMARY KEY(site_id, page_url))")
    c = connect(ADB)
    c.execute("BEGIN")
    for s in range(20):
        for p in range(500):
            c.execute("INSERT INTO agg VALUES (?,?,?,?,?)",
                      (f"site{s}", f"/page/{p}", p * 7, 1800.0 + p, 1752800000))
    c.execute("COMMIT")

    stop = threading.Event()
    counts = [0] * 32
    lats = []
    readers = [threading.Thread(target=reader_thread, args=(stop, counts, lats, i)) for i in range(32)]
    for t in readers: t.start()

    # concurrent writer: worker flushing a 500-row upsert batch 4x/s
    end = time.perf_counter() + DUR
    flushes = 0
    while time.perf_counter() < end:
        c.execute("BEGIN IMMEDIATE")
        for p in range(500):
            c.execute(
                "INSERT INTO agg VALUES (?,?,?,?,?) ON CONFLICT(site_id,page_url) "
                "DO UPDATE SET cnt=cnt+excluded.cnt, p75=excluded.p75, last_seen=excluded.last_seen",
                (f"site{p % 20}", f"/page/{p}", 3, 1900.0, 1752800001))
        c.execute("COMMIT")
        flushes += 1
        time.sleep(0.25)
    stop.set()
    for t in readers: t.join()
    qps = sum(counts) / DUR
    p95 = statistics.quantiles(lats, n=100)[94] * 1000
    print(f"phase3 32 readers + writer : {qps:8.0f} queries/s   p95 {p95:.2f}ms  ({flushes} upsert batches of 500 landed)")


if __name__ == "__main__":
    print(f"sqlite {sqlite3.sqlite_version}, WAL, synchronous=NORMAL, {DUR:.0f}s per phase")
    phase1()
    phase2()
    phase3()

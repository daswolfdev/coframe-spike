# Data-Intensive Systems

A compact distillation of Martin Kleppmann's *Designing Data-Intensive
Applications* — the durable ideas about how data systems store, move, and reason
about state at scale. This is the *vocabulary and the trade-offs*.

> The prime directive: **a data-intensive system is defined by its data — its
> volume, complexity, and rate of change — not its CPU.** The whole job is moving
> the right data to the right place, correctly, as the system and its schema
> evolve.

---

## The three goals

Every design decision is in service of one of these — name which one when you
make a trade-off.

- **Reliability** — works correctly *despite* faults (hardware, software, human).
  Fault ≠ failure; build systems that tolerate faults so they don't become
  failures. Deliberately trigger faults (fault injection) to prove it.
- **Scalability** — copes with growth in load. Describe load with concrete
  **parameters** (req/s, read/write ratio, fan-out), and performance with
  **percentiles** (p95/p99), **never averages** — tail latency is what users feel.
- **Maintainability** — operable, simple, evolvable. Most cost is *after* the
  first ship; optimize for the people who come later.

## Data models & storage

- **Pick the model for the access shape.** Relational for many-to-many and ad-hoc
  joins; document for tree-shaped, locality-heavy aggregates; graph for densely
  interconnected data. Most "NoSQL vs SQL" debates are really *locality vs joins*.
- **Storage engines split two ways.** **LSM-trees** (log-structured: fast writes,
  compaction, e.g. RocksDB) vs **B-trees** (in-place, read-optimized, the classic
  RDBMS index). Writes-heavy ⇒ LSM; reads-heavy with predictable latency ⇒ B-tree.
- **OLTP vs OLAP are different machines.** Transaction processing (small,
  keyed, low-latency) and analytics (large scans, columnar, aggregates) want
  opposite layouts. Don't run a warehouse query against your serving store.

## Encoding & evolution

- **Schema is a contract across time and space.** Old and new code coexist during
  any rolling deploy, so favor formats with **backward compatibility** (new code
  reads old data) and **forward compatibility** (old code reads new data).
- **Add, don't repurpose.** New optional fields are safe; changing the meaning of
  an existing field is a silent break.
- **Prefer explicit schemas** (Protobuf/Avro/typed JSON contracts) over implicit
  ones — they make evolution checkable rather than hoped-for.

## Replication & partitioning *(when you scale)*

- **Replication** copies the same data to many nodes for availability and read
  scale: **single-leader** (simple, the default), **multi-leader** (multi-region
  writes, conflict resolution), **leaderless** (quorums, Dynamo-style). Cost is
  **replication lag** and the resulting read-your-writes / monotonic-read anomalies.
- **Partitioning (sharding)** splits *different* data across nodes for write scale.
  Balance by key range or hash; watch for **hot spots** and the cost of
  cross-partition transactions and secondary indexes.
- **Scale when a load parameter forces it, not a hunch.** Bank the scale lessons;
  take the consistency lessons now.

## Transactions & consistency

- **ACID is a marketing term until you read the isolation level.** "Isolation"
  ranges from read-committed → snapshot/repeatable-read → serializable; each
  blocks a specific class of race (dirty/non-repeatable reads, write skew, lost
  updates). Know which anomaly you're paying to prevent.
- **Distributed systems lie.** Networks drop/delay/duplicate, clocks drift (never
  trust wall-clock ordering across nodes), nodes fail partially. Design for it.
- **The strong guarantees, precisely:** **linearizability** (behaves like one
  copy, real-time order), **causal/ordering** guarantees, and **consensus**
  (agree one value despite faults — the hard core under leader election, locks,
  uniqueness). **CAP** is the crude version: under a partition, choose
  consistency *or* availability.

## Derived data & event logs

The book's payoff chapter.

- **Split systems of record from derived data.** The **system of record** is the
  authoritative source; everything else — caches, indexes, materialized views,
  search indexes — is **derived** and can be **rebuilt from the source**. Never
  let two systems both claim to be the truth.
- **An ordered event log is a great system of record.** Appending immutable facts
  and deriving state by replaying them gives you auditability, time travel, and
  trivially rebuildable read models — *event sourcing* and *change data capture*
  are the same idea from two ends.
- **The "unbundled database":** treat the log as the kernel and let each consumer
  maintain its own derived view (stream processing). State is a fold over events.

---

*A data system's hardest problem is keeping derived data faithful to its source.
Event sourcing answers it by making the source a log and everything else a
rebuildable fold.*

*Part of the repo canon — see [CLAUDE.md](../CLAUDE.md).*

// Package queue is the worker's side of the producer-owned queue table.
// Schema authority: services/api/api/db.py (QUEUE_SCHEMA, negotiated on
// issue #11) — the DDL below is that schema verbatim, duplicated so
// either process can start first on a fresh volume. claim_id is
// consumer-owned effectively-once state: NULL = unclaimed; the api
// never reads or writes it.
package queue

import (
	"database/sql"

	"perfmon/worker/internal/db"
)

// Event is one row of the queue contract. Fields are additive-only
// (add, don't repurpose).
type Event struct {
	SiteID       string
	PageURL      string
	LCPms        float64
	TSms         int64 // client event time, epoch ms; stored, not trusted
	SessionID    string
	ReceivedAtMs int64 // producer clock at enqueue, epoch ms
}

type Queue struct{ db *sql.DB }

func Open(path string) (*Queue, error) {
	d, err := db.Open(path)
	if err != nil {
		return nil, err
	}
	err = db.ExecAll(d,
		`CREATE TABLE IF NOT EXISTS queue (
			id INTEGER PRIMARY KEY,          -- insertion order = claim order
			site_id TEXT NOT NULL,
			page_url TEXT NOT NULL,
			lcp_ms REAL NOT NULL,
			ts_ms INTEGER NOT NULL,          -- client event time, epoch ms
			session_id TEXT NOT NULL,
			received_at_ms INTEGER NOT NULL, -- api clock at enqueue, epoch ms
			claim_id INTEGER                 -- consumer-owned; NULL = unclaimed (#11)
		)`,
		`CREATE INDEX IF NOT EXISTS queue_unclaimed
			ON queue (id) WHERE claim_id IS NULL`,
	)
	if err != nil {
		d.Close()
		return nil, err
	}
	return &Queue{db: d}, nil
}

func (q *Queue) Close() error { return q.db.Close() }

// Enqueue is the producer path — used by tests standing in for the api.
// claim_id is deliberately omitted, as the api's INSERT is.
func (q *Queue) Enqueue(e Event) error {
	_, err := q.db.Exec(
		`INSERT INTO queue (site_id, page_url, lcp_ms, ts_ms, session_id, received_at_ms)
		 VALUES (?, ?, ?, ?, ?, ?)`,
		e.SiteID, e.PageURL, e.LCPms, e.TSms, e.SessionID, e.ReceivedAtMs)
	return err
}

// Claim marks up to limit unclaimed events (oldest first) with batchID
// and returns them. One UPDATE…RETURNING statement, so it is atomic.
func (q *Queue) Claim(batchID int64, limit int) ([]Event, error) {
	rows, err := q.db.Query(`
		UPDATE queue SET claim_id = ?
		WHERE id IN (SELECT id FROM queue WHERE claim_id IS NULL
		             ORDER BY id LIMIT ?)
		RETURNING site_id, page_url, lcp_ms, ts_ms, session_id, received_at_ms`,
		batchID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Event
	for rows.Next() {
		var e Event
		if err := rows.Scan(&e.SiteID, &e.PageURL, &e.LCPms, &e.TSms, &e.SessionID, &e.ReceivedAtMs); err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// Ack deletes a batch's rows — the final transaction of the protocol.
func (q *Queue) Ack(batchID int64) error {
	_, err := q.db.Exec(`DELETE FROM queue WHERE claim_id = ?`, batchID)
	return err
}

// Unclaim returns a batch to the unclaimed pool (recovery path for a
// batch that never reached its agg.db marker).
func (q *Queue) Unclaim(batchID int64) error {
	_, err := q.db.Exec(`UPDATE queue SET claim_id = NULL WHERE claim_id = ?`, batchID)
	return err
}

// InFlight lists claim ids left behind by a previous process.
func (q *Queue) InFlight() ([]int64, error) {
	rows, err := q.db.Query(
		`SELECT DISTINCT claim_id FROM queue WHERE claim_id IS NOT NULL`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

// Depth counts unclaimed events — the platform's named failure signal:
// sustained growth means the worker is down or drowning. (The api's
// /stats queue_depth counts all rows; the two differ by at most one
// in-flight batch.)
func (q *Queue) Depth() (int64, error) {
	var n int64
	err := q.db.QueryRow(
		`SELECT COUNT(*) FROM queue WHERE claim_id IS NULL`).Scan(&n)
	return n, err
}

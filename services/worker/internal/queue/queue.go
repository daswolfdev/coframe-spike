// Package queue owns queue.db: the events schema (the two-service
// contract the API will conform to) and the claim/ack protocol that
// gives the worker effectively-once batches.
package queue

import (
	"database/sql"

	"perfmon/worker/internal/db"
)

// Event is one row of the queue contract. Fields are additive-only
// (add, don't repurpose).
type Event struct {
	SiteID    string
	PageURL   string
	LCPms     int64
	SessionID string
	TS        int64 // client-reported epoch ms; stored, not trusted
}

type Queue struct{ db *sql.DB }

func Open(path string) (*Queue, error) {
	d, err := db.Open(path)
	if err != nil {
		return nil, err
	}
	err = db.ExecAll(d,
		`CREATE TABLE IF NOT EXISTS events (
			id         INTEGER PRIMARY KEY,
			site_id    TEXT NOT NULL,
			page_url   TEXT NOT NULL,
			lcp_ms     INTEGER NOT NULL,
			session_id TEXT NOT NULL,
			ts         INTEGER NOT NULL,
			claim_id   INTEGER
		)`,
		`CREATE INDEX IF NOT EXISTS events_unclaimed
			ON events(id) WHERE claim_id IS NULL`,
	)
	if err != nil {
		d.Close()
		return nil, err
	}
	return &Queue{db: d}, nil
}

func (q *Queue) Close() error { return q.db.Close() }

func (q *Queue) Enqueue(e Event) error {
	_, err := q.db.Exec(
		`INSERT INTO events (site_id, page_url, lcp_ms, session_id, ts)
		 VALUES (?, ?, ?, ?, ?)`,
		e.SiteID, e.PageURL, e.LCPms, e.SessionID, e.TS)
	return err
}

// Claim marks up to limit unclaimed events (oldest first) with batchID
// and returns them. One UPDATE…RETURNING statement, so it is atomic.
func (q *Queue) Claim(batchID int64, limit int) ([]Event, error) {
	rows, err := q.db.Query(`
		UPDATE events SET claim_id = ?
		WHERE id IN (SELECT id FROM events WHERE claim_id IS NULL
		             ORDER BY id LIMIT ?)
		RETURNING site_id, page_url, lcp_ms, session_id, ts`,
		batchID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Event
	for rows.Next() {
		var e Event
		if err := rows.Scan(&e.SiteID, &e.PageURL, &e.LCPms, &e.SessionID, &e.TS); err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// Ack deletes a batch's rows — the final transaction of the protocol.
func (q *Queue) Ack(batchID int64) error {
	_, err := q.db.Exec(`DELETE FROM events WHERE claim_id = ?`, batchID)
	return err
}

// Unclaim returns a batch to the unclaimed pool (recovery path for a
// batch that never reached its agg.db marker).
func (q *Queue) Unclaim(batchID int64) error {
	_, err := q.db.Exec(`UPDATE events SET claim_id = NULL WHERE claim_id = ?`, batchID)
	return err
}

// InFlight lists claim ids left behind by a previous process.
func (q *Queue) InFlight() ([]int64, error) {
	rows, err := q.db.Query(
		`SELECT DISTINCT claim_id FROM events WHERE claim_id IS NOT NULL`)
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
// sustained growth means the worker is down or drowning.
func (q *Queue) Depth() (int64, error) {
	var n int64
	err := q.db.QueryRow(
		`SELECT COUNT(*) FROM events WHERE claim_id IS NULL`).Scan(&n)
	return n, err
}

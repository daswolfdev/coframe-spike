package aggregate

import (
	"database/sql"
	"errors"
	"time"

	"perfmon/worker/internal/db"
)

// Sample is the aggregate-side view of one event — just what folding
// needs, so this package doesn't import queue.
type Sample struct {
	SiteID  string
	PageURL string
	LCPms   int64
}

const (
	trailingMinutes = 60   // window for page_current.p75_ms
	keepBatches     = 1000 // applied_batches retained for recovery
)

// Store owns agg.db. The worker is agg.db's ONLY writer (repo
// invariant); page_minute is the system of record for aggregates,
// page_current is derived from it, applied_batches is the
// effectively-once marker.
type Store struct{ db *sql.DB }

func Open(path string) (*Store, error) {
	d, err := db.Open(path)
	if err != nil {
		return nil, err
	}
	err = db.ExecAll(d,
		`CREATE TABLE IF NOT EXISTS page_minute (
			site_id   TEXT NOT NULL,
			page_url  TEXT NOT NULL,
			minute    INTEGER NOT NULL,
			count     INTEGER NOT NULL,
			hist      BLOB NOT NULL,
			p75_ms    INTEGER NOT NULL,
			last_seen INTEGER NOT NULL,
			PRIMARY KEY (site_id, page_url, minute)
		)`,
		`CREATE TABLE IF NOT EXISTS site_minute (
			site_id   TEXT NOT NULL,
			minute    INTEGER NOT NULL,
			count     INTEGER NOT NULL,
			hist      BLOB NOT NULL,
			p75_ms    INTEGER NOT NULL,
			last_seen INTEGER NOT NULL,
			PRIMARY KEY (site_id, minute)
		)`,
		`CREATE TABLE IF NOT EXISTS page_current (
			site_id   TEXT NOT NULL,
			page_url  TEXT NOT NULL,
			count     INTEGER NOT NULL,
			p75_ms    INTEGER NOT NULL,
			last_seen INTEGER NOT NULL,
			PRIMARY KEY (site_id, page_url)
		)`,
		`CREATE TABLE IF NOT EXISTS applied_batches (
			batch_id   INTEGER PRIMARY KEY,
			applied_at INTEGER NOT NULL
		)`,
	)
	if err != nil {
		d.Close()
		return nil, err
	}
	return &Store{db: d}, nil
}

func (s *Store) Close() error { return s.db.Close() }

func (s *Store) LastBatchID() (int64, error) {
	var id int64
	err := s.db.QueryRow(
		`SELECT COALESCE(MAX(batch_id), 0) FROM applied_batches`).Scan(&id)
	return id, err
}

func (s *Store) Applied(batchID int64) (bool, error) {
	var n int
	err := s.db.QueryRow(
		`SELECT COUNT(*) FROM applied_batches WHERE batch_id = ?`,
		batchID).Scan(&n)
	return n > 0, err
}

// Apply folds one batch in a single transaction: minute-bucket upserts,
// page_current recompute for touched pages, the batch marker that makes
// redelivery a no-op, and marker pruning. Buckets use worker arrival
// time (now), never the client-reported ts — client clocks lie.
func (s *Store) Apply(batchID int64, samples []Sample, now time.Time) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	minute := now.Unix() / 60
	nowUnix := now.Unix()

	type key struct{ site, page string }
	added := map[key]*Hist{}
	nAdded := map[key]int64{}
	for _, smp := range samples {
		k := key{smp.SiteID, smp.PageURL}
		if added[k] == nil {
			added[k] = &Hist{}
		}
		added[k].Add(smp.LCPms)
		nAdded[k]++
	}

	for k, h := range added {
		// Fold into this minute's bucket (h becomes the bucket total).
		var blob []byte
		err := tx.QueryRow(
			`SELECT hist FROM page_minute WHERE site_id=? AND page_url=? AND minute=?`,
			k.site, k.page, minute).Scan(&blob)
		switch {
		case errors.Is(err, sql.ErrNoRows):
		case err != nil:
			return err
		default:
			old, derr := Decode(blob)
			if derr != nil {
				return derr
			}
			h.Merge(old)
		}
		if _, err := tx.Exec(
			`INSERT INTO page_minute (site_id, page_url, minute, count, hist, p75_ms, last_seen)
			 VALUES (?, ?, ?, ?, ?, ?, ?)
			 ON CONFLICT (site_id, page_url, minute) DO UPDATE SET
			   count = excluded.count, hist = excluded.hist,
			   p75_ms = excluded.p75_ms, last_seen = excluded.last_seen`,
			k.site, k.page, minute, h.Count(), h.Encode(), h.P75(), nowUnix); err != nil {
			return err
		}

		// Recompute the running row's p75 from the trailing window
		// (sees this tx's own bucket write); count accumulates all-time.
		trailing, err := trailingHist(tx, k.site, k.page, minute-trailingMinutes)
		if err != nil {
			return err
		}
		if _, err := tx.Exec(
			`INSERT INTO page_current (site_id, page_url, count, p75_ms, last_seen)
			 VALUES (?, ?, ?, ?, ?)
			 ON CONFLICT (site_id, page_url) DO UPDATE SET
			   count = page_current.count + excluded.count,
			   p75_ms = excluded.p75_ms, last_seen = excluded.last_seen`,
			k.site, k.page, nAdded[k], trailing.P75(), nowUnix); err != nil {
			return err
		}
	}

	// Site-level minute buckets: the dashboard trend's source (#15). A
	// true per-site p75 needs the merged histogram — per-page p75s don't
	// compose — so the fold happens here, where histograms live; the api
	// reads p75_ms as a plain column. Built from samples, not `added`:
	// the page loop above mutated those hists into bucket totals, and
	// re-merging totals would double-count prior batches.
	siteAdded := map[string]*Hist{}
	for _, smp := range samples {
		if siteAdded[smp.SiteID] == nil {
			siteAdded[smp.SiteID] = &Hist{}
		}
		siteAdded[smp.SiteID].Add(smp.LCPms)
	}
	for site, h := range siteAdded {
		var blob []byte
		err := tx.QueryRow(
			`SELECT hist FROM site_minute WHERE site_id=? AND minute=?`,
			site, minute).Scan(&blob)
		switch {
		case errors.Is(err, sql.ErrNoRows):
		case err != nil:
			return err
		default:
			old, derr := Decode(blob)
			if derr != nil {
				return derr
			}
			h.Merge(old)
		}
		if _, err := tx.Exec(
			`INSERT INTO site_minute (site_id, minute, count, hist, p75_ms, last_seen)
			 VALUES (?, ?, ?, ?, ?, ?)
			 ON CONFLICT (site_id, minute) DO UPDATE SET
			   count = excluded.count, hist = excluded.hist,
			   p75_ms = excluded.p75_ms, last_seen = excluded.last_seen`,
			site, minute, h.Count(), h.Encode(), h.P75(), nowUnix); err != nil {
			return err
		}
	}

	if _, err := tx.Exec(
		`INSERT INTO applied_batches (batch_id, applied_at) VALUES (?, ?)`,
		batchID, nowUnix); err != nil {
		return err
	}
	if _, err := tx.Exec(
		`DELETE FROM applied_batches WHERE batch_id <= ?`,
		batchID-keepBatches); err != nil {
		return err
	}
	return tx.Commit()
}

func trailingHist(tx *sql.Tx, site, page string, sinceMinute int64) (*Hist, error) {
	rows, err := tx.Query(
		`SELECT hist FROM page_minute WHERE site_id=? AND page_url=? AND minute > ?`,
		site, page, sinceMinute)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var total Hist
	for rows.Next() {
		var blob []byte
		if err := rows.Scan(&blob); err != nil {
			return nil, err
		}
		h, err := Decode(blob)
		if err != nil {
			return nil, err
		}
		total.Merge(h)
	}
	return &total, rows.Err()
}

// Current reads one running row — used by tests and ops tooling; the
// dashboard's API reads the same schema directly.
func (s *Store) Current(site, page string) (count, p75 int64, err error) {
	err = s.db.QueryRow(
		`SELECT count, p75_ms FROM page_current WHERE site_id=? AND page_url=?`,
		site, page).Scan(&count, &p75)
	return count, p75, err
}

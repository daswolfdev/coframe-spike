// Package db opens SQLite the one blessed way: WAL, NORMAL sync, 5s busy
// timeout, immediate write transactions — the exact configuration the
// throughput report (docs/reports/2026-07-18-sqlite-wal-throughput.md)
// measured. Every store in the worker goes through here so the decision
// has one owner.
package db

import (
	"database/sql"

	_ "modernc.org/sqlite"
)

// Open returns a pool capped at one connection: the worker is a single
// sequential writer, and one connection means its transactions queue
// in-process instead of racing for the file lock.
func Open(path string) (*sql.DB, error) {
	dsn := "file:" + path +
		"?_txlock=immediate" +
		"&_pragma=journal_mode(WAL)" +
		"&_pragma=synchronous(NORMAL)" +
		"&_pragma=busy_timeout(5000)"
	d, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	d.SetMaxOpenConns(1)
	return d, nil
}

// ExecAll runs DDL statements one by one (the driver does not accept
// multi-statement Exec strings).
func ExecAll(d *sql.DB, stmts ...string) error {
	for _, s := range stmts {
		if _, err := d.Exec(s); err != nil {
			return err
		}
	}
	return nil
}

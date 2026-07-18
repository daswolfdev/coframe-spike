// The worker binary: wiring only. Opens the two stores, recovers,
// starts the tick loop and the ops HTTP server, and exits nonzero on
// the first tick error (crash-only — compose restarts us).
package main

import (
	"context"
	"encoding/json"
	"flag"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"perfmon/worker/internal/aggregate"
	"perfmon/worker/internal/loop"
	"perfmon/worker/internal/queue"
)

func main() {
	check := flag.Bool("check", false, "healthcheck probe: GET /healthz and exit 0/1")
	flag.Parse()

	listen := envOr("LISTEN", ":8081")
	if *check {
		os.Exit(probe(listen))
	}

	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))

	queuePath := envOr("QUEUE_DB", "/data/queue.db")
	aggPath := envOr("AGG_DB", "/data/agg.db")
	pollMs := envIntOr("POLL_MS", 250)
	batchLimit := envIntOr("BATCH_LIMIT", 2000)

	q, err := queue.Open(queuePath)
	if err != nil {
		fatal("open queue", err)
	}
	defer q.Close()
	agg, err := aggregate.Open(aggPath)
	if err != nil {
		fatal("open agg", err)
	}
	defer agg.Close()
	l, err := loop.New(q, agg, batchLimit)
	if err != nil {
		fatal("recover", err)
	}
	slog.Info("worker up",
		"queue_db", queuePath, "agg_db", aggPath,
		"poll_ms", pollMs, "batch_limit", batchLimit, "listen", listen)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	srv := &http.Server{Addr: listen, Handler: mux(l)}
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fatal("http server", err)
		}
	}()

	err = l.Run(ctx, time.Duration(pollMs)*time.Millisecond)
	shutCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	srv.Shutdown(shutCtx)
	if err != nil {
		fatal("tick failed — exiting for restart+recovery", err)
	}
	slog.Info("worker stopped")
}

func mux(l *loop.Loop) *http.ServeMux {
	m := http.NewServeMux()
	m.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		if !l.Healthy(time.Now()) {
			http.Error(w, "loop stalled", http.StatusServiceUnavailable)
			return
		}
		w.Write([]byte("ok\n"))
	})
	m.HandleFunc("GET /stats", func(w http.ResponseWriter, r *http.Request) {
		snap, err := l.StatsSnapshot()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(snap)
	})
	return m
}

// probe implements the container healthcheck: the image is FROM scratch,
// so the worker binary doubles as its own curl.
func probe(listen string) int {
	addr := listen
	if strings.HasPrefix(addr, ":") {
		addr = "127.0.0.1" + addr
	}
	resp, err := http.Get("http://" + addr + "/healthz")
	if err != nil || resp.StatusCode != http.StatusOK {
		return 1
	}
	return 0
}

func fatal(msg string, err error) {
	slog.Error(msg, "err", err)
	os.Exit(1)
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envIntOr(key string, def int) int {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		fatal("bad "+key, err)
	}
	return n
}

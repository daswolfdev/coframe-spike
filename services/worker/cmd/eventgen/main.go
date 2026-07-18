// eventgen is the demo/verification producer: synthetic LCP events at a
// steady rate. It stands in for the API until that service lands, and
// stays useful for load demos afterward.
package main

import (
	"flag"
	"fmt"
	"log"
	"math"
	"math/rand/v2"
	"time"

	"perfmon/worker/internal/queue"
)

func main() {
	queuePath := flag.String("queue", "/data/queue.db", "path to queue.db")
	rate := flag.Int("rate", 200, "events per second")
	sites := flag.Int("sites", 2, "number of site ids")
	pages := flag.Int("pages", 5, "pages per site")
	duration := flag.Duration("duration", 10*time.Second, "how long to run (0 = until killed)")
	flag.Parse()

	q, err := queue.Open(*queuePath)
	if err != nil {
		log.Fatal(err)
	}
	defer q.Close()

	interval := time.Second / time.Duration(*rate)
	var deadline time.Time
	if *duration > 0 {
		deadline = time.Now().Add(*duration)
	}

	n := 0
	for deadline.IsZero() || time.Now().Before(deadline) {
		now := time.Now().UnixMilli()
		e := queue.Event{
			SiteID:       fmt.Sprintf("site-%d", rand.IntN(*sites)+1),
			PageURL:      fmt.Sprintf("/page-%d", rand.IntN(*pages)+1),
			LCPms:        lcp(),
			TSms:         now,
			SessionID:    fmt.Sprintf("s%04d", rand.IntN(1000)),
			ReceivedAtMs: now,
		}
		if err := q.Enqueue(e); err != nil {
			log.Fatal(err)
		}
		n++
		time.Sleep(interval)
	}
	fmt.Printf("eventgen: wrote %d events\n", n)
}

// lcp draws from a log-normal centered near 2.5s — the shape of real
// LCP distributions.
func lcp() float64 {
	return math.Exp(rand.NormFloat64()*0.5 + math.Log(2500))
}

# Performance

Load tests use Locust (`tests/load/locustfile.py`, D-032) against the full
Docker stack with mock providers:

```bash
make demo
USERS=300 SPAWN_RATE=50 DURATION=90s make load    # results in tests/load/results/
```

## Profile

Three kinds of simulated user, weighted roughly like expected traffic:

| User | Share | What they do | Think time |
| --- | --- | --- | --- |
| Browser | 60% | App start-up (config, prices, cities) and the price calculator, not signed in | 1–4 s |
| Customer | 30% | Active orders, one order, inbox, profile; sometimes requests a book | 2–6 s |
| Admin | 10% | Order queue, an order's detail, search | 2–5 s |

Sign-in is rate-limited per address, so a pool of eight customers and one admin
sign in at the start and are shared. That is how many phones behind one
carrier NAT look to the API.

## Results (9 October 2026)

Everything ran on one 4 vCPU, 16 GB machine: the load generator, Caddy, two API
processes (`WEB_CONCURRENCY=2`, 40 request threads each), Postgres 16, Redis,
MinIO and the worker. A real deployment has the API to itself, so treat these
as a floor.

| Concurrent users | Requests/s | Failures | p50 | p95 | p99 |
| --- | --- | --- | --- | --- | --- |
| 50 | 30 | 0 | 13 ms | 40 ms | 98 ms |
| 300 | 179 | 0 | 15 ms | 72 ms | 240 ms |
| 500 | 260 | 0 | 140 ms | 740 ms | 1.2 s |
| 800 | 242 | 0 | 1.4 s | 2.7 s | 3.3 s |

At 300 users every endpoint's p95 stays under 300 ms. The slowest are writes
and lists (`POST /orders/source`, `GET /orders`, admin search). Around 250
requests per second the machine is saturated. Beyond that latency grows, but
throughput holds and nothing fails.

For scale: 10,000 customers who each open the app a few times a day generate
a peak of a few requests per second, far inside these numbers.

## What the load test found and fixed

The first run at 300 users fell over. Throughput dropped from 30 to 14
requests per second, 65 requests failed with 500, and p95 reached 31 seconds:

| Users | Before: req/s, failures, p95 | After: req/s, failures, p95 |
| --- | --- | --- |
| 300 | 14, 65 (500s), 31 s | 179, 0, 72 ms |
| 800 | 34, 482 (503s), 40 s | 242, 0, 2.7 s |

The cause was database connections held by requests that had no thread to
run on. Sync endpoints run on a pool of request threads. Each request held its
connection across several hops through that pool: from the sign-in check to
the endpoint, from the endpoint to response validation, and until clean-up
after the response was sent. When the threads were busy, requests waited
between hops while holding connections. That emptied the connection pool, and
threads then blocked for a connection until they timed out. The fixes (D-051):

- The connection pool can always serve every request thread
  (`THREADPOOL_SIZE`, `DB_POOL_SIZE`; `kitaab/db.py`).
- The session is released when the work that needs it ends. The sign-in
  check ends its read before the endpoint runs. The endpoint closes the
  session as its last step on the same thread (`kitaab/api/routing.py`).
  Clean-up runs on the event loop and never waits for a thread.
- Dependencies that do no I/O are `async`, so they take no thread.
- The two request middlewares are plain ASGI, not `BaseHTTPMiddleware`.
- If the database is unreachable or every connection is busy, the API
  answers `503 service-busy` with `Retry-After: 5` instead of `500`.

## Sizing for production

- One API process per vCPU (`WEB_CONCURRENCY`), each with up to
  `THREADPOOL_SIZE` (40) connections. Keep
  `WEB_CONCURRENCY × THREADPOOL_SIZE + 20` below Postgres `max_connections`
  (100 by default). The 20 covers the worker, beat and admin sessions.
- A 2 vCPU, 4 GB server comfortably runs the API, worker and Caddy for launch
  traffic. Postgres should run on its own instance or a managed service.
- Uploads go straight from phones to S3 through presigned URLs and never pass
  through the API, so their size does not affect API capacity.

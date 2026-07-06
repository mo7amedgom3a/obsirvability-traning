# Observability Chaos Sim

A FastAPI service that simulates real production failure modes — timeouts, 5xxs,
CPU spikes, memory leaks, a slow database, and a flaky third-party dependency —
plus structured JSON logging done the way you'd actually want it in production.
Built so you have something realistic to point Prometheus / Grafana / an ELK
or Loki stack / OpenTelemetry at.

## Project layout

```
observability-sim/
├── app/
│   ├── main.py              # FastAPI app, middleware & router wiring, /metrics
│   ├── config.py            # pydantic-settings, env-var driven
│   ├── logging_config.py    # structlog -> JSON, wired into stdlib + uvicorn
│   ├── middleware.py        # request id + structured access logging
│   └── routers/
│       ├── basic.py         # /success, /error
│       ├── chaos.py         # /random, /slow
│       ├── resource.py      # /cpu-burn, /memory-leak(/status|/reset)
│       ├── database.py      # /db
│       ├── external.py      # /external-api
│       └── health.py        # /health, /ready, /live
├── weather_service/         # standalone flaky "third-party" API
├── observability/           # Prometheus + Grafana provisioning
├── docker-compose.yml
├── Dockerfile / Dockerfile.weather
└── requirements.txt
```

## Run it

### Locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r weather_service/requirements.txt

# terminal 1
uvicorn weather_service.main:app --port 9000

# terminal 2
WEATHER_API_URL=http://localhost:9000 uvicorn app.main:app --port 8000 --reload
```

Docs: http://localhost:8000/docs · Metrics: http://localhost:8000/metrics

### With Docker Compose (app + fake dependency + Prometheus + Grafana)

```bash
docker compose up --build
```

| Service     | URL                              |
|-------------|-----------------------------------|
| chaos-app   | http://localhost:8000/docs        |
| weather dep | http://localhost:9000/weather     |
| Prometheus  | http://localhost:9090             |
| Grafana     | http://localhost:3000 (admin/admin, anonymous view enabled) |

In Grafana, the Prometheus datasource is pre-provisioned — go build panels
against metrics like `http_requests_total`, `http_request_duration_seconds_bucket`,
`process_resident_memory_bytes`, and `process_cpu_seconds_total`.

The `chaos-app` container is capped at 256MB memory in `docker-compose.yml`
specifically so `/memory-leak` can actually trigger an OOM kill and container
restart — a realistic thing to watch for in your dashboards/alerts.

## Endpoints & what to observe

| Endpoint | What it does | Watch for |
|---|---|---|
| `GET /success` | Always 200 | Baseline |
| `GET /error` | Always 500 | Error-rate alerts, 5xx dashboards |
| `GET /slow?min_seconds=&max_seconds=` | Random latency in range | Latency histograms/percentiles |
| `GET /random` | 80% success / 10% timeout / 5% unhandled exception / 5% HTTP 500 | Realistic noisy graphs — every request is different |
| `GET /cpu-burn?duration_seconds=&blocking=` | Busy-loops a CPU core. `blocking=true` (default) also starves the event loop, so *every* concurrent request stalls — a very real footgun | CPU usage, request latency across *unrelated* endpoints, traces showing queueing delay |
| `GET /memory-leak?size_mb=` | Appends N MB to a global list that's never freed | RSS growth over time, container OOM-kill + restart, memory alerts |
| `GET /memory-leak/status` | Current leaked total | — |
| `POST /memory-leak/reset` | Clears the leak (testing convenience) | — |
| `GET /db` | Simulated DB query, 20% chance of a 4s "slow query" (`SLOW_DB_PROBABILITY`) | Span duration (`db_query_span` log event), slow-request tail latency |
| `GET /external-api` | Calls the fake weather service; translates its 500/timeout/429 into 502/504/429 | Dependency error rates, timeout handling, upstream vs. downstream status codes |
| `GET /health` | Generic liveness/uptime check | — |
| `GET /ready` | Readiness probe (503 when not ready) | K8s traffic routing |
| `GET /live` | Liveness probe | K8s restarts |
| `GET /metrics` | Prometheus exposition format | Request count/latency/in-flight, process CPU/RSS |

### Fake external dependency (`weather_service/`)

A second, standalone FastAPI app on port 9000 with its own random-outcome
generator (70% success / 15% HTTP 500 / 10% hang-until-timeout / 5% HTTP 429
with `Retry-After`). `chaos-app`'s `/external-api` depends on it via
`WEATHER_API_URL`, so you can practice observing and handling a flaky
third-party integration end-to-end, including how a hang on the far side
surfaces as a `504` on your side.

## Structured logging

`app/logging_config.py` configures [structlog](https://www.structlog.org/) to
emit single-line JSON to stdout, following the practices that actually matter
for observability:

- **One event, one line.** No multi-line tracebacks breaking your log parser —
  exceptions are rendered as structured fields (`exception`, `event`, etc.) via
  `structlog.processors.format_exc_info`.
- **Consistent schema.** Every line has `timestamp` (ISO-8601 UTC),
  `level`, `logger`, and `event` at minimum.
- **Request correlation for free.** `app/middleware.py` generates/propagates a
  `request_id` (respects an inbound `X-Request-ID` header, echoes it back in
  the response) and binds it via `structlog.contextvars`, so *every* log line
  emitted anywhere during that request automatically carries the same
  `request_id` — no need to thread it through every function call manually.
- **uvicorn's own logs are unified** into the same JSON format instead of
  printing a different, unstructured style next to your app logs.
- **Access logs are a first-class event** (`request_finished`, with
  `status_code` and `duration_ms`) — the single most useful field for
  building latency/error dashboards and alerts.

Toggle `JSON_LOGS=false` locally if you want human-readable colored console
output instead (structlog's `ConsoleRenderer`) while still keeping the same
code path.

Example log line:

```json
{"status_code": 504, "duration_ms": 3033.47, "event": "request_finished", "http_path": "/external-api", "http_method": "GET", "request_id": "5963a855-...", "logger": "http.access", "level": "warning", "timestamp": "2026-07-01T11:30:48.850063Z"}
```

## Notes / next steps

- **Tracing**: this is metrics + logs only. If you want spans/traces, add
  `opentelemetry-instrumentation-fastapi` + `opentelemetry-instrumentation-httpx`
  and export to Jaeger/Tempo — the `request_id` here maps naturally to a
  trace id if you want to bridge the two.
- **`/cpu-burn` with `blocking=false`** offloads to a thread pool instead of
  blocking the event loop — useful if you want to compare "one bad endpoint
  degrades the whole service" vs. "isolated resource contention."
- Adjust failure weights, sleep durations, and probabilities directly in
  `app/routers/chaos.py`, `app/routers/database.py`, and
  `weather_service/main.py` to match whatever scenario you're rehearsing.

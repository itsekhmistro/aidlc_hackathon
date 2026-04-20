# TASK-16 Load-Test Runbook

Harness for the five NFR scenarios defined in `specs/16-nfr-load-testing.md`.
Scenarios S1–S4 are Locust scripts in `locustfile.py`; S5 is a pytest module
(`test_persistence_restart.py`) that shells out to `docker compose`.

## Prerequisites

1. **Stack running.** From the repo root:
   ```bash
   docker compose up -d --build
   ```
   Wait for `backend` to show `healthy`.

2. **Python toolchain.** The harness reuses the backend's uv project (Locust
   and websocket-client are declared as dev deps):
   ```bash
   cd backend && uv sync
   ```

3. **macOS file-descriptor limit.** Locust opens one WS + HTTP socket per VU.
   Before S2 (1000 users) and S1 (300 users), raise the limit in the same
   shell you launch Locust from:
   ```bash
   ulimit -n 8192
   ```
   Do **not** set ulimits on the backend container — per `docker-compose.yml`,
   the server side is fine at the default; the bottleneck is the harness host.

## Seed

All seeding goes through `backend/scripts/seed_load.py`. It writes rows with a
`loadtest_` prefix and mints `UserSession` rows you can feed straight to the
harness via `--token-out`. Run from `backend/`:

| Scenario | One-liner |
|---|---|
| S1 steady | `uv run python -m scripts.seed_load --reset --users 300 --rooms 30 --members-per-room 10 --big-room-size 0 --history-room-size 0 --history-room-messages 0 --token-out ../loadtests/tokens.json` |
| S2 fanout | `uv run python -m scripts.seed_load --reset --users 1000 --rooms 0 --members-per-room 0 --big-room-size 1000 --history-room-size 0 --history-room-messages 0 --token-out ../loadtests/tokens.json` |
| S3 presence | reuses S1's data (100 VUs share a room — seed `--users 300 --rooms 30 --members-per-room 100`). |
| S4 history | `uv run python -m scripts.seed_load --reset --users 50 --rooms 0 --members-per-room 0 --big-room-size 0 --history-room-size 50 --history-room-messages 10000 --token-out ../loadtests/tokens.json` |
| S5 persistence | driven by the pytest itself — no manual seed required. |

> **Note:** `tokens.json` is git-ignored (see `loadtests/.gitignore`). Feel
> free to keep several, e.g. `tokens_s1.json`, `tokens_s2.json`, and point
> the harness at the right one via `LOADTEST_TOKENS=loadtests/tokens_s1.json`.

## Run

Invoke Locust from the **repository root** so relative paths in the script
line up. `--project backend` tells uv to resolve the Locust binary from the
backend's virtualenv.

```bash
mkdir -p loadtests/reports
```

| # | Scenario | Command |
|---|---|---|
| S1 | steady_state_300 | `uv run --project backend locust -f loadtests/locustfile.py --tags steady --host http://localhost:8000 --headless -u 300 -r 30 -t 5m --csv loadtests/reports/s1` |
| S2 | fanout_1000 | `uv run --project backend locust -f loadtests/locustfile.py --tags fanout --host http://localhost:8000 --headless -u 1000 -r 100 -t 5m --processes 4 --csv loadtests/reports/s2` |
| S3 | presence_propagation | `uv run --project backend locust -f loadtests/locustfile.py --tags presence --host http://localhost:8000 --headless -u 100 -r 10 -t 3m --csv loadtests/reports/s3` |
| S4 | history_10k_read | `uv run --project backend locust -f loadtests/locustfile.py --tags history --host http://localhost:8000 --headless -u 50 -r 10 -t 3m --csv loadtests/reports/s4` |
| S5 | persistence_restart | `cd backend && uv run pytest ../loadtests/test_persistence_restart.py -v` |

For S2 the publisher↔listener latency correlation table lives in process
memory. With `--processes 4` that table is per-worker, so roughly 75% of
listener receipts will fire a `0.0 ms` latency event (different process
from the publisher) — interpret S2's p95 as an upper bound and cross-check
the delivered/sent ratio via the CSV row count. If precise S2 latency
matters, re-run without `--processes` at the cost of more CPU contention.

## Reports

Locust writes `{prefix}_stats.csv`, `{prefix}_stats_history.csv`,
`{prefix}_failures.csv`, and `{prefix}_exceptions.csv` under
`loadtests/reports/`. The NFR-derived p50/p95/p99 for each scenario lives
in `stats.csv` on the row named `e2e:<scenario>`. Paste those into
`RESULTS.md`.

## Hardware baseline

_Fill in when results are recorded._

| Host | CPU | RAM | OS | Docker | Stack |
|---|---|---|---|---|---|
| _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ | `docker compose up -d --build` |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `QueuePool limit ... overflow` in server log | More than 100 concurrent DB sessions | Raise `pool_size` / `max_overflow` in `backend/app/core/db.py` (already 50/50). If S2 still trips it, shed load by dropping the publisher rate. |
| WS drops to 1006 mid-run | ping/pong timing mismatch | Confirm `--ws-ping-interval 20 --ws-ping-timeout 30` in the backend CMD (docker-compose.yml line ~46). |
| `Too many open files` in Locust output | macOS default fd limit (256) | `ulimit -n 8192` in the same shell before launching Locust. |
| `tokens.json not found` | Seeder not run yet / wrong path | Run the relevant seed command above; or set `LOADTEST_TOKENS=/abs/path`. |
| S5 skips with "docker CLI not on PATH" | Running outside the dev laptop | Expected — S5 is laptop-only. |
| S2 delivered/sent ratio < 1.0 | Listener greenlets lagging behind fanout | Drop listener count to 500 and re-measure; or lower publisher to 1 msg/s. |

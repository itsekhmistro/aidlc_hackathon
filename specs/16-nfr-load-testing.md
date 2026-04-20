# TASK-16: NFR Load & Performance Testing

**Agent:** `/qa` (primary) · `/backend` (harness hooks + mitigations) · `/docker` (runtime limits)
**Phase:** Post-feature verification — runs on `greenbase` after all functional specs are closed
**Depends on:** TASK-01..15 (feature-complete stack)
**Parallel with:** — (exclusive use of the stack while running)

---

## Goal

Produce a reproducible load-test suite that validates the project's non-functional requirements (NFR §3.1–§3.3 of `Initial-goal-definition.md`) on a single laptop-class host using `docker compose`. Output is (a) a scripted harness, (b) a seeding utility, (c) a short results report tied to the exact numeric pass/fail thresholds below.

---

## NFRs under test

| Ref | Requirement | How we validate |
|-----|-------------|-----------------|
| 3.1 | Up to 300 simultaneous users | Scenario S1 (`steady_state_300`) |
| 3.1 | Up to 1000 participants per room | Scenario S2 (`fanout_1000`) |
| 3.1 | Unlimited rooms per user, typical 20/50 | Covered structurally by S1 topology; "unlimited" is unfalsifiable and explicitly out of scope |
| 3.2 | Message delivered within 3 s | p99 e2e latency ≤ 3000 ms in S1 and S2 |
| 3.2 | Presence propagates within 2 s | Scenario S3 (`presence_propagation`) |
| 3.2 | Room with ≥10 000 messages stays usable | Scenario S4 (`history_10k_read`) |
| 3.3 | Messages persisted for years | Scenario S5 (`persistence_restart`) + structural review (no TTL, soft-delete only) |
| 3.3 | Infinite scroll over history | S4 exercises keyset pagination end-to-end |

---

## Tool choice — Locust

Pick Locust + the `websockets` library. Rationale:

- **Stack fit**: Python coroutine per virtual user mirrors real client behaviour (REST login → WS open → heartbeat → send). `/backend` agent can extend scenarios without switching languages.
- **300 VUs on a laptop**: Locust's gevent worker handles 300 WS clients comfortably (<200 MB RSS). For S2 (1000-member fanout) run `locust --processes 4` on the same host to dodge GIL contention.
- **Rejected alternatives**: k6 (JS-only scripting is awkward for stateful chat flows); raw asyncio harness (reinvents ramp-up, stats, reporting — wastes the demo window).

Dependency change: `uv add --group dev locust websockets`.

---

## Test scenarios

| # | Name | Goal | Topology | Workload | Pass metric |
|---|------|------|----------|----------|-------------|
| S1 | `steady_state_300` | NFR 3.1 (300 concurrent) + 3.2 (message <3 s) | 300 users, 30 rooms (~10 members each) | 1 msg/user/10 s; 30 s heartbeat | p95 ≤ 1500 ms · p99 ≤ 3000 ms · error <0.5% |
| S2 | `fanout_1000` | NFR 3.1 (1000/room) + 3.2 (delivery) | 1 room, 1000 members | 1 publisher @ 2 msg/s · 999 listeners | p95 ≤ 2500 ms · delivered/sent = 1.000 |
| S3 | `presence_propagation` | NFR 3.2 (<2 s) | 100 users sharing a room | User A toggles online↔afk every 10 s | p95 heartbeat→`presence.update` ≤ 1500 ms |
| S4 | `history_10k_read` | NFR 3.2 (10 k messages usable) | 1 seeded room with 10 000 messages | 50 users: initial page + 5 scroll pages | p95 per page ≤ 500 ms · p99 ≤ 1000 ms |
| S5 | `persistence_restart` | NFR 3.3 (persistence) | 10 rooms × 500 messages seeded | `docker compose restart backend`; clients reconnect and reload | 100% message recovery, content + `created_at` identical |

Run S1 + S3 together as the "realism" suite; S2, S4, S5 standalone.

---

## Latency measurement

Ground truth: `time.monotonic_ns()` on the harness host (harness and server share one clock on localhost — no NTP, no wall-clock skew).

Minimal protocol change required:

1. Harness generates a `client_msg_id` (UUID) and includes it in the `POST /api/messages/{room_id}` body. Record `t_send` keyed by that id.
2. Server echoes `client_msg_id` back inside `message.new.message` (pass-through only — no DB column, no migration). Additive, backward compatible.
3. Receiver coroutine records `t_recv` on `message.new`, looks up `t_send` by `client_msg_id`, emits `e2e_latency_ms` as a Locust custom metric.

A `server_received_at` timestamp is **not** added for the demo — it's a triage tool, not an NFR signal. Add it only if S2 fails and we need to split request-time vs fanout-time.

---

## Seeding strategy

Script: **`backend/scripts/seed_load.py`** (new; run via `uv run python -m scripts.seed_load`).

- **Users** — bulk insert (`session.execute(insert(User), [...])`). Hash **one** password with bcrypt cost 12 once and reuse `hashed_password` across all seeded users. Full population in <1 s.
- **Room membership** — one `Room` row + `insert(RoomMember)` with N rows in a single statement (~50 ms for 1000).
- **Messages** — batched `executemany` (1000 rows per batch) via psycopg. Set `created_at = now() - interval '<i> seconds'` so keyset pagination returns realistic ordering. 10 k messages in ~3 s.
- **Session tokens** — harness never hits `/api/auth/login` (bcrypt on the hot path would serialize via the threadpool). Instead, the seeder writes `Session` rows directly and hands the harness the raw bearer tokens. A test-only route is NOT introduced — direct DB writes keep prod code clean.

---

## Backend mitigations (pre-flight — fix before first S2 run)

Top risks identified in design review; fix order matches probability of failure.

1. **`send_to_room` sequential awaits** (`backend/app/core/connection_manager.py`): current loop does `await send_to_user(...)` serially. At 1000 members × ~1 ms/send ≈ 1 s of fanout per message, blocking subsequent broadcasts. **Fix:** wrap the per-user sends in `asyncio.gather(*[...])` (~5 LOC).
2. **Postgres connection pool** (`backend/app/core/db.py`): default `pool_size=5, max_overflow=10` will starve under S1. **Fix:** raise to `pool_size=50, max_overflow=50` and document in `.env.example`.
3. **Room member list lookup per broadcast**: under S2 every send re-queries `SELECT user_id FROM room_member WHERE room_id=...`. **Fix:** in-memory cache on `ConnectionManager` keyed by `room_id`, invalidated on `room.member_joined / member_left / member_banned` events (those broadcasts are already the source of truth).
4. **WS ping/pong under fanout backlog**: confirm uvicorn starts with `--ws-ping-interval 20 --ws-ping-timeout 30`. Update `docker-compose.yml` / backend CMD if missing. If S2 still shows spurious disconnects, raise the 90 s stale threshold documented in TASK-11.
5. **File-descriptor limit on macOS** (`ulimit -n` default 256): runbook must set `ulimit -n 8192` before launching S2. Add to `loadtests/README.md`.

---

## Acceptance criteria

Primary deliverables:

- [ ] `loadtests/locustfile.py` with scenarios S1–S4, each runnable via `uv run locust -f loadtests/locustfile.py --tags <scenario>`
- [ ] `loadtests/test_persistence_restart.py` (pytest) covering S5
- [ ] `backend/scripts/seed_load.py` with CLI flags: `--users`, `--rooms`, `--members-per-room`, `--messages`, `--big-room-size`, `--big-room-history`
- [ ] Backend mitigations 1–4 landed and unit-tested
- [ ] `loadtests/README.md` with: one-liner per scenario, hardware baseline used for the reported results, `ulimit` + `docker compose` setup steps
- [ ] `loadtests/RESULTS.md` capturing p50/p95/p99 + error-rate numbers per scenario from a real run on the documented host, and a verdict line per NFR

Numerical pass thresholds (all must hold on a 1-run suite):

- [ ] S1 message e2e: p50 ≤ 500 ms · p95 ≤ 1500 ms · p99 ≤ 3000 ms · error rate <0.5%
- [ ] S2 fanout (1000 listeners): p95 ≤ 2500 ms · delivered/sent ratio = 1.000
- [ ] S3 presence propagation: p95 ≤ 1500 ms (comfortably under NFR's 2000 ms)
- [ ] S4 history page: p95 ≤ 500 ms · p99 ≤ 1000 ms · no pg query >2 s in `pg_stat_statements`
- [ ] S5 restart: 100% of seeded messages recovered; byte-equal content; `created_at` preserved to the millisecond

---

## Out of scope

- **Multi-node scale-out** — single uvicorn process, no Redis pub/sub, no sticky LB. If we outgrow this, it is a separate task.
- **"Years of persistence"** — not testable in a hackathon. Claim via structural review: schema has no TTL, no cron purge, `deleted_at` is soft-delete only. Record the review in `RESULTS.md`.
- **"Unlimited rooms per user"** — unfalsifiable; S1's 20-rooms-per-user topology represents the typical case and is what we claim.
- **Real internet conditions** — localhost only; no packet loss, no TLS, no NAT.
- **Attachment throughput** — 20 MB uploads stress the disk and multipart path, not the chat NFRs. Defer.
- **Browser rendering at 10 k messages** — a Playwright-driven FPS/scroll-jank test belongs to a separate frontend perf task; S4 only validates the server-side history read path.

---

## Implementation notes

- Same-host testing: co-locating Locust and the backend on one laptop will steal CPU from the server. Report p99 with that caveat, and run each scenario with the harness process pinned to different cores via `taskset` / macOS's `taskpolicy` if available.
- Correlation IDs are per-message only — do **not** thread them through the DB. Echo-through the in-flight `message.new` payload is sufficient.
- S5 asserts persistence across `docker compose restart backend` (preserves the `postgres_data` named volume). `docker compose down -v` is the destructive path and is not part of any scenario.
- All scenarios should emit CSV (Locust's `--csv` flag) so `RESULTS.md` can be regenerated reproducibly from the raw data.

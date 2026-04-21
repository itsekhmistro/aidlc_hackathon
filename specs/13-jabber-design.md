# TASK-13 Jabber / XMPP Integration — Design

**Status:** Design (no code). Implements `specs/13-jabber.md`.
**Author:** `/architect`  **Date:** 2026-04-21  **Branch target:** `greenbase`
**Consumers:** `/backend`, `/frontend`, `/docker` (parallel work on this doc).

Goal: embed a Prosody XMPP server alongside the FastAPI app so external XMPP clients
(Pidgin, Gajim, Conversations) can connect, two instances of the stack can federate
via S2S, and an admin UI exposes connection + federation traffic.

---

## 0. Scope carve-outs (read first)

| Item | Decision |
|---|---|
| **User provisioning sync** | IN — Prosody account is created on FastAPI register; password updated on change; disabled on account delete. |
| **External client connectivity** | IN — `ejabber`/`Gajim` can log in with the FastAPI username+password. |
| **S2S federation between Prosody A and Prosody B** | IN — via `docker-compose.federation.yml`. |
| **Admin dashboards** (`/admin/jabber`, `/admin/jabber/federation`) | IN — read-only, polled every 10s. |
| **Federation log DB table** | IN — metadata only, populated by Prosody webhook. |
| **Load-test script** (`scripts/federation_load_test.py`) | IN — separate PR from `/qa`; design only references it. |
| **Unified history bridge** (XMPP ↔ FastAPI `message` table two-way sync) | **OUT (v2)** — listed in §7. Don't attempt under demo time pressure. |
| **MUC (group chat over XMPP)** | OUT. Rooms stay FastAPI-only. |
| **TLS / cert chain for S2S** | OUT for dev; `s2s_secure_auth = false` per spec. Dev-only, see §7. |

---

## 1. Data model additions

### 1.1 `User.is_admin: bool`

Add a single column to the existing `user` table.

- **Model edit:** `backend/app/models/user.py` → `User` gains
  `is_admin: bool = Field(default=False, nullable=False)`.
- **Semantics:** global admin (not per-room). Only gates Jabber admin screens today;
  leave room-level admin semantics untouched.
- **Seeding the first admin:** no self-service UI. `/backend` adds a CLI one-liner
  (`uv run python -m app.scripts.make_admin <username>`) under
  `backend/app/scripts/make_admin.py`. Keeps the migration side-effect-free.

**Migration file**: `backend/alembic/versions/b2c3d4e5f6a7_add_is_admin_and_federation_log.py`
(revises `a1b2c3d4e5f6`).

Upgrade operations — single migration covering both additions in §1.1 and §1.2:

```
op.add_column('user', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('false')))
# Drop server_default after the column is populated so the ORM controls future inserts
op.alter_column('user', 'is_admin', server_default=None)

op.create_table('federation_log',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ts', sa.DateTime(), nullable=False),
    sa.Column('direction', sa.String(length=3), nullable=False),   # 'in' | 'out'
    sa.Column('local_jid', sa.String(length=320), nullable=False),
    sa.Column('remote_jid', sa.String(length=320), nullable=False),
    sa.Column('remote_server', sa.String(length=255), nullable=False),
    sa.Column('message_preview', sa.String(length=140), nullable=True),
    sa.Column('session_id', sa.String(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id'),
)
op.create_index('ix_federation_log_ts', 'federation_log', ['ts'])
op.create_index('ix_federation_log_remote_server_ts', 'federation_log', ['remote_server', 'ts'])
op.create_index('ix_federation_log_session_id', 'federation_log', ['session_id'])
```

Downgrade is the mirror (drop table, drop column). Keep the existing pattern: no
`op.drop_constraint` on the `is_admin` column — there's no FK, just a bool.

### 1.2 `federation_log` table

New SQLModel in `backend/app/models/federation.py`. No FK to `user` — the
remote JID may belong to a user who doesn't exist locally, and even the local
JID isn't required to resolve (the XMPP username and the FastAPI username
happen to match by convention but the schema must not assume it).

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid.UUID` PK | `default_factory=uuid.uuid4` |
| `ts` | `datetime` | UTC; indexed for "recent 50" query |
| `direction` | `str(3)` | `"in"` or `"out"` (stored as text, not enum, to keep Prosody webhook payloads trivial) |
| `local_jid` | `str(320)` | Full JID, e.g. `alice@server-a.local` |
| `remote_jid` | `str(320)` | Full JID on the remote host |
| `remote_server` | `str(255)` | Denormalised host part for cheap GROUP-BY in the federation dashboard |
| `message_preview` | `str(140) \| None` | **See §1.3.** First 140 chars of body; NULL if Prosody was configured to omit bodies |
| `session_id` | `str(64) \| None` | Prosody S2S stream id; used to group a burst of messages into one connection |

**Indexes:**
- `ix_federation_log_ts` — for the `recent` query (ORDER BY ts DESC LIMIT 50).
- `ix_federation_log_remote_server_ts` — composite, for `remotes` aggregation
  (group by `remote_server`, max ts per group, count per group).
- `ix_federation_log_session_id` — for debugging and the "burst counter" in the
  federation dashboard.

**No FK** to `user` — remote JIDs are not local users; local JIDs may belong
to soft-deleted users. Keep the table independent so federation accounting
survives account tombstones.

### 1.3 Message body storage — privacy decision

**Decision: metadata + 140-char preview, default off for body content.**

Rationale in one sentence: federation logging is an operator-visibility tool,
not an archive, and storing full message bodies of traffic that crosses a
server boundary (where at least one party may be on the other server) crosses
a consent line we don't own — keep the schema optional so a deployment can
flip a single flag to go full metadata-only.

- Prosody webhook sends `message_preview` truncated at 140 chars.
- A new setting `XMPP_LOG_PREVIEWS: bool = True` in `backend/app/core/config.py`;
  when False, the webhook handler writes `NULL` into `message_preview` regardless
  of what Prosody sent.
- The admin UI already shows `"..."` for NULL previews (§5). No schema change
  needed if an operator disables preview capture mid-flight.
- No attachment bodies. No file transfer capture. MAM and history bridging are
  out of scope (§7).

---

## 2. API contract (FastAPI)

All three endpoints live in a new router file: `backend/app/api/routes/jabber_admin.py`
registered as `api_router.include_router(jabber_admin.router)` in `backend/app/api/main.py`.
Routes use the `/api/admin/jabber` and `/api/internal/xmpp` prefixes (no `/v1` — the
rest of the app's new routes don't use it either; see `auth.py`, `rooms.py`, etc.).

Response schemas live in `backend/app/schemas/jabber.py`.

### 2.1 `GET /api/admin/jabber/status`

Polled by `/admin/jabber` dashboard every 10 s.

**Auth:** `CookieCurrentUser` + `require_admin` (§2.5).

**Implementation:** backend calls Prosody's `mod_http_api` stats endpoint
(`GET http://prosody:5280/api/stats`, token auth). Cache the result in-process
for 5 s to absorb the 10 s polling from multiple admin tabs without hammering
Prosody. When `XMPP_ENABLED=False`, return 503 with `{"detail":"XMPP bridge disabled"}`
so the frontend can render a clean "bridge off" state.

**Response:**
```json
{
  "server_host": "server-a.local",
  "uptime_seconds": 8041,
  "connected_clients": 47,
  "s2s_links_active": 2,
  "sessions": [
    {"jid": "alice@server-a.local", "client": "Gajim 1.8", "ip": "192.168.1.5", "connected_seconds": 840},
    {"jid": "bob@server-a.local",   "client": "Pidgin",    "ip": "192.168.1.6", "connected_seconds": 7201}
  ]
}
```

- `server_host` — value from `XMPP_HOST` env; echoed back so the UI doesn't
  need to hit `/api/auth/me` for the server identity.
- `sessions` capped at 100 rows; if Prosody reports more, truncate and add
  `"truncated": true`. Admin panel can paginate later.

### 2.2 `GET /api/admin/jabber/federation`

Polled by `/admin/jabber/federation` every 10 s.

**Auth:** `CookieCurrentUser` + `require_admin`.

**Implementation:** two DB queries against `federation_log`:

1. `remotes`: `SELECT remote_server, direction, COUNT(*), MAX(ts) FROM federation_log GROUP BY remote_server, direction` then collapse to one row per remote server with a `direction` of `"in"` / `"out"` / `"both"`.
2. `recent`: `SELECT id, ts, local_jid, remote_jid, message_preview FROM federation_log ORDER BY ts DESC LIMIT 50`.

**Response:**
```json
{
  "remotes": [
    {"server": "server-b.local", "direction": "both", "message_count": 1247, "last_active_seconds_ago": 5}
  ],
  "recent": [
    {"ts": "2026-04-21T14:22:01Z", "from_jid": "alice@server-a.local", "to_jid": "bob@server-b.local", "preview": "Hello from A!"},
    {"ts": "2026-04-21T14:22:02Z", "from_jid": "bob@server-b.local",   "to_jid": "alice@server-a.local", "preview": "Got it!"}
  ]
}
```

- `last_active_seconds_ago` computed server-side from `MAX(ts)` so the UI
  doesn't need clock-skew-aware relative formatting.
- `preview` is either the stored 140-char slice or `null`. Frontend must
  render `"…"` for null without crashing.
- `recent` hard-limited to 50 rows. No cursor/page params in v1 — operator
  needs the last 50, not deep history; keeps the endpoint cacheable.

### 2.3 `POST /api/internal/xmpp/event` (Prosody webhook)

Prosody pushes here via a small Lua module (`/docker` delivers it in
`jabber/modules/mod_fastapi_webhook.lua`). One endpoint, two payload shapes
discriminated by `type`.

**Auth:** `X-XMPP-Webhook-Token: <XMPP_WEBHOOK_TOKEN>` shared-secret header.
Constant-time compare in the handler. **Not** the session cookie — Prosody
has no cookie jar. Return 401 on mismatch, 200 on success, 202 on valid but
throttled (see below).

**Payload A — federation message:**
```json
{
  "type": "federation.message",
  "ts": "2026-04-21T14:22:01Z",
  "direction": "out",
  "local_jid": "alice@server-a.local",
  "remote_jid": "bob@server-b.local",
  "remote_server": "server-b.local",
  "message_preview": "Hello from A!",
  "session_id": "s2s_0001"
}
```
Handler inserts into `federation_log`. If `XMPP_LOG_PREVIEWS=False`,
`message_preview` is overwritten with `NULL` before insert.

**Payload B — client session change:**
```json
{
  "type": "session.client",
  "ts": "2026-04-21T14:22:01Z",
  "event": "login" | "logout",
  "jid": "alice@server-a.local",
  "client": "Gajim 1.8",
  "ip": "192.168.1.5",
  "session_id": "c2s_abc123"
}
```
Handler: **no-op on DB**. We read client sessions from Prosody's own stats
endpoint (§2.1) rather than a write-path mirror. We accept this payload and
return 200 anyway so the Lua module is symmetric (one webhook, two shapes)
and so a future v2 can turn on audit logging without touching Prosody config.
Log at `INFO` level; don't alert on it.

**Throttling:** if the endpoint sees > 500 events/second (token-bucket in
`ConnectionManager`-style module state), drop to 202 + discard. Dev-only
guardrail — a misbehaving S2S stream must not DoS the FastAPI DB.

### 2.4 `GET /api/auth/me` — extend

Return `is_admin` so the frontend can gate nav. Edit
`backend/app/schemas/user.py`:

```
class UserPublic(SQLModel):
    id: uuid.UUID
    username: str
    email: str
    created_at: datetime
    is_admin: bool = False   # NEW
```

`UserPublic` flows from the `user` ORM object, and SQLModel's `from_attributes`
behaviour picks up the new column automatically. No change needed in
`backend/app/api/routes/auth.py` / `users.py` — they both already
`response_model=UserPublic` on `/me` and `/users/me`.

Frontend: add `is_admin: boolean` to the `UserPublic` interface in
`frontend/src/lib/types.ts` (default-true-on-missing is **not** safe; if the
field is absent, treat as false).

### 2.5 `require_admin` dependency

New in `backend/app/api/deps.py`:

```
def get_current_admin(current_user: CookieCurrentUser) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user

AdminUser = Annotated[User, Depends(get_current_admin)]
```

Both `GET /api/admin/jabber/status` and `GET /api/admin/jabber/federation`
take `admin: AdminUser` as a positional dependency. Use `AdminUser` not a
reusable `require_admin()` guard so that the resolved `User` is available
in the route body (handy for logging who viewed what).

The internal webhook route (§2.3) **does not** take `AdminUser` — it uses
a separate dependency `verify_xmpp_webhook_token(request: Request)` that
compares the `X-XMPP-Webhook-Token` header against `settings.XMPP_WEBHOOK_TOKEN`.
No user context needed; the webhook operates outside the user session model.

---

## 3. Prosody bridge contract (FastAPI → Prosody)

New module: `backend/app/core/xmpp.py`. Three async wrapper functions over
`httpx.AsyncClient` against Prosody's `mod_http_api`.

### 3.1 Prosody endpoints we use

Prosody's `mod_http_api` (community module) exposes REST-ish admin actions
over HTTP with a bearer token. The endpoints (and exact payloads) we need:

| Action | Method + Path | Payload | Prosody mod |
|---|---|---|---|
| Create user | `POST /admin/create_user` | `{"username":"alice","password":"..."}` | `mod_http_api` |
| Change password | `POST /admin/change_user_password` | `{"username":"alice","password":"..."}` | `mod_http_api` |
| Disable/delete user | `POST /admin/delete_user` | `{"username":"alice"}` | `mod_http_api` |
| Stats (§2.1) | `GET /api/stats` | — | `mod_http_api` + `mod_admin_stats` |

Auth on all four: `Authorization: Bearer <XMPP_ADMIN_TOKEN>`.

Base URL: `http://{XMPP_HOST}:5280` where `XMPP_HOST` defaults to
`"prosody"` (the docker service name). 5280 is Prosody's HTTP port; it is
**not** exposed on the host in single-server mode — intra-compose only.

### 3.2 Python wrapper signatures

```python
# backend/app/core/xmpp.py

async def provision_xmpp_user(username: str, password: str) -> None: ...
async def change_xmpp_password(username: str, new_password: str) -> None: ...
async def disable_xmpp_user(username: str) -> None: ...
```

All three: no return value; on success, log at INFO; on transient failure,
log at WARNING and return (do NOT raise). See §3.3.

The three wrappers are called from:

- `provision_xmpp_user`: `POST /api/auth/register` (after `session.commit()`).
- `change_xmpp_password`: `PATCH /api/auth/password-change` (after commit) and
  `POST /api/auth/password-reset` (after commit). The raw password is
  available only at these points — pass it through, do not persist it.
- `disable_xmpp_user`: `DELETE /api/auth/account` (after commit, before
  `response.delete_cookie`). Username is a tombstone in FastAPI but we fully
  remove it from Prosody so the JID is reclaimable by a future registrant
  with the same username. (Our `username` is a tombstone *within FastAPI*;
  the bridge is allowed to recreate, because `disable_xmpp_user` would only
  ever be called here for a tombstoned account.)

### 3.3 Error handling

**Decision: XMPP bridge failure does NOT block FastAPI registration, password
change, or account deletion.** The wrapper catches `httpx.HTTPError` +
`httpx.TimeoutException` + Prosody 5xx, logs at WARNING with `{username,
action, status_code}`, and returns normally.

Rationale: the FastAPI app was demoed and shipped as v1.0.0 *without*
Prosody; users whose registration succeeded in FastAPI but failed to
provision in Prosody should still be able to use the chat app. The XMPP
account will be missing until an operator runs a reconciliation script
(`scripts/reconcile_xmpp.py` — not in this PR). A partial failure must not
500 the registration endpoint.

Exception: **401/403 from Prosody** (misconfigured `XMPP_ADMIN_TOKEN`) is
logged at ERROR — this is a deployment bug, not a transient failure, and
the operator should see it immediately in backend logs. Still no raise.

Timeouts: `httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=1.0))`.
Registration latency budget is ~100 ms; 2 s is generous but bounded so a
wedged Prosody can't wedge the register endpoint.

### 3.4 `XMPP_ENABLED` feature flag

New in `backend/app/core/config.py`:

```python
XMPP_ENABLED: bool = False
XMPP_HOST: str = "prosody"
XMPP_ADMIN_TOKEN: str = ""           # set in .env; no safe default
XMPP_WEBHOOK_TOKEN: str = ""         # set in .env; no safe default
XMPP_LOG_PREVIEWS: bool = True
```

When `XMPP_ENABLED=False`:
- All three `*_xmpp_*` wrappers short-circuit at the top: `if not settings.XMPP_ENABLED: return`.
- `GET /api/admin/jabber/status` returns 503 (see §2.1).
- `POST /api/internal/xmpp/event` returns 410 Gone.
- The migration still adds `is_admin` and `federation_log` — schema change
  is independent of the flag so turning it on later doesn't require another
  migration.

**Default: False** so an existing deployment of v1.0.0 that pulls this
branch doesn't try to talk to a Prosody service that doesn't exist. The
docker-compose files (§4) set `XMPP_ENABLED=true` explicitly.

Missing `.env` entries: the backend starts fine with `XMPP_ENABLED=False`
and empty tokens. If `XMPP_ENABLED=True` but `XMPP_ADMIN_TOKEN` is empty,
log ERROR once at startup in `app.main.lifespan`; do not crash — dev
ergonomics matter.

### 3.5 `.env.example` additions

```
# --- XMPP bridge (TASK-13) --- off by default
XMPP_ENABLED=false
XMPP_HOST=prosody
XMPP_ADMIN_TOKEN=
XMPP_WEBHOOK_TOKEN=
XMPP_LOG_PREVIEWS=true
```

---

## 4. Docker topology

### 4.1 Single-server mode — `docker-compose.yml` additions

Add a `prosody` service next to `backend` on the default network. Intent:
local XMPP client (Gajim on host) connects to `localhost:5222` and talks to
a user provisioned by the backend.

```yaml
  prosody:
    image: prosody/prosody:0.12
    restart: unless-stopped
    ports:
      - "5222:5222"   # XMPP client (c2s)
      - "5269:5269"   # S2S (not used in single-server mode, exposed for manual tests)
      - "5280:5280"   # HTTP admin API — exposed for debugging ONLY; see note
    volumes:
      - ./jabber/prosody_single.cfg.lua:/etc/prosody/prosody.cfg.lua:ro
      - ./jabber/modules:/usr/lib/prosody/modules-custom:ro
      - prosody_data:/var/lib/prosody
    environment:
      XMPP_ADMIN_TOKEN: ${XMPP_ADMIN_TOKEN}
      XMPP_WEBHOOK_TOKEN: ${XMPP_WEBHOOK_TOKEN}
      FASTAPI_WEBHOOK_URL: "http://backend:8000/api/internal/xmpp/event"
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "prosodyctl status || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

  backend:
    # … existing definition …
    environment:
      # … existing keys …
      XMPP_ENABLED: "true"
      XMPP_HOST: prosody
      XMPP_ADMIN_TOKEN: ${XMPP_ADMIN_TOKEN}
      XMPP_WEBHOOK_TOKEN: ${XMPP_WEBHOOK_TOKEN}

volumes:
  postgres_data:
  uploads_data:
  prosody_data:         # NEW: persist Prosody's internal_plain user store
```

Notes:
- **Port 5280 exposure:** convenient for manual `curl` during development.
  In a real deployment, remove this line — the admin token is the only guard.
- `prosody_data` volume holds Prosody's `internal_plain` auth backend
  (SQLite-style files). If you truly want single source of truth on
  FastAPI, switch to `authentication = "ldap"` or a custom auth module in v2;
  for now Prosody keeps its own copy and the bridge syncs it.
- `prosody` depends on `backend.service_healthy` because Prosody will
  sometimes call the webhook at startup, and an unreachable webhook
  logs errors (benign but noisy).

### 4.2 Two-server federation — `docker-compose.federation.yml`

New file. Does **not** extend `docker-compose.yml`; it's a complete
stand-alone compose that spins up six services: two backends, two DBs,
two Prosody instances, each backend behind its own DB, both Prosody
instances sharing one federation bridge network.

Key decisions:
- Server B must shift all host-visible ports because server A already
  occupies 5222/5269/5280/8000/5173/5433. Allocations below.
- `extra_hosts` aliases give each Prosody a predictable way to resolve the
  other's VirtualHost name inside the Docker network (no real DNS, no
  `/etc/hosts` mutation on the host).
- Each backend has its own DB so user tables are separate — federation
  between two independent chat deployments, not a shared cluster.

```yaml
services:
  # --- Server A ---
  db_a:
    image: postgres:18
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: hackathon_a
    networks: [internal_a]
    volumes: [postgres_a_data:/var/lib/postgresql]

  backend_a:
    build: { context: ./backend, dockerfile: Dockerfile }
    environment:
      POSTGRES_SERVER: db_a
      POSTGRES_DB: hackathon_a
      XMPP_ENABLED: "true"
      XMPP_HOST: prosody_a
      XMPP_ADMIN_TOKEN: ${XMPP_ADMIN_TOKEN}
      XMPP_WEBHOOK_TOKEN: ${XMPP_WEBHOOK_TOKEN}
    ports: ["8000:8000"]
    networks: [internal_a]
    depends_on: { db_a: { condition: service_healthy } }
    # command identical to docker-compose.yml

  prosody_a:
    image: prosody/prosody:0.12
    ports:
      - "5222:5222"     # c2s
      - "5269:5269"     # S2S
      # 5280 NOT exposed — accessed by backend_a over internal_a only
    volumes:
      - ./jabber/prosody_a.cfg.lua:/etc/prosody/prosody.cfg.lua:ro
      - ./jabber/modules:/usr/lib/prosody/modules-custom:ro
      - prosody_a_data:/var/lib/prosody
    environment:
      FASTAPI_WEBHOOK_URL: "http://backend_a:8000/api/internal/xmpp/event"
      XMPP_WEBHOOK_TOKEN: ${XMPP_WEBHOOK_TOKEN}
    extra_hosts:
      - "server-b.local:prosody_b"   # resolves via Docker DNS
    networks: [internal_a, federation_net]

  # --- Server B ---
  db_b:
    image: postgres:18
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: hackathon_b
    networks: [internal_b]
    volumes: [postgres_b_data:/var/lib/postgresql]

  backend_b:
    build: { context: ./backend, dockerfile: Dockerfile }
    environment:
      POSTGRES_SERVER: db_b
      POSTGRES_DB: hackathon_b
      XMPP_ENABLED: "true"
      XMPP_HOST: prosody_b
      XMPP_ADMIN_TOKEN: ${XMPP_ADMIN_TOKEN}
      XMPP_WEBHOOK_TOKEN: ${XMPP_WEBHOOK_TOKEN}
    ports: ["8001:8000"]
    networks: [internal_b]
    depends_on: { db_b: { condition: service_healthy } }

  prosody_b:
    image: prosody/prosody:0.12
    ports:
      - "5322:5222"     # c2s  (shifted)
      - "5369:5269"     # S2S  (shifted)
      - "5381:5280"     # HTTP admin (shifted; exposed for load-test use only)
    volumes:
      - ./jabber/prosody_b.cfg.lua:/etc/prosody/prosody.cfg.lua:ro
      - ./jabber/modules:/usr/lib/prosody/modules-custom:ro
      - prosody_b_data:/var/lib/prosody
    environment:
      FASTAPI_WEBHOOK_URL: "http://backend_b:8000/api/internal/xmpp/event"
      XMPP_WEBHOOK_TOKEN: ${XMPP_WEBHOOK_TOKEN}
    extra_hosts:
      - "server-a.local:prosody_a"
    networks: [internal_b, federation_net]

networks:
  internal_a:
  internal_b:
  federation_net:   # shared S2S path — ONLY prosody_a and prosody_b attach

volumes:
  postgres_a_data:
  postgres_b_data:
  prosody_a_data:
  prosody_b_data:
```

**Host-port allocation summary (server B):**

| Purpose | Server A (host:container) | Server B (host:container) |
|---|---|---|
| Backend HTTP | 8000:8000 | 8001:8000 |
| XMPP c2s | 5222:5222 | 5322:5222 |
| XMPP S2S | 5269:5269 | 5369:5269 |
| XMPP HTTP admin | not exposed | 5381:5280 |
| Postgres | not exposed | not exposed |

Backends are exposed so a load-test script on the host can hit either side
independently. Postgres stays internal.

**Network topology:**
- `internal_a`: `db_a`, `backend_a`, `prosody_a`. East-west app traffic.
- `internal_b`: `db_b`, `backend_b`, `prosody_b`.
- `federation_net`: only `prosody_a` + `prosody_b`. No backend sits here, so
  a misbehaving backend can't accidentally reach the federation bus. Prosody
  uses this bridge for S2S on port 5269.

**DB separation:** two independent postgres services, two databases
(`hackathon_a`, `hackathon_b`). Alembic runs at boot in each backend (existing
compose command already does `alembic upgrade head && uvicorn …`). No
cross-server DB access; federation logs live in each backend's own DB.

---

## 5. Frontend route map

### 5.1 Routes

Add two routes to `frontend/src/App.tsx` inside the `<ProtectedRoute>`/`<AppShell>`
block:

```
<Route path="/admin/jabber" element={<JabberDashboardPage />} />
<Route path="/admin/jabber/federation" element={<JabberFederationPage />} />
```

New files:
- `frontend/src/pages/JabberDashboardPage.tsx`
- `frontend/src/pages/JabberFederationPage.tsx`
- `frontend/src/hooks/useJabber.ts` (both query hooks)
- Optional: `frontend/src/components/admin/JabberSessionTable.tsx` and
  `JabberFederationTable.tsx` for extraction; the `components/admin/` folder
  already exists.

### 5.2 Nav gating

The top nav (`frontend/src/components/TopNav.tsx`) is the only menu today.
Add a conditional "Jabber Admin" link to the dropdown menu, rendered only
when `me?.is_admin === true`:

```tsx
{me?.is_admin && (
  <Link to="/admin/jabber" onClick={() => setOpen(false)} className="…" role="menuitem">
    Jabber Admin
  </Link>
)}
```

Also gate the route components themselves: if a non-admin somehow navigates
to `/admin/jabber`, the page must render a "Forbidden" stub and **not** fire
the query (the endpoint will 403 anyway, but skipping the request avoids a
red toast). Use `enabled: !!me?.is_admin` on the `useQuery` inside
`useJabber.ts`.

### 5.3 Query hooks (`frontend/src/hooks/useJabber.ts`)

```ts
export function useJabberStatus() {
  return useQuery<JabberStatus>({
    queryKey: ["jabber", "status"],
    queryFn: () => api.get<JabberStatus>("/api/admin/jabber/status"),
    refetchInterval: 10_000,
    refetchOnWindowFocus: false,
    retry: (failCount, err) => failCount < 2 && !isAuthError(err),
  });
}

export function useJabberFederation() {
  return useQuery<JabberFederation>({
    queryKey: ["jabber", "federation"],
    queryFn: () => api.get<JabberFederation>("/api/admin/jabber/federation"),
    refetchInterval: 10_000,
    refetchOnWindowFocus: false,
  });
}
```

Types added to `frontend/src/lib/types.ts`:

```ts
export interface JabberStatus {
  server_host: string;
  uptime_seconds: number;
  connected_clients: number;
  s2s_links_active: number;
  sessions: Array<{ jid: string; client: string; ip: string; connected_seconds: number }>;
  truncated?: boolean;
}

export interface JabberFederation {
  remotes: Array<{ server: string; direction: "in" | "out" | "both"; message_count: number; last_active_seconds_ago: number }>;
  recent: Array<{ ts: string; from_jid: string; to_jid: string; preview: string | null }>;
}
```

Polling at 10 s for both. No WebSocket channel for Jabber events in v1 —
it's an admin dashboard, not a real-time firehose, and the existing
WS connection is already carrying enough for §3 NFRs.

---

## 6. Implementation checklist (file-level assignment)

Translated from `specs/13-jabber.md` §Implementation Checklist into concrete
paths. `/backend`, `/frontend`, `/docker` can work in parallel on their
respective rows; the only ordering constraint is (a) the migration must
land before any route that reads `is_admin`, and (b) the `.env.example`
update should land with the docker compose changes.

### 6.1 `/backend` (Python)

| Task | File(s) |
|---|---|
| Add `is_admin` to User model | `backend/app/models/user.py` |
| Create `FederationLog` model | `backend/app/models/federation.py` (new) |
| Alembic migration (is_admin + federation_log) | `backend/alembic/versions/b2c3d4e5f6a7_add_is_admin_and_federation_log.py` (new) |
| `require_admin` dep | `backend/app/api/deps.py` |
| XMPP bridge wrappers | `backend/app/core/xmpp.py` (new) |
| Config keys | `backend/app/core/config.py` |
| Call `provision_xmpp_user` on register | `backend/app/api/routes/auth.py` (register handler) |
| Call `change_xmpp_password` on password-change + password-reset | `backend/app/api/routes/auth.py` |
| Call `disable_xmpp_user` on account delete | `backend/app/api/routes/auth.py` (delete_account) |
| Admin routes (status + federation) | `backend/app/api/routes/jabber_admin.py` (new) |
| Internal webhook route | same file as above (or split to `jabber_webhook.py` — either works) |
| Schemas | `backend/app/schemas/jabber.py` (new) |
| `UserPublic.is_admin` | `backend/app/schemas/user.py` |
| Register routers | `backend/app/api/main.py` |
| One-off admin CLI | `backend/app/scripts/make_admin.py` (new) |
| Unit tests | `backend/tests/test_jabber_admin.py`, `test_xmpp_bridge.py` (mock `httpx`) |

### 6.2 `/frontend` (React + TS)

| Task | File(s) |
|---|---|
| Add `is_admin` to `UserPublic` | `frontend/src/lib/types.ts` |
| Add `JabberStatus` + `JabberFederation` types | `frontend/src/lib/types.ts` |
| Query hooks | `frontend/src/hooks/useJabber.ts` (new) |
| Dashboard page | `frontend/src/pages/JabberDashboardPage.tsx` (new) |
| Federation page | `frontend/src/pages/JabberFederationPage.tsx` (new) |
| Optional table components | `frontend/src/components/admin/JabberSessionTable.tsx`, `JabberFederationTable.tsx` |
| Routes | `frontend/src/App.tsx` |
| Nav item | `frontend/src/components/TopNav.tsx` |
| Tests | `frontend/src/__tests__/jabber.test.tsx` (mock fetch for both endpoints; assert nav gating on `is_admin=false`) |

### 6.3 `/docker` (infra)

| Task | File(s) |
|---|---|
| Single-server Prosody service | `docker-compose.yml` |
| Federation compose | `docker-compose.federation.yml` (new) |
| Prosody config (single) | `jabber/prosody_single.cfg.lua` (new) |
| Prosody config (server A) | `jabber/prosody_a.cfg.lua` (new) |
| Prosody config (server B) | `jabber/prosody_b.cfg.lua` (new) |
| Webhook Lua module | `jabber/modules/mod_fastapi_webhook.lua` (new) |
| `.env.example` additions | `.env.example` |
| `podman-compose.yml` mirror if it diverges | `podman-compose.yml` (only if docker/podman diverge on the Prosody image) |
| README: Jabber how-to | add a section to the existing `README.md` (no new markdown file) |

### 6.4 `/qa` (follow-up, out of this design but noted for planning)

| Task | File(s) |
|---|---|
| Load test script | `scripts/federation_load_test.py` (new) |
| E2E smoke | `frontend/e2e/jabber-admin.spec.ts` (new) — nav visible only when admin, dashboard renders |
| Unit tests | covered in §6.1 and §6.2 rows above |

---

## 7. Risk / out-of-scope

1. **Message bridge (XMPP ↔ FastAPI chat history) — OUT, v2.** Two-way sync
   between Prosody's `mod_mam` archive and the FastAPI `message` table
   requires either (a) Prosody writing via another webhook into a shared
   schema, or (b) Prosody's MAM backed by the same Postgres. Both are
   substantially larger than the user-provisioning sync and introduce a
   consent question (XMPP messages from a federated remote user into our
   DB). **Skip for initial ship.** The `federation_log` table intentionally
   does NOT share a schema with `message` so flipping this on later is an
   additive change, not a migration of live chat data.

2. **TLS for S2S — dev only.** `s2s_secure_auth = false` in all three
   Prosody configs is a hard requirement for the local Docker federation
   to work without a real CA. **Do not ship to an internet-facing
   deployment as-is.** Production federation needs `mod_s2s_auth_certs`,
   a valid cert chain, and DNSSEC/DANE or at minimum a TOFU pinned fingerprint
   store. Flag in the README next to the federation how-to.

3. **Admin CLI ergonomics.** `make_admin.py` is a foot-gun (anyone who can
   `docker exec` into the backend can grant themselves admin). This is
   fine for a hackathon, not fine for a real deployment — v2 would gate
   it behind a bootstrap env var or a one-time token.

4. **Prosody 0.12 vs 0.13.** Pinned at `0.12` per the spec. If 0.13 ships
   a breaking `mod_http_api` schema before the demo, pin harder
   (`prosody/prosody:0.12.3`); the HTTP API has historically been stable
   within a minor version.

5. **Federation log growth.** No TTL / no partition / no archival. At
   1000 messages/min this table gains ~1.4M rows/day. Hackathon scale is
   fine; for anything longer-lived, add a nightly prune of rows older
   than 30 days. Not in v1.

6. **Connection pool on the webhook path.** The webhook handler writes to
   the same Postgres pool as the API. Prosody is throttled server-side
   (§2.3 token bucket) and the webhook is a single INSERT, so pool
   contention is unlikely — but worth a `/qa` eye during load testing
   (TASK-16 sized the pool at 50+50, which should hold).

7. **`message_preview` and GDPR-style concerns.** Documented in §1.3. The
   `XMPP_LOG_PREVIEWS=false` flag is the operator escape hatch. If a user
   ever requests deletion of their federation log entries, the operator
   must query by `local_jid` / `remote_jid` manually — no self-service
   API in v1.

---

## 8. Acceptance checklist (for `/qa`)

- [ ] `uv run alembic upgrade head` on a v1.0.0 database adds `is_admin` and
      creates `federation_log` without touching existing data.
- [ ] `GET /api/auth/me` returns `is_admin: false` for existing users;
      `uv run python -m app.scripts.make_admin ivan` flips it to true
      without invalidating the active session.
- [ ] With `XMPP_ENABLED=false`, registering a user does NOT call Prosody
      (no outbound httpx call observable in tests) and the register
      endpoint still returns 201.
- [ ] With `XMPP_ENABLED=true` and Prosody up, registering a user creates
      the JID; Gajim can then log in with the same credentials.
- [ ] With Prosody down (`docker compose stop prosody`), registering a user
      still returns 201 within the normal latency window; a WARNING log
      line is emitted with `{action: "provision", status: "timeout"}`.
- [ ] Two-server compose brings up six containers; Prosody A and Prosody B
      complete an S2S handshake (visible in both logs); a message sent from
      `alice@server-a.local` to `bob@server-b.local` arrives, and
      `federation_log` on server A contains the `"out"` row with
      `remote_server="server-b.local"`.
- [ ] `/admin/jabber` renders for an admin, 403s for a non-admin, and
      the nav item is hidden for non-admins.
- [ ] Polling at 10 s on both admin pages does not leak intervals on
      route change (React-Query handles this; one assertion in vitest).
- [ ] `XMPP_LOG_PREVIEWS=false` — webhook inserts NULL `message_preview`
      regardless of payload.

# Release Notes

Consolidated changelog for the hackathon chat app. Conventions: MAJOR.MINOR.PATCH,
dates in UTC, references to `specs/current-state.md` for the authoritative
shipped-state audit and to `specs/*.md` for per-task specs.

---

## `1.1.0` — Advanced: Jabber / XMPP integration
**Date:** 2026-04-21
**Commit:** `6b0f6fe` on `greenbase` (annotated tag `1.1.0`)
**Scope:** Specs §6 Advanced — the last remaining line item from
`specs/Initial-goal-definition.md`.

### Highlights

- Embedded Prosody XMPP server as a Docker sidecar. Users registered through
  the FastAPI web flow are now provisioned into Prosody automatically, so
  standard XMPP clients (Gajim, Pidgin, Conversations) sign in with the same
  credentials.
- Two-server federation topology under `docker-compose.federation.yml`:
  six services, shared `federation_net` with DNS aliases so `server-a.local`
  and `server-b.local` resolve inside the bus without hostname gymnastics.
- Two new admin dashboards — **Jabber Admin** (connection status) and
  **Federation** (S2S traffic) — gated on a new `User.is_admin` flag, polled
  every 10 s from the frontend.
- Single-server Prosody is **opt-in via compose profile** so `docker compose up`
  is byte-identical to `1.0.0` for anyone who doesn't want the sidecar.

### Backend

- `app/core/xmpp.py` — async wrappers (`provision_xmpp_user`,
  `change_xmpp_password`, `disable_xmpp_user`). Fire-and-forget: bridge
  failures never propagate to the user-facing endpoint. Short-circuits to
  `True` when `XMPP_ENABLED=False`.
- `app/core/xmpp_registry.py` — in-memory session + S2S peer cache populated
  by the Prosody webhook.
- `app/api/routes/admin_jabber.py` — `GET /api/admin/jabber/status`,
  `GET /api/admin/jabber/federation`. Both require `is_admin=True`
  (`require_admin` dep).
- `app/api/routes/xmpp_webhook.py` — `POST /api/internal/xmpp/event` with
  `X-XMPP-Webhook-Token` header auth; discriminated union for
  `federation.message` vs. `session.client` events.
- `app/models/user.py` — `is_admin: bool = False` (default false at column
  level, backfilled via Alembic `b2c3d4e5f6a7`).
- `app/models/federation.py` — new `federation_log` table. Metadata-only by
  default; 140-char body preview gated on `XMPP_LOG_PREVIEWS`.
- `app/scripts/make_admin.py` — `uv run python -m app.scripts.make_admin <username>`;
  the only grant path for global admin. Idempotent on re-run.
- `app/api/routes/auth.py` — register / password-change / password-reset /
  account-delete all call the matching bridge function.
- Config additions: `XMPP_ENABLED`, `XMPP_HOST`, `XMPP_HTTP_PORT`,
  `XMPP_DOMAIN`, `XMPP_ADMIN_TOKEN`, `XMPP_WEBHOOK_TOKEN`,
  `XMPP_LOG_PREVIEWS` (all `core/config.py`).

### Frontend

- `UserPublic.is_admin` + `JabberStatus` / `JabberFederation` / `JabberSession`
  types (`lib/types.ts`).
- Typed fetchers `getJabberStatus` / `getJabberFederation` (`lib/api.ts`).
- `useJabberStatus` / `useJabberFederation` hooks — react-query with 10 s
  `refetchInterval`, `enabled: me?.is_admin === true` (`hooks/useJabber.ts`).
- Pages `/admin/jabber` (dashboard) and `/admin/jabber/federation` (traffic).
  Non-admins bounced to `/chat` client-side; API layer enforces independently.
- `TopNav` renders "Jabber Admin" + "Federation" links only when
  `me.is_admin === true`.

### Docker + Prosody

- `docker-compose.yml` — adds `prosody` service under `profiles: ["jabber"]`.
  Image `prosody/prosody:0.11.9` (0.12 not published on docker.io as of
  2026-04-21; inline comment tracks the pin).
- `docker-compose.federation.yml` — standalone two-server topology:
  `prosody_a`/`prosody_b` on shared `federation_net` with per-container DNS
  aliases (`server-a.local`, `server-b.local`), two independent
  `backend_a`/`backend_b` + `db_a`/`db_b` stacks on separate `internal_a`/
  `internal_b` bridges.
- `jabber/modules/mod_admin_api.lua` — custom Lua module we ship ourselves
  because `prosody/prosody:0.11.9` doesn't bundle `mod_http_api`. Four
  bearer-token-authenticated endpoints under `/admin/*`: `create_user`,
  `change_user_password`, `delete_user`, `test_password` (the last added
  during QA verification).
- `jabber/modules/mod_fastapi_webhook.lua` — hooks `message/bare`,
  `message/full`, `resource-bind`, `resource-unbind` and POSTs events to
  FastAPI.

### Load test

- `scripts/federation_load_test.py` — slixmpp-based harness. Defaults to
  50 clients per server, 1 msg/sec each, 120 s. Reports sent / delivered /
  lost + avg / p95 / p99 latency + throughput. Configurable via `argparse`.

### Docs

- `specs/13-jabber-design.md` — authoritative design contract, produced
  up front as a no-code pass.
- `specs/JabberIntegrationResults.md` — as-built record including the
  full 5-step verification plan with results (Chrome-DevTools-driven UI
  smoke, synthesized webhook round-trip, server-side credential check).
- `specs/current-state.md` — flipped §6 from "out of scope" to shipped
  (Wave 7) and updated test counts.

### Testing

- **Backend:** `241 → 264 passing` (+23 across `test_xmpp_bridge.py`,
  `test_admin_jabber.py`, `test_xmpp_webhook_edges.py`,
  `test_auth_xmpp_wiring.py`, `test_make_admin.py`). 1 pre-existing skip;
  1 PG-dependent test deselected in CI-less runs.
- **Frontend:** `149 → 156 passing vitest` (+7 across
  `__tests__/jabber.test.tsx`). TypeScript clean. Production Vite build
  clean.
- **Manual verification:** end-to-end 5-step plan in
  `specs/JabberIntegrationResults.md §5` — register provisions JID on
  disk; `mod_admin_api.test_password` confirms credentials; webhook
  round-trip populates admin dashboards; UI smoke as admin + non-admin
  via Chrome DevTools.

### Known issues (logged for v2)

All five flagged during the architect post-implementation review;
none release-blocking.

1. 🟡 Webhook token comparison uses `!=` instead of `hmac.compare_digest`
   (`xmpp_webhook.py:46`).
2. 🟡 No token-bucket throttle on the Prosody webhook (design §2.3 asked
   for 202 over 500 events/sec).
3. 🟡 HTTP contract drift when `XMPP_ENABLED=False`: admin endpoints
   return 200 with zeroed counters instead of 503; webhook returns 401
   instead of 410.
4. 🟢 `federation_log` composite index `(remote_server, ts)` downgraded
   to a single-column index on `remote_server`.
5. 🟢 `require_admin` dep lives in `admin_jabber.py` instead of the
   shared `deps.py`. Functionally identical; move on next touch.

### Breaking changes

None. `1.0.0` deployments upgrade cleanly — `alembic upgrade head` adds
`is_admin` (default false) and `federation_log` without touching existing
data. `XMPP_ENABLED=0` remains the default, so the bridge never fires
until explicitly turned on.

### Upgrade notes

```bash
cp .env.example .env          # then edit XMPP_ENABLED=1 to opt in
docker compose --profile jabber up --build -d
# first admin grant (no self-service path):
docker compose exec backend uv run python -m app.scripts.make_admin <username>
```

Without `--profile jabber`, the stack boots identically to `1.0.0`.

---

## `1.0.0` — Core chat app
**Date:** 2026-04-21
**Commit:** `2cfb619` on `greenbase` (annotated tag `1.0.0`,
pre-release `1.0.0-rc` for staging verification).
**Scope:** All core requirements from `specs/Initial-goal-definition.md`
§§ 2–5 plus NFRs from §3 independently verified via TASK-16. §6 (Jabber)
explicitly deferred (landed in `1.1.0`).

### Accounts & Auth (spec §2.1)

- Register / login / logout, persistent session via "keep me signed in"
  cookie.
- Password reset (request + token-based apply) and password change
  (`/api/auth/password-reset-request`, `password-reset`,
  `password-change`).
- Account deletion cascades: owned rooms + messages + attachments +
  read receipts + room memberships + friendships + bans + presence +
  sessions are all removed; user record soft-deleted (tombstone
  preserves the username).

### Presence & sessions (spec §2.2)

- `online` / `afk` / `offline` status with multi-tab awareness
  (`PresenceManager.compute_status`).
- 1-minute AFK threshold (`useActivityTracker` — `IDLE_MS = 60_000`).
- Active-sessions list + selective logout (`SessionsPage` +
  `session.revoked` WS event) — TASK-11.

### Contacts / friends (spec §2.3)

- Friend list + request-by-username + accept + remove.
- User-to-user ban (`/api/bans`) with frozen-history semantics.
- DM gated on friendship + no-ban (`personal.py:49-54`).
- "Send friend request" entry in chat-room member context menu
  (`MemberRowMenu.tsx`).

### Chat rooms (spec §2.4)

- Public catalog + private + invite-only, join/leave, room deletion
  cascade, ban list, invitations.
- Room name uniqueness enforced at 422 (`rooms.py:150-151`).
- Admin UI (spec §4.5) shipped in TASK-10 as a modal.
- Owner / admin / member role rules enforced server-side.

### Messaging (spec §2.5)

- Replies, edit (with "edited" label), delete, 3 KB max, UTF-8 incl.
  emoji. `Message.content: max_length=3072`.
- Infinite scroll via cursor pagination (`useMessages` +
  `MessageThread`).
- Offline delivery via persisted history — `message.new` WS is
  ephemeral; full history on next open.

### Attachments (spec §2.6)

- Image + arbitrary file, upload button + paste, original filename,
  optional comment.
- Access-control gated on room membership; files persist after a
  user loses access.
- 20 MB file / 3 MB image limits (`config.py:29-30`,
  `attachments.py:33-34`).

### Notifications (spec §2.7)

- Unread badges per room + per contact (TASK-08 + Wave 1 browser-tab
  title counter).
- Presence latency < 2 s (WS direct fan-out; p99 measured at 87 ms
  under TASK-16 S3).

### UI (spec §4)

- Three-pane layout, top menu, message area, input (§4.1).
- Accordion collapse on active room / DM (`SidebarLeft.tsx`, Wave 3).
- Auto-scroll + no-force-scroll + infinite scroll (§4.2).
- Multiline + emoji + attachments + reply (§4.3).
- Unread visual indicators (§4.4).
- Admin UI via modal (§4.5, TASK-10).

### Non-functional (spec §3) — TASK-16

Full Locust + pytest load-test suite under `loadtests/`. Five scenarios —
`steady_state_300`, `fanout_1000`, `presence_propagation`,
`history_10k_read`, `persistence_restart` — all **PASS** on `bf8acef`.
See `loadtests/RESULTS.md` for p50/p95/p99 numbers and the topology
deviation note for S2.

Backend mitigations that landed with TASK-16:
- `send_to_room` fan-out via `asyncio.gather`
- `pool_size=50` / `max_overflow=50`
- Per-room member cache on `ConnectionManager`
- Uvicorn `--ws-ping-interval 20 --ws-ping-timeout 30`
- `client_msg_id` echo-through for latency attribution

QA follow-up `2cfb619`: `ws.py` helpers routed through
`core/db.session_scope()` so unit tests can monkeypatch the WS DB session.
12 new direct tests for auth / upsert / audience paths.

### Testing at tag time

- Backend: **223 pytest passing** (1 pre-existing skip).
- Frontend: **149 vitest passing** · 0 TypeScript errors · clean Vite
  build.
- E2E: 12 Playwright specs passing (including the Wave-6 reply
  round-trip spec landed above the tag).
- Load: 5/5 NFR scenarios PASS.
- Migration auto-applies on container boot.

### Post-tag waves living on `greenbase` between `1.0.0` and `1.1.0`

- **Wave 6** — post-demo polish: inline image preview, reply-spec
  Playwright coverage, surgical `message.new` cache update via
  `mergeNewMessage`.

### Explicit non-goals at `1.0.0`

- **§6 Advanced / Jabber integration** — deferred. Landed in `1.1.0`.
- **Message bridge (XMPP ↔ FastAPI chat history)** — noted in the
  `1.1.0` design as v2.
- **MUC (group chat over XMPP)** — out of scope; rooms remain
  FastAPI-only in `1.1.0` as well.

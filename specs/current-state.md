
⏺ Gap audit — Initial-goal-definition.md vs shipped state

  Bottom line: **16 of 16 core requirements + advanced Jabber/XMPP integration
  (TASK-13) + NFR load-testing (TASK-16) shipped**. Releases tagged **`1.0.0`**
  (2026-04-21, core scope) and **`1.1.0`** (2026-04-21, Jabber/XMPP) on
  `greenbase`.

  Section-by-section coverage

  §2.1 Accounts & Auth — ✅ complete

  - 2.1.1–2.1.3 Register/login/logout/persistent session — ✅ (auth.py, LoginPage, RegisterPage, "keep me signed in" cookie)
  - 2.1.4 Password reset + change — ✅ (auth.py:128-170, ForgotPasswordPage, ResetPasswordPage)
  - 2.1.5 Account deletion cascades owned rooms — ✅ (auth.py:182-252, ProfilePage:96-146)

  §2.2 Presence & sessions — ✅ complete

  - 2.2.1–2.2.3 online/AFK/offline multi-tab — ✅ (PresenceManager.compute_status)
  - 2.2.2 1-minute AFK threshold — ✅ (useActivityTracker:4 — IDLE_MS = 60_000)
  - 2.2.4 Active-sessions list + selective logout — ✅ (SessionsPage, session.revoked WS, shipped TASK-11)

  §2.3 Contacts/friends — ✅ complete

  - 2.3.1–2.3.4 Friend list, request by username, accept, remove — ✅
  - 2.3.5 User-to-user ban — ✅ backend (/api/bans) + UI in `ContactRow.tsx` ⋮ menu ("Ban user" with confirm modal)
  - 2.3.6 DM gated on friends + no-ban — ✅ (personal.py:49-54)
  - 2.3.2 Friend request "from user list in chat room" — ✅ Wave 3 closed via `MemberRowMenu.tsx` (right sidebar ⋮ → "Send friend request")

  §2.4 Chat rooms — ✅ complete

  - All owner/admin/member role rules, public catalog, private+invite, join/leave, room deletion cascade, ban list, invitations — ✅
  - Room name uniqueness 422 — ✅ (rooms.py:150-151)
  - Admin UI (spec §4.5) — ✅ shipped in TASK-10

  §2.5 Messaging — ✅ complete

  - Replies + edit (with "edited" label) + delete + 3 KB max + UTF-8 — ✅ (MessageBubble:172-174; Message.content: max_length=3072)
  - Infinite scroll — ✅ (MessageThread:47-54 + useMessages cursor pagination)
  - Offline delivery via persisted history — ✅ (message.new ephemeral; full history on next open)

  §2.6 Attachments — ✅ complete

  - Image + arbitrary file, upload button + paste, original filename, optional comment — ✅
  - Access-control gated on room membership; files persist after access loss — ✅
  - 20 MB file / 3 MB image — ✅ (config.py:29-30, attachments.py:33-34)

  §2.7 Notifications — ✅ complete

  - Unread badges per room/contact — ✅ (TASK-08 + Wave 1 browser-tab title)
  - Presence latency <2 s — ✅ (WS direct fanout, measured at p99 87 ms in S3)

  §3 NFRs — ✅ measured and passing (TASK-16)

  - Full Locust + pytest load-test suite lives under `loadtests/`. Five scenarios
    (`steady_state_300`, `fanout_1000`, `presence_propagation`, `history_10k_read`,
    `persistence_restart`) all **PASS** on `bf8acef`. See `loadtests/RESULTS.md` for
    p50/p95/p99 numbers and the topology deviation note for S2.
  - Persistence, file-size limits, session behavior — ✅

  §4 UI — ✅ complete

  - 4.1 Three-pane layout, top menu, message area, input — ✅
  - 4.1.1 Accordion collapse on active room — ✅ Wave 3 (`SidebarLeft.tsx`: Contacts collapses on regular-room nav, Rooms collapses on DM nav, user caret toggle overrides)
  - 4.2 Auto-scroll + no-force-scroll + infinite scroll — ✅
  - 4.3 Multiline + emoji (UTF-8) + attachments + reply — ✅
  - 4.4 Unread visual indicators — ✅
  - 4.5 Admin UI via modal — ✅ (TASK-10)

  §5 Notes — ✅ all invariants covered

  Username immutable ✅ (no PATCH for username); email/username unique ✅; frozen history after user-ban ✅ (read-only); room-delete cascade ✅.

  §6 Advanced (Jabber) — ✅ shipped post-v1.0.0 (Wave 7, 2026-04-21)

  TASK-13 landed on `greenbase`:
  - Prosody XMPP sidecar (`prosody/prosody:0.11.9`, opt-in via
    `--profile jabber`) + two-server federation compose
    (`docker-compose.federation.yml`, six services: two Prosody, two backends,
    two Postgres, shared `federation_net` with DNS aliases).
  - FastAPI→Prosody bridge (`backend/app/core/xmpp.py`): provision on
    register, change on password-reset + password-change, disable on
    account-delete. Fire-and-forget; bridge failures never block the
    user-facing endpoint.
  - Prosody→FastAPI webhook (`POST /api/internal/xmpp/event`, shared-secret
    token). Mounted Lua module (`jabber/modules/mod_fastapi_webhook.lua`)
    hooks `message/bare`, `message/full`, `resource-bind`, and
    `resource-unbind` to post federation + client-session events.
  - Admin routes (`GET /api/admin/jabber/status`,
    `GET /api/admin/jabber/federation`) gated by `require_admin` dep;
    `User.is_admin` added via Alembic revision `b2c3d4e5f6a7`.
  - Admin screens (`/admin/jabber`, `/admin/jabber/federation`) polled at
    10 s, surfaced in `TopNav` only when `is_admin=true`.
  - Bootstrap CLI: `uv run python -m app.scripts.make_admin <username>`.
  - Load test: `scripts/federation_load_test.py` (slixmpp-based; default
    50+50 clients, configurable rate/duration).
  - Verified: 241 backend tests pass (19 new: `test_xmpp_bridge.py` +
    `test_admin_jabber.py`); 153 vitest (4 new: `jabber.test.tsx`); TS
    clean; production Vite build clean; both compose files validate.

  ---
  Spec-complete status (v1.1.0, 2026-04-21)

  All §2–§6 requirements shipped. §3 NFRs independently verified via TASK-16.
  §6 (Jabber) delivered in Wave 7 (TASK-13) after the `1.0.0` cut.

  Release trail:

  - **Wave 3 (2026-04-20)** — member context menu, sidebar accordion, contact-row ban
  - **Wave 4 (2026-04-20) — TASK-15** — personal-room display names (`RoomPublic.display_name`;
    `@<username>` for DMs, `#<name>` for rooms)
  - **Wave 5 (2026-04-21) — TASK-16** — NFR load-test harness + results
    - Locust file (`loadtests/locustfile.py`) with scenarios S1-S4; pytest
      `test_persistence_restart.py` for S5; `backend/scripts/seed_load.py` with
      all required flags; `RESULTS.md` with real run numbers.
    - Backend mitigations that landed during the run: `send_to_room` fan-out
      via `asyncio.gather`, `pool_size=50` / `max_overflow=50`, per-room
      member cache on `ConnectionManager`, uvicorn `--ws-ping-interval 20
      --ws-ping-timeout 30`, `client_msg_id` echo-through for latency attribution.
    - QA follow-up `2cfb619`: `ws.py` helpers routed through
      `core/db.session_scope()` so unit tests can monkeypatch the WS DB
      session. 12 new direct tests for auth / upsert / audience paths.
  - **Release tag `1.0.0`** (annotated, signed author `ivan.tsekhmistro`, on
    `greenbase`). Preceded by `1.0.0-rc` for staging verification.
  - **Wave 6 (2026-04-21, post-tag) — post-demo polish** — three items drawn from the
    deferred list, low-risk and already exercised by the test suite:
    - Inline image preview: `MessageBubble.tsx` distinguishes `image/*` MIME
      types and renders `<img>` (max-h 16rem, object-contain) linked to the
      same `/api/attachments/:id` URL, with a filename/size caption below.
      Non-image attachments still render as the text-link chip. Covered by
      two new vitest cases.
    - Reply round-trip Playwright coverage: `e2e/reply.spec.ts` sends a
      message, clicks ↩ on its bubble, sends a reply, and asserts the new
      bubble's `data-testid="reply-preview"` element contains the original
      message's text — proving both the server's `reply_preview` computation
      and the client's render.
    - Surgical `message.new` cache update: `hooks/useMessages.ts` exports
      `mergeNewMessage`, an idempotent infinite-query splice that prepends
      the WS-echoed `MessagePublic` into `pages[0]`. `App.tsx` now calls
      this instead of `invalidateQueries` on `message.new`. Listeners in a
      1000-member room no longer trigger a per-message refetch; 4 new
      vitest cases cover prepend / dedupe / unopened-room / empty-pages.
  - **Wave 7 (2026-04-21, post-tag) — TASK-13 Jabber/XMPP integration**
    (commits `8662caf` + `6b0f6fe`). Design-first (`specs/13-jabber-design.md`),
    as-built record (`specs/JabberIntegrationResults.md`). Architect
    post-implementation review cleared the work for `1.1.0` — five polish
    items (constant-time token compare, webhook throttle, disabled-bridge
    HTTP contract, composite index, `require_admin` file location) noted for
    v2 as 🟡/🟢, none release-blocking.
    - Single-server Prosody sidecar behind `profiles: ["jabber"]` so
      `docker compose up` is byte-identical to v1.0.0.
    - Two-server federation topology (`docker-compose.federation.yml`:
      six services, three networks, DNS aliases on `federation_net`).
    - FastAPI→Prosody bridge (`backend/app/core/xmpp.py`): provision /
      change / disable hooked into register, password-change,
      password-reset, account-delete. Fire-and-forget; bridge failures
      never block the user-facing endpoint.
    - Prosody→FastAPI webhook (`POST /api/internal/xmpp/event`) with
      shared-secret auth; persists S2S traffic to `federation_log` and
      mutates the in-memory session registry.
    - Admin dashboards `/admin/jabber` + `/admin/jabber/federation` gated
      on `User.is_admin` (Alembic `b2c3d4e5f6a7`); polled every 10 s.
    - Bootstrap CLI: `uv run python -m app.scripts.make_admin <username>`.
    - slixmpp load-test harness `scripts/federation_load_test.py`.
    - Custom Lua modules: `mod_admin_api.lua` (user provisioning surface
      — `prosody/prosody:0.11.9` doesn't ship `mod_http_api`) and
      `mod_fastapi_webhook.lua` (pushes session + federation events).
    - +23 backend pytest cases (bridge, admin routes, webhook edges,
      auth wiring, `make_admin` CLI), +7 vitest cases (dashboard,
      federation, nav gating).
    - Verified end-to-end per the 5-step plan in
      `specs/JabberIntegrationResults.md §5` incl. Chrome-DevTools-driven
      UI smoke; live two-server S2S handshake the only piece not
      exercised this pass.

  ---
  Demo-script confidence (5-step happy path)

  1. Register + login → `e2e/auth.spec.ts` (×3)
  2. Create + join room → `e2e/rooms.spec.ts` (×2)
  3. Send message + attachment → `e2e/attachments.spec.ts` (text file asserted; image preview falls through to the same text-link rendering)
  4. Unread badge → `e2e/unread.spec.ts` (two browser contexts, appear + clear)
  5. DM open + ban-kick + admin moderation → `e2e/dm.spec.ts` + `e2e/ban-kick.spec.ts` + `e2e/admin.spec.ts`

  Smoke coverage: `e2e/smoke.spec.ts` walks `/chat`, `/rooms`, `/sessions`, `/profile` — no uncaught console errors, exactly one "Current session" pill.

  ---
  Final verification (2026-04-21, v1.1.0 — Wave 6 + Wave 7)

  - Backend: **264** pytest passing (1 pre-existing skip, 1 PG-dependent
    deselect) — was 223 at `1.0.0`; +18 during Wave 6/early-TASK-16
    follow-ups, +23 during Wave 7 (TASK-13 bridge/admin/webhook/wiring/CLI)
  - Frontend: **156** vitest passing — was 149; Wave 7 added 7 (dashboard +
    federation + nav gating) · 0 TypeScript errors · clean Vite build
  - E2E: 12 Playwright specs passing (unchanged since Wave 6)
  - Load: 5/5 NFR scenarios PASS (see `loadtests/RESULTS.md`)
  - Migration auto-applies on container boot (idempotent); uploads persist across `force-recreate`
  - TASK-13 architect post-ship review: cleared for `1.1.0`; five polish
    items (all 🟡/🟢) logged for v2
  - No open 🔴 blockers

  Branch: `greenbase` · release tags: `1.0.0` (commit `2cfb619`, core) and
  `1.1.0` (commit `6b0f6fe`, Jabber/XMPP). Wave 6 lives between the two tags;
  Wave 7 is the `1.1.0` tag.

  ---
  Deferred (post-demo)

  - ✅ ~~Inline image preview for attachments~~ — shipped Wave 6 (`MessageBubble.tsx`; 2 vitest cases)
  - ✅ ~~Reply round-trip Playwright coverage~~ — shipped Wave 6 (`e2e/reply.spec.ts`)
  - ✅ ~~`message.new` cache invalidation is per-room refetch~~ — shipped Wave 6 (`mergeNewMessage` in `hooks/useMessages.ts`; 4 vitest cases)
  - 🟡 `room.invitation_cancelled` WS event — currently admin cancel is local-refetch only; invitee's "pending invitation" banner stays live until they refresh or click-through. Cosmetic at demo scale
  - ✅ ~~Jabber / XMPP federation (`specs/13-jabber.md`)~~ — shipped Wave 7
    (TASK-13) in `1.1.0`. Architect review logged five v2 polish items:
    constant-time webhook-token compare, Prosody→FastAPI event
    throttle/202, disabled-bridge 503/410 HTTP contract, composite
    `federation_log` index, moving `require_admin` from `admin_jabber.py`
    to `deps.py`. See `specs/JabberIntegrationResults.md` for full
    verification results and `specs/RELEASE-NOTES.md` for the consolidated
    changelog.

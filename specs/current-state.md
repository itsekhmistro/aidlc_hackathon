
⏺ Gap audit — Initial-goal-definition.md vs shipped state

  Bottom line: **16 of 16 core requirements shipped + NFR load-testing (TASK-16) verified**.
  Release tagged **`1.0.0`** (annotated, on `greenbase`, 2026-04-21). Advanced Jabber
  scope not attempted (explicitly optional in spec §6).

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

  §6 Advanced (Jabber) — ❌ not attempted (explicitly optional)

  No XMPP server, no federation, no Jabber UI. Spec says "if you manage to implement requirements above quickly" — given TASK-10 landed T-24h before demo, Jabber is out of realistic scope.

  ---
  Spec-complete status (v1.0.0, 2026-04-21)

  All §2–§5 requirements shipped **and** §3 NFRs independently verified via TASK-16.
  §6 (Jabber) remains out of scope per original carve-out.

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

  ---
  Demo-script confidence (5-step happy path)

  1. Register + login → `e2e/auth.spec.ts` (×3)
  2. Create + join room → `e2e/rooms.spec.ts` (×2)
  3. Send message + attachment → `e2e/attachments.spec.ts` (text file asserted; image preview falls through to the same text-link rendering)
  4. Unread badge → `e2e/unread.spec.ts` (two browser contexts, appear + clear)
  5. DM open + ban-kick + admin moderation → `e2e/dm.spec.ts` + `e2e/ban-kick.spec.ts` + `e2e/admin.spec.ts`

  Smoke coverage: `e2e/smoke.spec.ts` walks `/chat`, `/rooms`, `/sessions`, `/profile` — no uncaught console errors, exactly one "Current session" pill.

  ---
  Final verification (2026-04-21, v1.0.0 + Wave 6)

  - Backend: 223 pytest passing (1 pre-existing skip) — up from 211 after the
    TASK-16 QA pass added 12 direct WS-helper tests
  - Frontend: 149 vitest passing (was 139; Wave 6 added 2 image-preview
    and 4 `mergeNewMessage` cases) · 0 TypeScript errors · clean Vite build
  - E2E: 12 Playwright specs passing (was 11; Wave 6 added `reply.spec.ts`)
  - Load: 5/5 NFR scenarios PASS (see `loadtests/RESULTS.md`)
  - Migration auto-applies on container boot (idempotent); uploads persist across `force-recreate`
  - No open 🔴 blockers

  Branch: `greenbase` · release tag: `1.0.0` (commit `2cfb619`). Wave 6 lives
  on `greenbase` above the tag.

  ---
  Deferred (post-demo)

  - ✅ ~~Inline image preview for attachments~~ — shipped Wave 6 (`MessageBubble.tsx`; 2 vitest cases)
  - ✅ ~~Reply round-trip Playwright coverage~~ — shipped Wave 6 (`e2e/reply.spec.ts`)
  - ✅ ~~`message.new` cache invalidation is per-room refetch~~ — shipped Wave 6 (`mergeNewMessage` in `hooks/useMessages.ts`; 4 vitest cases)
  - 🟡 `room.invitation_cancelled` WS event — currently admin cancel is local-refetch only; invitee's "pending invitation" banner stays live until they refresh or click-through. Cosmetic at demo scale
  - ⬜ Jabber / XMPP federation (`specs/13-jabber.md`) — advanced scope, not targeted for this hackathon

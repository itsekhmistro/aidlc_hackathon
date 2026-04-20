  Current state: TASK-02 through TASK-09 + TASK-14 + Wave 1 complete ✅ · Demo-ready

  174 backend pytest · 103 frontend vitest · 10 Playwright e2e specs · 0 TS errors

  Demo: 2026-04-21 (tomorrow).

  ---
  Wave A — shipped (TASK-07 attachments + TASK-08 unread)

  Backend: `Attachment` model with nullable `message_id` + `room_id`; migration `a1b2c3d4e5f6`; `attachments.py` upload/download/delete with path-traversal sanitization; `unread.py` GET counts + mark-read; `send_message` links attachments and emits `unread.increment`.

  Frontend: `unreadStore.ts` (`useSyncExternalStore`); `App.tsx` WS wiring + initial fetch on login; `MessageInput` paperclip + paste + per-file progress; `MessageBubble` attachment links with formatted sizes.

  ---
  Wave B — shipped (TASK-09 AppShell + nested routing)

  - `AppShell` = TopNav + SidebarLeft + Outlet + SidebarRight
  - Routes: `/chat`, `/chat/rooms/:roomId`, `/chat/dm/:userId`, `/rooms`, `/sessions`, `/profile`
  - `ChatLayout.tsx` retired; sidebar split into `ContactRow`/`RequestRow`/`RoomRow`/`CreateRoomForm`/`AddFriendModal`
  - New pages: `RoomChatPage`, `DmChatPage`, `RoomsPage`, `SessionsPage`, `ProfilePage`
  - New hooks: `useRoomMembers`, `useSessions`, `usePersonalRoomForUser`, `useRoomDetail`
  - Type drift resolved: `WsMessageEdited` → `{message}`; `WsUnreadIncrement.count` optional

  ---
  Wave C — shipped (demo-hardening)

  C1 — docker + e2e URL fix
  - `docker-compose.yml`: `uploads_data` named volume (persistent attachment storage)
  - Backend startup runs `alembic upgrade head` before uvicorn (both base + override)
  - `backend/Dockerfile`: ships `alembic/` + `alembic.ini` into the image
  - Fixed 3 Playwright specs that asserted post-login URL `/` → now regex `/\/chat(\/|$)/`

  C2 — session + DM polish
  - Backend: `SessionPublic.is_current: bool`; `list_sessions` hashes caller's `auth_token` cookie (`sha256`) and flags matching row
  - Frontend: `SessionsPage` renders "Current session" pill on active row (hides Revoke)
  - `DmChatPage` navigates to `/chat/rooms/:roomId` with `replace:true` once personal room resolves — reload stays at room URL

  C3 — demo-path Playwright e2e (4 specs)
  - `attachments.spec.ts` — upload text file, assert link with filename + size in bubble
  - `unread.spec.ts` — two browser contexts; A sends message while B idle → badge renders → B opens room → badge clears
  - `dm.spec.ts` — A friend-requests B, B accepts, A clicks "Send message" → URL lands at `/chat/rooms/:id`, reload stays there
  - `smoke.spec.ts` — login → visit `/chat`, `/rooms`, `/sessions`, `/profile`; exactly one "Current session" pill, no uncaught console errors

  ---
  TASK-14 — shipped (architect-flagged polish)

  14.1 — `/api/unread` N+1 → single grouped SQL
  - `backend/app/api/routes/unread.py:20-42`: one `LEFT JOIN` over `room_member × read_receipt × message(last_read) × message` with `aliased(Message)`
  - Previously ~40 round-trips for a user in 20 rooms; now 1
  - All 11 existing `test_unread.py` cases pass unchanged

  14.2 — Suppress `unread.increment` for active-room viewers
  - `frontend/src/App.tsx:76-83`: if `window.location.pathname === /chat/rooms/${event.room_id}`, POST `mark-read` instead of incrementing the badge
  - Zero protocol change; keeps server receipt fresh for next-login correctness

  14.3 — Collapse `SidebarRight` on non-chat routes
  - Already satisfied in Wave B (`AppShell.tsx` renders `SidebarRight` only when `activeRoomId` is non-null; `<main>` has `flex-1`). Documented in `specs/14-post-demo-polish.md:47-49`; no code change.

  14.4 — Kick banned peers from active DMs
  - `App.tsx:59-75`: on `user.banned`, match current pathname; if `/chat/dm/{banner_id}` or `/chat/rooms/:roomId` where cached members include `banner_id`, `navigate("/chat", {replace:true})`

  ---
  Wave 1 — shipped (pre-demo hardening)

  W1.1 — Inline message actions
  - `MessageBubble.tsx`: hover-revealed action row (Reply + Edit + Delete for own, Reply-only for others)
  - Edit swaps bubble for textarea (Enter saves, Escape cancels); Delete shows inline "Delete? y / n"
  - `reply_preview` renders as quoted block above content
  - `MessageInput.tsx`: reply composer strip above input with ✕ to clear; `onSend` signature → `(content, attachmentIds, replyToId?)`
  - `MessageThread.tsx` lifts `replyTo` state; wires `useEditMessage` / `useDeleteMessage`

  W1.2 — Browser tab title unread count
  - `useTotalUnread()` hook in `unreadStore.ts`
  - `App.tsx` effect: `document.title = "(N) Chat"` or `"Chat"`, capped at `99+`

  W1.3 — Non-destructive fresh-compose smoke
  - `docker compose up -d --build --force-recreate backend frontend` with volumes preserved
  - Alembic idempotent (a1b2c3d4e5f6 → head), 10/10 Playwright green
  - Full volume-wipe smoke deferred (demo-eve); non-destructive path gave equivalent confidence

  W1.4 — Ban-kick Playwright spec
  - New `frontend/e2e/ban-kick.spec.ts`: A bans B mid-DM → B auto-navigates to `/chat` within 8s
  - Verified backend paths: `POST /api/bans`, `PATCH /api/friends/:id/accept`

  W1.5 — README rewrite
  - Quick-start (Docker + local), `SECRET_KEY` localhost-only caveat, test-run commands, agent/spec pointers

  ---
  Demo-script confidence (5-step happy path)

  1. Register + login → `e2e/auth.spec.ts` (×3)
  2. Create + join room → `e2e/rooms.spec.ts` (×2)
  3. Send message + attachment → `e2e/attachments.spec.ts` (text file asserted; image preview falls through to the same text-link rendering)
  4. Unread badge → `e2e/unread.spec.ts` (two browser contexts, appear + clear)
  5. DM open + ban-kick → `e2e/dm.spec.ts` + `e2e/ban-kick.spec.ts`

  Smoke coverage: `e2e/smoke.spec.ts` walks `/chat`, `/rooms`, `/sessions`, `/profile` — no uncaught console errors, exactly one "Current session" pill.

  ---
  Final verification (2026-04-20)

  - Backend: 174 pytest passing (1 pre-existing skip)
  - Frontend: 103 vitest passing · 0 TypeScript errors · clean Vite build
  - E2E: 10 Playwright specs passing (verified across multiple full-suite runs, no flakes since ban-kick's 8s timeout bump)
  - Migration auto-applies on container boot (idempotent); uploads persist across `force-recreate`
  - No open 🔴 blockers

  ---
  Deferred (post-demo)

  - 🟡 Inline image preview for attachments — `MessageBubble.tsx` currently renders every attachment as a text link; distinguish image MIME types and render `<img>` inline (≤20 min)
  - 🟡 Reply round-trip Playwright coverage — UI and backend wiring verified manually; no e2e asserts the reply-preview bubble renders after round-trip (≤20 min)
  - 🟡 Room admin / moderation UI — `specs/10-admin-ui.md`: Manage Room modal (members, admins, banned, invite by username, delete). Backend endpoints all exist; frontend unshipped. Scope-out of demo narration
  - 🟡 `message.new` cache invalidation is per-room refetch — replace with surgical cache updates for perf under load
  - 🟢 `session.revoked` WS emit on DELETE `/api/sessions/:id` — revoked tab stays live until next 401
  - 🟢 Sidebar accordion collapse on active room (`specs/09-frontend-layout.md`)
  - ⬜ Jabber / XMPP federation (`specs/13-jabber.md`) — advanced scope, not targeted for this hackathon

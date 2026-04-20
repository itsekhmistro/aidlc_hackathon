  Current state: TASK-02 through TASK-09 complete ✅ · Wave A + B + C shipped · Demo-ready

  173 backend tests · 98 frontend unit tests · 9 Playwright e2e specs

  ---
  Wave A — shipped (TASK-07 attachments + TASK-08 unread)

  Backend: Attachment model with nullable `message_id` + `room_id`; migration `a1b2c3d4e5f6`; `attachments.py` upload/download/delete; `unread.py` GET counts + mark-read; `send_message` links attachments + emits `unread.increment`.

  Frontend: `unreadStore.ts` (`useSyncExternalStore`); `App.tsx` WS wiring + initial fetch; `MessageInput` paperclip/paste/progress; `MessageBubble` attachment links with formatted sizes.

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
  - Backend startup now runs `alembic upgrade head` before uvicorn (both base + override)
  - `backend/Dockerfile`: ships `alembic/` + `alembic.ini` into the image
  - Fixed 3 Playwright specs that asserted post-login URL `/` → now regex `\/chat(\/|$)/`
  - Verified: DB at `a1b2c3d4e5f6 (head)`; attachment schema nullable + `room_id`; `/uploads` writable

  C2 — session + DM polish
  - Backend: `SessionPublic.is_current: bool`; `list_sessions` hashes caller's `auth_token` cookie (`sha256`) and flags matching row. +2 pytest cases.
  - Frontend: `SessionsPage` renders "Current session" pill on the active row (hides Revoke). +1 vitest case.
  - `DmChatPage` navigates to `/chat/rooms/:roomId` with `replace:true` once personal room resolves — reload stays at room URL.

  C3 — demo-path Playwright e2e (4 new specs, all green)
  - `attachments.spec.ts` — upload text file via hidden input, assert link with filename + size in bubble
  - `unread.spec.ts` — two browser contexts; A sends message while B idle → badge renders → B opens room → badge clears
  - `dm.spec.ts` — A friend-requests B (via `/api/friends/request`), B accepts, A clicks "Send message" → URL lands at `/chat/rooms/:id`, reload stays there
  - `smoke.spec.ts` — login → visit `/chat`, `/rooms`, `/sessions`, `/profile`; assert exactly one "Current session" pill, no uncaught console errors

  Playwright totals: 9 passing / 0 failing (two consecutive runs, no flakes)

  ---
  Wave 1 — shipped (pre-demo hardening, 2026-04-20 PM)

  - W1.1 Message hover actions: Edit / Delete / Reply + reply-preview quoted block (`MessageBubble`, `MessageInput`, `MessageThread`); edit in-place textarea; inline delete confirm
  - W1.2 Browser tab title unread count: `useTotalUnread` hook + `document.title = "(N) Chat"` effect, capped at `99+`
  - W1.4 Ban-kick Playwright spec: A bans B mid-DM → B auto-navigates to `/chat`
  - W1.5 README rewrite: quick-start for Docker + local, SECRET_KEY caveat, test commands, specs pointer

  Verified paths during W1.4: `POST /api/bans`, `PATCH /api/friends/:id/accept` (corrected from initial guesses)

  W1.3 deferred-style smoke (non-destructive): `docker compose up -d --build --force-recreate backend frontend` with volumes preserved — new images boot cleanly, alembic runs idempotently (a1b2c3d4e5f6 → head), 10/10 Playwright green.

  ---
  Final verification (2026-04-20, end of Wave 1)

  - Backend: 174 pytest (172 Wave A/B + 2 `is_current`, 1 pre-existing skip)
  - Frontend: 103 vitest / 0 failing · 0 TypeScript errors · clean Vite build
  - E2E: 10 Playwright specs passing (5 pre-existing + 4 from Wave C + 1 ban-kick); verified twice on parallel-worker runs, no flakes
  - Schema: migration auto-applies on boot (idempotent); uploads persist across container recreate
  - Architect Wave-1 plan items 1/2/4/5 complete; item 3 delivered via non-destructive alternative
  - No open 🔴 blockers for 2026-04-21 demo

  ---
  Deferred (post-demo)

  - 🟡 `/api/unread` N+1 query — fold to one grouped SQL (currently ~40 round-trips for a user in 20 rooms; fine at demo scale)
  - 🟡 `unread.increment` WS emits to members actively viewing the room (stale counter until `mark-read`); suppress via active-room tracking in `presence_manager`
  - 🟢 Collapse `SidebarRight` on non-chat routes
  - 🟢 Kick users from active DMs when the peer bans them (currently only `qc.invalidateQueries` fires)

  Demo: 2026-04-21.

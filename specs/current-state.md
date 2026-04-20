  Current state: TASK-02 through TASK-11 + TASK-14 + Wave 1 complete ✅ · Demo-ready

  184 backend pytest · 116 frontend vitest · 11 Playwright e2e specs · 0 TS errors

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
  Wave 2A — shipped (TASK-11 WebSocket protocol gaps · commit `087779a`)

  11.1 — `session.revoked` emit + frontend handler
  - `sessions.py::revoke_session` is now `async`; emits `{"type":"session.revoked","session_id":…}` via `presence_manager.send_to_user(current_user.id, …)` after commit. Fans out to all tabs of the revoking user.
  - `frontend/src/lib/sessionRevoked.ts`: pure helper that probes `/api/auth/me`. 401 → clears `["me"]` cache + `navigate("/login", {replace:true})`; 200 → invalidates `["sessions"]`.
  - `App.tsx::handleMessage` dispatches `session.revoked` events to the helper.

  11.2 — Idle-connection reap after 90s
  - `ws.py`: module constant `IDLE_TIMEOUT = 90`; `asyncio.wait_for(websocket.receive_json(), timeout=IDLE_TIMEOUT)` inside the recv loop. `except asyncio.TimeoutError` → `websocket.close(code=4000)`. Any recv (ping, heartbeat) resets the window.

  11.3 — Fixed two silent wire-format bugs uncovered by the audit
  - `friends.py:124`: event renamed `friend.request_accepted` → `friend.accepted` (frontend handler had been matching the new name and never firing).
  - `user_bans.py:47-53`: `user.banned` payload now carries both `banner_id` AND `banned_id` (was missing the latter).

  11.4 — New tests (+7 pytest, +2 vitest)
  - `test_sessions.py`: happy-path emit, multi-tab fanout, owner-only target (spy on `send_to_user`)
  - `test_ws_idle.py`: close after idle; ping resets the timer
  - `test_friends.py`: `friend.accepted` rename regression guard
  - `test_user_bans.py`: payload contains both ids
  - `__tests__/sessionRevoked.test.ts`: 401 kick + 200 refresh

  ---
  Wave 2B — shipped (TASK-10 Admin & Moderation UI · commit `967bffb`)

  10.1 — Backend
  - `DELETE /api/rooms/{room_id}/invitations/{invitation_id}` — admin-only cancel, 404 when missing or already accepted. No WS broadcast; frontend refetches invitation list on mutate.
  - Existing moderation routes (grant/remove admin, ban/unban, invite, update, delete) already in place from TASK-05; only the cancel endpoint was missing.

  10.2 — Frontend (shadcn init + component tree)
  - `npx shadcn@latest init` + `add tabs dialog dropdown-menu button input label`; `@/*` alias wired into `vite.config.ts`.
  - New `hooks/useAdmin.ts`: `useRoomBans`, `useRoomInvitations` + 8 mutations (`useGrantAdmin`, `useRemoveAdmin`, `useBanMember`, `useUnbanMember`, `useInviteUser`, `useCancelInvitation`, `useUpdateRoom`, `useDeleteRoom`).
  - New `components/ManageRoomModal.tsx` with 4 tabs (Members, Banned, Invitations, Settings); uses `@base-ui/react/tabs` via shadcn `ui/tabs`.
  - Role gating derived once from `useRoomMembers` + `useCurrentUser`; passed to tabs as `myRole` prop. Owner = all; admin = ban non-admins + invite; member = no Manage button at all.
  - New `components/ConfirmModal.tsx` (reusable); Settings tab has type-to-confirm delete flow inline.
  - `SidebarRight.tsx`: role-gated "Manage" button renders only for owner/admin.

  10.3 — Tests (+3 pytest, +11 vitest, +1 Playwright)
  - `test_rooms.py`: cancel-invitation happy path, 403 non-admin, 404 missing/accepted
  - `__tests__/useAdmin.test.ts`: all 10 hooks covered (query + mutation + cache invalidation)
  - `e2e/admin.spec.ts`: owner creates room, member joins, owner opens Manage → bans member → member disappears from Members tab → appears in Banned tab → unban → list empty

  ---
  Demo-script confidence (5-step happy path)

  1. Register + login → `e2e/auth.spec.ts` (×3)
  2. Create + join room → `e2e/rooms.spec.ts` (×2)
  3. Send message + attachment → `e2e/attachments.spec.ts` (text file asserted; image preview falls through to the same text-link rendering)
  4. Unread badge → `e2e/unread.spec.ts` (two browser contexts, appear + clear)
  5. DM open + ban-kick + admin moderation → `e2e/dm.spec.ts` + `e2e/ban-kick.spec.ts` + `e2e/admin.spec.ts`

  Smoke coverage: `e2e/smoke.spec.ts` walks `/chat`, `/rooms`, `/sessions`, `/profile` — no uncaught console errors, exactly one "Current session" pill.

  ---
  Final verification (2026-04-20, post-Wave-2)

  - Backend: 184 pytest passing (1 pre-existing skip)
  - Frontend: 116 vitest passing · 0 TypeScript errors · clean Vite build (shadcn deps resolve via `@/*` alias)
  - E2E: 11 Playwright specs passing (including new `admin.spec.ts`)
  - Migration auto-applies on container boot (idempotent); uploads persist across `force-recreate`
  - Frontend image rebuilt post-shadcn-install (adds `@base-ui/react`, `class-variance-authority`, `tw-animate-css`, `@fontsource-variable/geist`)
  - No open 🔴 blockers

  Branch: `greenbase` · last commits: `967bffb` (TASK-10), `087779a` (TASK-11)

  ---
  Deferred (post-demo)

  - 🟡 Inline image preview for attachments — `MessageBubble.tsx` currently renders every attachment as a text link; distinguish image MIME types and render `<img>` inline (≤20 min)
  - 🟡 Reply round-trip Playwright coverage — UI and backend wiring verified manually; no e2e asserts the reply-preview bubble renders after round-trip (≤20 min)
  - 🟡 Member context menu (⋮) in `SidebarRight` — spec 10 wireframe called for right-click/⋮ on member rows with Send message / Make admin / Ban / Send friend request. Current shipping uses the Members tab in Manage Room modal for admin actions; a context menu on sidebar rows would be faster but adds surface area. Skipped for demo scope
  - 🟡 `room.invitation_cancelled` WS event — currently admin cancel is local-refetch only; invitee's "pending invitation" banner stays live until they refresh or click-through. Cosmetic at demo scale
  - 🟡 `message.new` cache invalidation is per-room refetch — replace with surgical cache updates for perf under load
  - 🟢 Sidebar accordion collapse on active room (`specs/09-frontend-layout.md`)
  - ⬜ Jabber / XMPP federation (`specs/13-jabber.md`) — advanced scope, not targeted for this hackathon

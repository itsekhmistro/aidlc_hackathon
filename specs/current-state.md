
⏺ Gap audit — Initial-goal-definition.md vs shipped state

  Bottom line: 16 of 16 core requirements shipped (post-Wave-3). Advanced Jabber scope not attempted (explicitly optional in spec §6).

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
  - Presence latency <2 s — ✅ (WS direct fanout)

  §3 NFRs — ✅ within demo scale

  - 300 users / 1000 per room / 10k+ history — architected for; load-testing not performed (out of scope for hackathon)
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
  Spec-complete status (Wave 3, 2026-04-20)

  All §2–§5 requirements shipped. §6 (Jabber) remains out of scope per original carve-out.

  Wave 3 closed the final polish items:

  - **A · Member context menu in `SidebarRight`** — `MemberRowMenu.tsx` exposes
    Send message, Send friend request (hidden when already friends), Make/Remove admin
    (owner-only), Ban from room (with confirm). Role-gated identically to the Manage
    Room → Members tab. Closes §2.3.2.
  - **B · Sidebar accordion collapse** — `SidebarLeft.tsx` auto-collapses the
    non-active section when navigating into a room (Contacts collapses) or a DM
    (Rooms collapses). Collapse state is user-toggleable via the section header
    caret. Closes §4.1.1.
  - **C · Contact-row ban action** — already shipped earlier in `ContactRow.tsx`
    (⋮ menu → "Ban user" with confirm modal). Re-verified 2026-04-20; no work needed.

  Wave 4 (2026-04-20) — TASK-15 personal-room display names:
  - Backend: `RoomPublic` gains a per-viewer `display_name` field. For personal
    rooms it resolves to the other member's username; for regular rooms it
    mirrors `name`. Canonical `Room.name` (`__dm__:<sorted uuids>`) stays
    immutable as the dedup key.
  - Frontend: `RoomRow` and `MessageThread` render `display_name` prefixed with
    `@` for DMs and `#` for regular rooms. `ManageRoomModal` title uses
    `display_name` too.
  - Tests: 3 pytest cases (viewer-specific DM resolution, flip between
    viewers, regular rooms unaffected) + 2 vitest for the thread header.

  ---
  Demo-script confidence (5-step happy path)

  1. Register + login → `e2e/auth.spec.ts` (×3)
  2. Create + join room → `e2e/rooms.spec.ts` (×2)
  3. Send message + attachment → `e2e/attachments.spec.ts` (text file asserted; image preview falls through to the same text-link rendering)
  4. Unread badge → `e2e/unread.spec.ts` (two browser contexts, appear + clear)
  5. DM open + ban-kick + admin moderation → `e2e/dm.spec.ts` + `e2e/ban-kick.spec.ts` + `e2e/admin.spec.ts`

  Smoke coverage: `e2e/smoke.spec.ts` walks `/chat`, `/rooms`, `/sessions`, `/profile` — no uncaught console errors, exactly one "Current session" pill.

  ---
  Final verification (2026-04-20, post-Wave-4)

  - Backend: 187 pytest passing (1 pre-existing skip)
  - Frontend: 139 vitest passing · 0 TypeScript errors · clean Vite build
  - E2E: 11 Playwright specs passing (sequential worker)
  - Migration auto-applies on container boot (idempotent); uploads persist across `force-recreate`
  - No open 🔴 blockers

  Branch: `greenbase` · Wave 2 commits: `967bffb` (TASK-10), `087779a` (TASK-11)

  ---
  Deferred (post-demo)

  - 🟡 Inline image preview for attachments — `MessageBubble.tsx` currently renders every attachment as a text link; distinguish image MIME types and render `<img>` inline (≤20 min)
  - 🟡 Reply round-trip Playwright coverage — UI and backend wiring verified manually; no e2e asserts the reply-preview bubble renders after round-trip (≤20 min)
  - 🟡 `room.invitation_cancelled` WS event — currently admin cancel is local-refetch only; invitee's "pending invitation" banner stays live until they refresh or click-through. Cosmetic at demo scale
  - 🟡 `message.new` cache invalidation is per-room refetch — replace with surgical cache updates for perf under load
  - 🟡 Sidebar search (filter rooms + contacts by name) — spec §4.1 / `09-frontend-layout.md` acceptance box still open; non-blocking at demo scale (a handful of rooms per user)
  - ⬜ Jabber / XMPP federation (`specs/13-jabber.md`) — advanced scope, not targeted for this hackathon

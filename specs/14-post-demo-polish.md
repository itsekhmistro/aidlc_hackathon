# TASK-14 — Post-demo polish (deferred items from Wave C)

Status: **completed** (2026-04-20) — all four items shipped on `greenbase` (commit `9fb8947`). See `specs/current-state.md` for the roll-up.

After Wave C shipped demo-readiness, four gaps were recorded as non-blocking. This spec tracks their implementation.

## Items

### 1. 🟡 N+1 on `/api/unread` — single grouped query

**Problem:** `get_unread_counts` loops over every room the user belongs to and runs 1–2 queries per room (~40 round-trips for a user in 20 rooms).

**Fix:** rewrite as one SQL statement:

```sql
SELECT rm.room_id, COUNT(m.id)
FROM room_member rm
LEFT JOIN read_receipt rr
  ON rr.room_id = rm.room_id AND rr.user_id = rm.user_id
LEFT JOIN message last_read
  ON last_read.id = rr.last_read_message_id
LEFT JOIN message m
  ON m.room_id = rm.room_id
  AND m.deleted_at IS NULL
  AND last_read.created_at IS NOT NULL
  AND m.created_at > last_read.created_at
WHERE rm.user_id = :current_user
GROUP BY rm.room_id;
```

Behavioral invariants preserved (covered by existing `tests/test_unread.py`):
- No room membership → empty counts
- Room with no receipt → 0 (not total messages)
- Receipt → count messages after `last_read.created_at` with `deleted_at IS NULL`

### 2. 🟡 Suppress `unread.increment` for active-room viewers

**Problem:** Backend emits `unread.increment` to every non-author member. If a user is actively viewing the room, the badge counter ticks up until they `mark-read` (which only fires on room-mount, not on new message arrival).

**Fix (client-side, zero protocol changes):** In `App.tsx`'s WS handler, before calling `incrementUnread`, check if `window.location.pathname === "/chat/rooms/${event.room_id}"`. If yes, fire `mark-read` to keep server-side receipt fresh, skip the increment. Otherwise, increment as today.

Chosen over server-side tab tracking because:
- No new WS events or shared state
- Already-existing behavior on room mount (`RoomChatPage` marks-read) handles the first-mount case; this covers subsequent in-room arrivals
- Demo-scale: negligible wasted traffic

### 3. 🟢 Collapse `SidebarRight` on non-chat routes

**Status:** already satisfied by Wave B. `components/AppShell.tsx` renders `SidebarRight` only when `activeRoomId` is non-null (derived from `useMatch` on `/chat/rooms/:roomId` and `/chat/dm/:userId`). On `/rooms`, `/sessions`, `/profile`, the sidebar is hidden and `<main className="flex-1">` expands. No code change needed. Documenting as resolved.

### 4. 🟢 Kick banned peers from active DMs

**Problem:** When user B bans user A, A keeps viewing the DM UI. Friendship query invalidates but the page doesn't navigate away.

**Fix (client-side):** In `App.tsx`'s `user.banned` handler, inspect current pathname:
- `/chat/dm/:userId` where `userId === banner_id` → `navigate("/chat", { replace: true })`
- `/chat/rooms/:roomId`: look up cached members via `qc.getQueryData(["rooms", roomId, "members"])`; if `banner_id` is a member, navigate away

For the room case, if members aren't cached we skip — the ban still invalidates friendship state and the next interaction will 403. Acceptable for demo.

## Verification

- Backend: existing `tests/test_unread.py` (11 cases) must pass unchanged
- Frontend: existing Vitest suite (98) must pass; Playwright suite (9) must pass
- No e2e for items 2 and 4 in this pass — pure runtime behaviors that don't break existing flows

## Out of scope

- Server-side active-room tracking via WS `room.active` event — deferred further
- Multi-member non-DM room redirects on ban — only personal rooms are targeted
- Clearing in-flight WS messages for kicked users

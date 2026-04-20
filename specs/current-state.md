# Current State — as of 2026-04-20

Last reviewed by Lead + Architect after commit `6ad6a38`.

---

## Phase 1 Status

| Task | Backend | Frontend | Overall |
|---|---|---|---|
| TASK-02 Auth | ✅ Complete | ✅ Complete | ✅ Done |
| TASK-03 Presence | ✅ Complete | ✅ Complete | ✅ Done |
| TASK-04 Contacts | ❌ Stubs (501) | ✅ Complete | 🟡 Backend only |
| TASK-05 Rooms | ✅ Complete | ❌ Not started | 🟡 Backend only |

---

## What is done

### TASK-02 Authentication
- **Backend**: All 9 routes + `GET /api/auth/me`. HttpOnly cookie, SHA-256 session tokens, 30-day persistent sessions, full cascade delete, password reset flow.
- **Frontend**: `useAuth.ts` (cookie-based, no localStorage). `LoginPage` (RHF+Zod, persistent checkbox). `RegisterPage`, `ForgotPasswordPage`, `ResetPasswordPage` with inline server errors.
- **Tests**: 30 backend tests (29 pass, 1 skipped — known email uniqueness design issue). 13 frontend unit tests.

### TASK-03 Presence
- **Backend**: `PresenceManager` — multi-tab keyed by `(user_id, tab_id)`, 3-state logic, broadcasts to room-mates + friends. `POST /api/presence/bulk` with live+DB fallback. WS at `/ws?tab_id=<uuid>`.
- **Frontend**: `useActivityTracker.ts` (60s idle → `afk` heartbeat), `presenceStore.ts` (useSyncExternalStore), `PresenceDot.tsx` (green/yellow/gray). WS URL uses `window.location.host` through Vite proxy.
- **Tests**: 10 backend tests. 9 frontend unit tests.

### TASK-04 Contacts (frontend)
- **Frontend**: `ChatLayout.tsx` with sidebar: contacts list with `PresenceDot`, context menu (send message / remove friend / ban), incoming requests panel (accept/decline), `AddFriendModal` (username + optional message), ban confirmation modal.
- **Hooks**: `useFriends.ts` — `useFriends`, `useFriendRequests`, `useSendFriendRequest`, `useAcceptFriendRequest`, `useRemoveFriend`, `useBanUser` all wired to backend (currently graceful 501 states).

### TASK-05 Rooms (backend)
- **Backend**: Full CRUD — list, create, get, update, delete, join, leave, members, admin grant/revoke, room bans, invitations. `is_personal` flag on `Room` model. All 93 backend tests passing.

### Infrastructure fix
- `vite.config.ts` proxy target reads `BACKEND_URL` env var (default `localhost:8000`).
- `docker-compose.override.yml` injects `BACKEND_URL=http://backend:8000` into frontend container. **Requires rebuild: `docker compose up --build frontend`.**

---

## What is stubbed (all return HTTP 501)

### TASK-04 Backend
| File | Endpoints |
|---|---|
| `backend/app/api/routes/friends.py` | GET /api/friends, GET /api/friends/requests/incoming, POST /api/friends/request, PATCH /api/friends/{id}/accept, DELETE /api/friends/{id} |
| `backend/app/api/routes/user_bans.py` | GET /api/user-bans, POST /api/user-bans/{user_id}, DELETE /api/user-bans/{user_id} |
| `backend/app/api/routes/personal.py` | GET /api/personal-rooms/{user_id} |

### TASK-06 Backend
| File | Endpoints |
|---|---|
| `backend/app/api/routes/messages.py` | GET /api/messages/{room_id}, POST /api/messages/{room_id}, PATCH /api/messages/{room_id}/{msg_id}, DELETE /api/messages/{room_id}/{msg_id} |

### Also stubbed (Phase 2+)
- `attachments.py` — 3 endpoints (TASK-07)
- `unread.py` — 2 endpoints (TASK-08)

---

## Known design issues (non-blocking)

1. **Email reuse after soft-delete**: `User.email` has a DB-level `UNIQUE` constraint. After account deletion, the email cannot be re-registered. Fix: mangle email on `DELETE /api/auth/account` → `user.email = f"__deleted__{uid}@deleted"`. Tracked as a skipped test.
2. **Reset token in `UserSession`**: Password reset tokens are stored as `UserSession` rows with `user_agent="password_reset"`. A `revoke_all_sessions` operation would accidentally invalidate pending resets. Fix: separate `PasswordResetToken` table. Deferred post-hackathon.

---

## Next steps — implementation plan

### Wave 1 (parallel — unblock everything)

**Backend A: TASK-04 friends + user_bans + shared helpers**

1. Create `backend/app/core/social.py` with:
   ```python
   def friendship_between(session, a: UUID, b: UUID) -> Friendship | None
   def ban_between(session, a: UUID, b: UUID) -> bool
   ```
2. Implement `friends.py` — all 5 routes. Key guards:
   - `POST /api/friends/request`: check ban + check dup friendship, broadcast `friend.request_received` to addressee
   - `PATCH .../accept`: only addressee can accept, broadcast `friend.accepted` to requester
   - `DELETE .../remove`: either party, broadcast `friend.removed` to both
   - All WS-broadcasting routes must be `async def`
3. Add `UserBanPublic` to `schemas/social.py`, implement `user_bans.py`:
   - `POST /api/user-bans/{user_id}`: create ban + delete friendship + broadcast `user.banned` to both
   - No WS broadcast needed for unban
4. Add `GET /api/rooms/mine` to `rooms.py` (registered before `/{room_id}` to avoid path conflict):
   ```python
   room_ids = session.exec(select(RoomMember.room_id).where(RoomMember.user_id == current_user.id)).all()
   rooms where id in room_ids and is_personal == False
   ```

**Backend B: TASK-06 messages**

1. Extract `_to_room_public` helper into `backend/app/core/room_utils.py` (avoids circular import from `personal.py`)
2. Implement `messages.py` — all 4 routes:
   - Cursor pagination: keyset `(created_at, id)` — use `ORDER BY created_at DESC, id DESC LIMIT n+1`
   - Include soft-deleted messages (`deleted=True, content=""`) — do NOT filter out
   - All WS-broadcasting routes (`send_message`, `edit_message`, `delete_message`) must be `async def`
   - Broadcast `message.new/edited/deleted` to all `RoomMember` user_ids for the room

### Wave 2 (after Wave 1 friends are done)

**Backend: personal.py**
- Use `friendship_between` from `app/core/social.py` and `ban_between`
- Use `_to_room_public` from `app/core/room_utils.py`
- Canonical room name: `__dm__` + `":".join(sorted([str(uid1), str(uid2)]))` (prefix prevents collision with user-created room names)
- Guard: must be friends, neither banned the other

**Frontend A: TASK-05 rooms UI**
- `useRooms.ts`: `useMyRooms` (GET /api/rooms/mine), `usePublicRooms`, `useCreateRoom`, `useJoinRoom`, `useLeaveRoom`
- `ChatLayout.tsx`: add "Rooms" section to sidebar below contacts
- `CreateRoomModal.tsx`: name + visibility select
- `RoomBrowserModal.tsx`: searchable public rooms list with join button

### Wave 3 (after Wave 1 messages are done)

**Frontend B: TASK-06 messaging UI**
- `useMessages.ts`: `useInfiniteQuery` keyed by `["messages", roomId]`; WS events update cache directly (no re-fetch)
- `MessageThread.tsx`: `RoomHeader` + `MessageList` (infinite scroll with Intersection Observer at top) + `MessageInput`
- `MessageBubble.tsx`: own/other styling, deleted placeholder, edited badge, reply preview, context menu
- Wire new WS event types in `App.tsx`: `message.new/edited/deleted`, `friend.request_received/accepted/removed`, `user.banned`
- "Send message" in `ContactRow` → call `GET /api/personal-rooms/{userId}` → set active room

### Wave 4 (integration)
- Unread counts (TASK-08 backend stubs: `GET /api/unread`, `DELETE /api/unread/{room_id}`)
- Frontend unread badges on sidebar room rows

---

## Architect risks to watch

| Risk | Severity | Mitigation |
|---|---|---|
| No `GET /api/rooms/mine` endpoint | **Blocker for TASK-05 frontend** | Add to `rooms.py` in Wave 1 — before `/{room_id}` path |
| Circular import: personal.py ↔ rooms.py ↔ friends.py | **High** | Extract helpers to `app/core/social.py` + `app/core/room_utils.py` |
| WS broadcasts from sync `def` routes | **High** | All broadcasting routes must be `async def` |
| Cursor pagination correctness (equal timestamps) | **Medium** | Composite keyset `(created_at, id)` handles ties; add explicit test |
| Personal room name collision with user-created rooms | **Medium** | Prefix with `__dm__` or validate in `POST /api/rooms` |

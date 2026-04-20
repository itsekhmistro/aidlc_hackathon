# Current State & Implementation Plan

**Last updated:** 2026-04-20  
**Author:** Architect Agent  
**Branch:** `greenbase`

---

## Implementation Status Summary

| Task | Status | Test count |
|------|--------|------------|
| TASK-02 Auth | Done | covered |
| TASK-03 Presence | Done | covered |
| TASK-04 Contacts | Done | covered |
| TASK-05 Rooms | Done | covered |
| TASK-06 Messages | Done | covered |
| TASK-07 Attachments | Stub (501) | 0 |
| TASK-08 Notifications | Stub (501) | 0 |
| TASK-09 Frontend Layout | Partial (ChatLayout exists) | 0 |

Total: 141 backend tests (1 skipped), 54 frontend unit tests.

---

## 1. Gap Analysis: TASK-04 / TASK-05 / TASK-06

### TASK-04 Contacts (friends.py, user_bans.py)

| Gap | Rating | Notes |
|-----|--------|-------|
| "Send message" button in ContactRow does nothing — no navigation | 🔴 Blocker | Needed for TASK-09 DM routing (`/chat/dm/:userId`) — must wire to react-router `useNavigate` |
| No DM-room auto-creation when friend is accepted | 🟡 Important | `personal.py` handles on-demand creation, but it's not triggered automatically on acceptance. Users must explicitly open a DM to create the room. Doesn't block 07-09 |
| WS `user.banned` payload has IDs only, no username for toast | 🟢 Nice-to-have | Non-blocking; toast can use IDs |

### TASK-05 Rooms

| Gap | Rating | Notes |
|-----|--------|-------|
| `WsMessageNew` broadcast shape mismatch: backend sends `{"type": "message.new", "message": {...}}` — no top-level `room_id`. TS type `WsMessageNew` expects `room_id` at top level. `App.tsx` reads `event.room_id` which is `undefined` → wrong query key invalidated | 🔴 Blocker | Fix: add `"room_id": str(room_id)` to the broadcast dict in `messages.py` |
| `_cascade_delete_room` removes Attachment DB rows but the on-disk cleanup (`shutil.rmtree`) is at the room level and is correct. No disk leak. | — | No gap |
| Room catalog has no cursor pagination UI in frontend | 🟢 Nice-to-have | — |

### TASK-06 Messages

| Gap | Rating | Notes |
|-----|--------|-------|
| No `unread.increment` WS event emitted in `send_message` | 🔴 Blocker | TASK-08 backend depends on this. Must emit to all room members except the author |
| `WsMessageEdited` backend shape: backend sends `{"type": "message.edited", "message": <MessagePublic>}`. TS type expects separate fields `message_id`, `content`, `edited_at`. App.tsx only invalidates queries (doesn't read sub-fields) so not currently broken at runtime, but the union type is wrong | 🟡 Important | Fix both sides for correctness |
| `AttachmentPublic` has no explicit download URL field — frontend uses `/api/attachments/{id}` which it can construct from the `id` field | 🟢 Nice-to-have | — |

---

## 2. Implementation Plan: TASK-07 Attachments

### Backend

#### Models — already complete

`Attachment` in `backend/app/models/message.py` has all required fields. `AttachmentPublic` schema is complete. `settings.UPLOAD_DIR`, `MAX_FILE_SIZE_BYTES`, `MAX_IMAGE_SIZE_BYTES` already present.

**One migration required:** `Attachment.message_id` is currently `NOT NULL`. Uploading before message creation requires making it nullable. See sequencing fix below.

#### Routes to implement in `backend/app/api/routes/attachments.py`

**POST `/api/attachments/{room_id}`** — Upload

```
Request:  multipart/form-data { file: UploadFile, comment: str | None }
Response: AttachmentPublic (201)
```

Logic:
1. Verify membership via `_get_membership(session, room_id, user_id)`
2. Determine size limit: if `file.content_type` starts with `image/` → `MAX_IMAGE_SIZE_BYTES` (3 MB), else `MAX_FILE_SIZE_BYTES` (20 MB)
3. Generate `attachment_id = uuid4()` upfront
4. Stream file in chunks, accumulate byte count → raise `HTTPException(413)` if limit exceeded
5. Write to `UPLOAD_DIR/{room_id}/{attachment_id}/{original_filename}` using `os.makedirs(exist_ok=True)`
6. `INSERT Attachment` with `message_id=None`, `stored_path`, `uploaded_by_id`
7. Return `AttachmentPublic`

**GET `/api/attachments/{attachment_id}`** — Download

```
Response: FileResponse (membership re-verified on each request)
```

Logic:
1. Fetch `Attachment` or 404
2. Fetch linked `Message` (may be None if `message_id` is null) → get `room_id`; if no message, fall back to stored room from upload context (store `room_id` on Attachment — see schema fix below)
3. Verify membership → 403 if not member
4. Return `FileResponse(path, filename=original_filename, media_type=mime_type)`

**Note:** To avoid needing to resolve room_id through the Message, add `room_id` directly to `Attachment` model (migration). This also simplifies the download access check.

**DELETE `/api/attachments/{attachment_id}`** — Delete

```
Response: 204
```

Logic:
1. Fetch `Attachment` or 404
2. Check: `att.uploaded_by_id == current_user.id` OR caller is admin/owner of the attachment's room
3. `os.unlink(att.stored_path)` (ignore `FileNotFoundError`)
4. `session.delete(att)` + commit

#### Schema fix: add `room_id` to Attachment

Add `room_id: UUID = Field(foreign_key="room.id", index=True)` to `Attachment`. Required for efficient access-check at download time. Add to migration.

Also update `AttachmentPublic` — no change needed (room_id is internal).

#### MessageCreate update

Add `attachment_ids: list[UUID] = []` to `MessageCreate`. In `send_message`, after inserting the message, run:

```python
for att_id in msg.attachment_ids:
    att = session.get(Attachment, att_id)
    if att and att.uploaded_by_id == current_user.id and att.message_id is None:
        att.message_id = message.id
        session.add(att)
```

#### WS events

No new WS events. The existing `message.new` broadcast already carries `attachments: []` in `MessagePublic`. Once the message is created with attachment IDs linked, the broadcast includes them.

#### Storage path

```
/uploads/{room_id}/{attachment_id}/{original_filename}
```

#### Cleanup

- Room deleted: `shutil.rmtree(UPLOAD_DIR/{room_id})` already in `rooms.py` — covers all attachments
- Single delete: `os.unlink(stored_path)` in delete route

---

### Frontend

#### New hook: `frontend/src/hooks/usePasteUpload.ts`

```typescript
export function usePasteUpload(onFiles: (files: File[]) => void): void {
  useEffect(() => {
    const handler = (e: ClipboardEvent) => {
      const files = e.clipboardData?.files;
      if (files?.length) { e.preventDefault(); onFiles(Array.from(files)); }
    };
    document.addEventListener("paste", handler);
    return () => document.removeEventListener("paste", handler);
  }, [onFiles]);
}
```

#### Upload UI in `MessageInput`

State: `pendingFiles: Array<{ file: File; comment: string; progress: number; attachmentId: string | null; error: string | null }>`

Flow:
1. Hidden `<input type="file" multiple>` triggered by paperclip icon button
2. Files added to `pendingFiles` state; show preview row per file: filename + size + comment input + remove button + progress bar
3. On send click:
   a. For each pending file without `attachmentId`: POST multipart to `/api/attachments/{room_id}` via `XMLHttpRequest` (for `onprogress`); on success, set `attachmentId`
   b. Collect all `attachmentId` values
   c. POST `{ content, reply_to_id, attachment_ids }` to `/api/rooms/{room_id}/messages`
   d. Clear `pendingFiles`

Upload via XHR (not fetch) to get progress events:
```typescript
const xhr = new XMLHttpRequest();
xhr.upload.onprogress = (e) => { if (e.lengthComputable) setProgress(e.loaded / e.total * 100); };
xhr.open("POST", `/api/attachments/${roomId}`);
// formData with file + comment
```

Error handling: show inline error per file for 413 (too large).

#### Attachment display in message

In `MessageThread` / message bubble, for each `att` in `message.attachments`:
- If `att.mime_type.startsWith("image/")`: `<img src="/api/attachments/{att.id}" className="max-w-[200px]" />` + lightbox on click
- Otherwise: download link `<a href="/api/attachments/{att.id}" download={att.original_filename}>` with file icon, filename, size
- Show `att.comment` if non-null below the file row
- On 403 response (user lost room access): show "No longer accessible" placeholder

---

## 3. Implementation Plan: TASK-08 Unread Notifications

### Backend

#### ReadReceipt model — already exists

Fields: `room_id` (PK), `user_id` (PK), `last_read_message_id`, `updated_at`. No changes needed.

#### Routes in `backend/app/api/routes/unread.py` — fully stub, needs implementation

**GET `/api/unread`** → `UnreadCountsPublic { counts: dict[str, int] }`

```python
from sqlmodel import func, select
from app.models.message import Message, ReadReceipt
from app.models.room import RoomMember

def get_unread_counts(current_user, session):
    room_ids = session.exec(
        select(RoomMember.room_id).where(RoomMember.user_id == current_user.id)
    ).all()

    counts = {}
    for room_id in room_ids:
        receipt = session.get(ReadReceipt, (room_id, current_user.id))
        if receipt is None:
            # No receipt: all non-own non-deleted messages are unread
            count = session.exec(
                select(func.count()).select_from(Message).where(
                    Message.room_id == room_id,
                    Message.author_id != current_user.id,
                    Message.deleted_at.is_(None),
                )
            ).one()
        else:
            anchor = session.get(Message, receipt.last_read_message_id)
            if anchor is None:
                count = 0
            else:
                count = session.exec(
                    select(func.count()).select_from(Message).where(
                        Message.room_id == room_id,
                        Message.created_at > anchor.created_at,
                        Message.author_id != current_user.id,
                        Message.deleted_at.is_(None),
                    )
                ).one()
        if count > 0:
            counts[str(room_id)] = count

    return UnreadCountsPublic(counts=counts)
```

**POST `/api/unread/{room_id}/mark-read`** → 204

```python
async def mark_room_read(room_id, current_user, session):
    _require_membership(session, room_id, current_user.id)

    latest = session.exec(
        select(Message)
        .where(Message.room_id == room_id, Message.deleted_at.is_(None))
        .order_by(Message.created_at.desc())
        .limit(1)
    ).first()

    if not latest:
        return  # no messages

    receipt = session.get(ReadReceipt, (room_id, current_user.id))
    if receipt:
        receipt.last_read_message_id = latest.id
        receipt.updated_at = datetime.now(timezone.utc)
    else:
        receipt = ReadReceipt(room_id=room_id, user_id=current_user.id, last_read_message_id=latest.id)
    session.add(receipt)
    session.commit()

    # Clear badge on ALL tabs of this user (multi-tab sync)
    await presence_manager.send_to_user(
        current_user.id,
        {"type": "unread.cleared", "room_id": str(room_id)},
    )
```

#### WS: `unread.increment` in `messages.py`

In `send_message`, after `_broadcast_room_event` for `message.new`:

```python
for uid in _room_member_ids(session, room_id):
    if uid != current_user.id:
        await presence_manager.send_to_user(
            uid, {"type": "unread.increment", "room_id": str(room_id), "count": 1}
        )
```

Sending `count: 1` as a delta. Frontend accumulates.

---

### Frontend

#### New: `frontend/src/lib/unreadStore.ts`

Mirror `presenceStore.ts` pattern (`useSyncExternalStore`):

```typescript
import { useSyncExternalStore } from "react";

const store = new Map<string, number>(); // roomId → count
const listeners = new Set<() => void>();
function notify() { listeners.forEach(l => l()); }

export function initUnread(counts: Record<string, number>): void {
  store.clear();
  Object.entries(counts).forEach(([k, v]) => store.set(k, v));
  notify();
}
export function incrementUnread(roomId: string, delta = 1): void {
  store.set(roomId, (store.get(roomId) ?? 0) + delta);
  notify();
}
export function clearUnread(roomId: string): void {
  store.delete(roomId);
  notify();
}
function subscribe(l: () => void) { listeners.add(l); return () => listeners.delete(l); }
function getSnapshot() { return store; }

export function useUnreadCount(roomId: string): number {
  const map = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  return map.get(roomId) ?? 0;
}
export function useTotalUnread(): number {
  const map = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  let t = 0; map.forEach(v => { t += v; }); return t;
}
```

#### `App.tsx` additions

1. On auth confirmation (`isAuthenticated`): fetch `GET /api/unread` → `initUnread(data.counts)`
2. WS handlers:
   ```typescript
   } else if (event.type === "unread.increment") {
     incrementUnread(event.room_id, event.count);
   } else if (event.type === "unread.cleared") {
     clearUnread(event.room_id);
   }
   ```
3. Browser tab title effect:
   ```typescript
   const total = useTotalUnread();
   useEffect(() => { document.title = total > 0 ? `(${total}) ChatApp` : "ChatApp"; }, [total]);
   ```

#### Mark-read trigger

In room selection handler (ChatLayout or new routing):
```typescript
// Optimistic local clear + debounced API call
clearUnread(roomId);
debouncedMarkRead(roomId); // 300ms debounce wrapping api.post(...)
```

#### Badge in RoomRow

```tsx
const count = useUnreadCount(room.id);
{count > 0 && (
  <span className="ml-auto bg-red-500 text-white text-xs rounded-full px-1.5 min-w-[1.25rem] text-center">
    {count > 99 ? "99+" : count}
  </span>
)}
```

---

## 4. Implementation Plan: TASK-09 Frontend Layout

### Prerequisite fixes required first

| Fix | Location | Impact |
|-----|----------|--------|
| Add `"room_id": str(room_id)` to `message.new` broadcast | `messages.py` send_message | Fixes broken query invalidation in App.tsx |
| Align `WsMessageEdited` backend shape with TS type (send `message_id`/`content`/`edited_at` at top level, not nested `message` object) | `messages.py` + `types.ts` | Correctness |
| Wire "Send message" → `useNavigate("/chat/dm/:userId")` | `ChatLayout.tsx` ContactRow | Enables DM routing |

### New components

All placed in `frontend/src/components/` unless noted as pages.

#### `AppShell.tsx`

```tsx
export default function AppShell() {
  const params = useParams();
  const hasActiveRoom = !!params.roomId || !!params.userId;
  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <TopNav />
      <div className="flex flex-1 overflow-hidden">
        <SidebarLeft />
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
        {hasActiveRoom && <SidebarRight />}
      </div>
    </div>
  );
}
```

#### `TopNav.tsx`

Layout: `Logo | NavLink×4 | Profile dropdown`

NavLinks:
- `/rooms` → "Public Rooms"
- `/chat` → filtered to private only (or separate `/private-rooms`)
- `/chat` → "Contacts" (scroll to contacts section in sidebar)
- `/sessions` → "Sessions"

Profile dropdown (right): username, "Edit profile" → `/profile`, "Sign out"

#### `SidebarLeft.tsx`

Replaces `Sidebar` from `ChatLayout.tsx`. Absorbs all existing logic:

- Search `<input>` at top — filters rooms and contacts by name (client-side, `useMemo`)
- **ROOMS accordion:**
  - "Public" group: rooms where `room.visibility === "public"` + unread badge
  - "Private" group: rooms where `room.visibility === "private"` + unread badge
  - Click room → `navigate("/chat/rooms/:roomId")`
- **CONTACTS section:** existing `ContactRow` list — click "Send message" → `navigate("/chat/dm/:userId")`
- Pending friend requests section (existing `RequestRow`)
- `[+ Create room]` and `[+ Add friend]` buttons
- Collapse toggle → icon-strip mode

#### `SidebarRight.tsx`

Shown when `roomId` param is present. Calls `GET /api/rooms/{roomId}/members`:

```tsx
function SidebarRight() {
  const { roomId } = useParams();
  const { data: room } = useRoom(roomId!);
  const { data: members = [] } = useRoomMembers(roomId!);
  // ... render room info, members list with PresenceDot
}
```

#### New page components (minimal stubs acceptable for Wave B)

- `frontend/src/pages/RoomCatalog.tsx` — lists public rooms, join button
- `frontend/src/pages/SessionsPage.tsx` — migrates from existing sessions UI (if any)
- `frontend/src/pages/ProfilePage.tsx` — stub with username/email display
- `frontend/src/pages/RoomChat.tsx` — thin wrapper: reads `:roomId` param, renders `<MessageThread>`
- `frontend/src/pages/DmChat.tsx` — calls `POST /api/personal/{userId}` to get/create DM room, then renders `<MessageThread>`

### Route structure in `App.tsx`

```tsx
<Route element={<ProtectedRoute />}>
  <Route element={<AppShell />}>
    <Route index element={<Navigate to="/chat" replace />} />
    <Route path="/chat" element={<ChatPlaceholder />} />
    <Route path="/chat/rooms/:roomId" element={<RoomChat />} />
    <Route path="/chat/dm/:userId" element={<DmChat />} />
    <Route path="/rooms" element={<RoomCatalog />} />
    <Route path="/sessions" element={<SessionsPage />} />
    <Route path="/profile" element={<ProfilePage />} />
  </Route>
  <Route path="*" element={<Navigate to="/chat" replace />} />
</Route>
```

### What to preserve from ChatLayout.tsx

Move these components into their new homes:
- `ContactRow` → `SidebarLeft.tsx` (keep logic intact)
- `RequestRow` → `SidebarLeft.tsx`
- `AddFriendModal` → `SidebarLeft.tsx`
- `RoomRow` → `SidebarLeft.tsx` (extend with unread badge)
- `CreateRoomForm` → `SidebarLeft.tsx`

`ChatLayout.tsx` can be deleted after migration, or kept temporarily as a re-export.

### Scroll behaviour

`MessageThread` already exists. For TASK-09, verify:
- Message list container: `overflow-y: auto` in a flex col filling height
- Auto-scroll: only if `scrollTop + clientHeight >= scrollHeight - 50`
- Infinite scroll: `IntersectionObserver` on top sentinel triggering next page load

---

## 5. Agent Assignments and Wave Plan

### Blockers to fix before any wave (5 minutes total)

1. Add `"room_id": str(room_id)` to `message.new` broadcast in `messages.py` — 1 line
2. Fix `WsMessageEdited` broadcast shape to match TS type — 5 lines
3. No frontend fix needed yet for "Send message" (blocked until routes exist in Wave B)

### Wave A (parallel — Backend and Frontend independent)

**Backend Agent tasks:**
1. Fix blocker items 1 and 2 above in `messages.py`
2. Alembic migration: `Attachment.message_id` nullable + add `room_id` column to `Attachment`
3. Fully implement `attachments.py` (upload, download, delete)
4. Fully implement `unread.py` (GET counts, POST mark-read)
5. Add `unread.increment` broadcast to `send_message` in `messages.py`
6. Update `MessageCreate` schema + `send_message` to accept `attachment_ids`

**Frontend Agent tasks (Wave A — independent of backend fix timing):**
1. Create `unreadStore.ts`
2. Wire `unread.increment` / `unread.cleared` in `App.tsx` WS handler
3. Add `GET /api/unread` fetch on auth mount → `initUnread`
4. Update `App.tsx` for `message.new` to use `event.message.room_id` as fallback until backend fix lands
5. Create `usePasteUpload.ts`
6. Add attachment upload UI to `MessageInput` (file picker, preview, XHR progress)
7. Add attachment display in message bubbles
8. Update `types.ts` to fix `WsMessageEdited` shape

### Wave B (after Wave A — Frontend only)

1. Create `AppShell.tsx`
2. Create `TopNav.tsx`
3. Create `SidebarLeft.tsx` (migrate from ChatLayout + unread badges)
4. Create `SidebarRight.tsx` (members panel + presence)
5. Create page stubs: `RoomChat`, `DmChat`, `RoomCatalog`, `SessionsPage`, `ProfilePage`
6. Restructure routes in `App.tsx` using nested `<Route element={<AppShell />}>`
7. Wire "Send message" in contacts to `/chat/dm/:userId`
8. Delete `ChatLayout.tsx` (or keep as re-export wrapper)

**Backend (Wave B):** No new work. Review / support QA.

### Wave C (QA — after Wave B)

1. Backend tests: `unread.py` (GET, mark-read, multi-room, own-message exclusion, no-receipt)
2. Backend tests: `attachments.py` (upload, download, delete, 413, 403 non-member)
3. Frontend unit tests: `unreadStore.ts` (init, increment, clear, total)
4. E2e: unread badge appears on new message, clears on room open, persists across reload
5. E2e: file upload via button, paste from clipboard, download, 413 error display
6. E2e: AppShell layout, nav, sidebar collapse, right panel

### Dependency graph

```
Wave A (parallel):
  Backend:  message.new fix → migration → attachments.py → unread.py → unread.increment
  Frontend: unreadStore → App.tsx wiring → attachment UI → types.ts fix

Wave B (after A completes):
  Frontend: AppShell → TopNav → SidebarLeft → SidebarRight → routes → DM navigation

Wave C (after B completes):
  QA: tests for 07, 08, 09
```

---

## Appendix: Key File Locations

| File | Purpose |
|------|---------|
| `backend/app/api/routes/attachments.py` | Stub — needs full implementation |
| `backend/app/api/routes/unread.py` | Stub — needs full implementation |
| `backend/app/api/routes/messages.py` | Fix `message.new` broadcast + emit unread events |
| `backend/app/models/message.py` | Attachment, ReadReceipt — migration for nullable message_id + room_id |
| `backend/app/schemas/message.py` | Add `attachment_ids` to `MessageCreate` |
| `backend/app/core/config.py` | UPLOAD_DIR + size limits already set |
| `frontend/src/lib/unreadStore.ts` | New — create in Wave A |
| `frontend/src/hooks/usePasteUpload.ts` | New — create in Wave A |
| `frontend/src/lib/types.ts` | Fix `WsMessageEdited` shape in Wave A |
| `frontend/src/App.tsx` | Add unread WS handlers + mount fetch in Wave A |
| `frontend/src/pages/ChatLayout.tsx` | Migrate logic to SidebarLeft in Wave B, then delete |
| `frontend/src/components/AppShell.tsx` | New — Wave B |
| `frontend/src/components/TopNav.tsx` | New — Wave B |
| `frontend/src/components/SidebarLeft.tsx` | New — Wave B |
| `frontend/src/components/SidebarRight.tsx` | New — Wave B |

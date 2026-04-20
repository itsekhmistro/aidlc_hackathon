# TASK-06: Messaging & Message History

**Agent:** `/backend` + `/frontend`  
**Phase:** 2 — Features  
**Depends on:** 01-architecture, 02-auth, 05-rooms  
**Parallel with:** 05-rooms

---

## Overview

Messages are stored persistently, paginated with keyset (cursor) pagination, and delivered in real-time over WebSocket. Personal dialogs reuse the same message model as rooms.

---

## Backend

### Routes (`backend/app/api/routes/messages.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/messages/{room_id}?before=<msg_id>&limit=50` | Load message page (oldest first within page) |
| POST | `/api/messages/{room_id}` | Send message (text + optional reply_to_id) |
| PATCH | `/api/messages/{room_id}/{msg_id}` | Edit own message |
| DELETE | `/api/messages/{room_id}/{msg_id}` | Soft-delete (author or room admin) |

### Authorization Guards

- Any request to a room endpoint: verify `RoomMember` row exists for `(room_id, current_user)`.
- Personal room: additionally verify friendship + no mutual ban.
- Edit: only message author.
- Delete: message author OR room admin/owner.

### Pagination

```python
# Keyset: fetch 50 messages with id < before_id, ordered DESC, then reverse for display
SELECT * FROM message
WHERE room_id = :room_id
  AND deleted_at IS NULL  -- soft-deleted shown as placeholder separately
  AND id < :before_id
ORDER BY created_at DESC, id DESC
LIMIT 50
```

Return `{ messages: [...], has_more: bool, next_cursor: msg_id | null }`.  
Include soft-deleted messages as `{ id, deleted: true }` if they have replies referencing them.

### Message Validation

- `content`: 1–3072 UTF-8 characters (strip leading/trailing whitespace)
- `reply_to_id`: must belong to same room

### WS Events

```json
{ "type": "message.new",     "room_id": "...", "message": { full message object } }
{ "type": "message.edited",  "room_id": "...", "message_id": "...", "content": "...", "edited_at": "..." }
{ "type": "message.deleted", "room_id": "...", "message_id": "..." }
```

Broadcast `message.new` to all connected members of the room.  
Messages to offline users are persisted in DB — delivered on next connection via REST history load.

---

## Frontend

### Message List (`frontend/src/components/MessageList.tsx`)

- Virtual list or intersection-observer infinite scroll
- On mount: load last 50 messages
- Scroll to bottom if user was at bottom before new message arrived
- No forced scroll if user has scrolled up (check `scrollTop + clientHeight < scrollHeight - threshold`)
- On scroll to top: load previous page (`before=firstMessageId`)
- Show loading spinner at top during fetch

### Message Item (`frontend/src/components/MessageItem.tsx`)

```
[avatar] Username                              10:21
         Message text here
         (optional) ┌ Reply context ──────────┐
                    │ > @Bob: Original message │
                    └──────────────────────────┘
         [edited] — gray, small, if edited_at set
```

- Soft-deleted messages: show "This message was deleted" placeholder
- Hover → show action menu: Reply, Edit (own), Delete (own or admin)

### Message Input (`frontend/src/components/MessageInput.tsx`)

- `<textarea>` auto-resizing (max 5 lines before scroll)
- Enter to send, Shift+Enter for newline
- Reply context bar above input (shows when replying): `Replying to @Bob × [dismiss]`
- Emoji picker button (trigger emoji-mart or similar library)
- Attach button (handled in Task 07)

### Message Sending Flow

1. Optimistically append message to list with `pending: true` state
2. POST to REST API
3. On success: replace with server response (real id + timestamp)
4. On error: show retry option, mark message as failed

---

## Acceptance Criteria

- [x] Send message → appears for all room members within 3 seconds via WS
- [x] Messages to offline user → visible when they reconnect (loaded from DB history)
- [x] Edit own message → `[edited]` indicator appears; content updated for all
- [ ] Delete message (author or admin) → replaced with deleted placeholder
- [x] Reply to message → quoted context shown above reply
- [ ] Infinite scroll: scrolling to top loads older messages without losing scroll position
- [ ] 10 000 message room remains usable (virtual list or windowing)
- [x] Content over 3072 chars rejected with clear error
- [x] Non-member cannot POST to room (403)
- [ ] Personal dialog: banned participant cannot send new messages (403)

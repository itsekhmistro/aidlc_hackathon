# TASK-08: Unread Notifications

**Agent:** `/backend` + `/frontend`  
**Phase:** 2 — Features  
**Depends on:** 06-messaging  
**Parallel with:** 07-attachments

---

## Overview

Show unread message counts per room/contact. Badge disappears when the user opens the chat. Driven by the `ReadReceipt` table.

---

## Backend

### ReadReceipt Model

```
ReadReceipt
  room_id: FK → Room
  user_id: FK → User
  last_read_message_id: FK → Message
  updated_at: datetime
  PRIMARY KEY (room_id, user_id)
```

### Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/unread` | `{ room_id: unread_count }` for all rooms the user belongs to |
| POST | `/api/unread/{room_id}/mark-read` | Update `ReadReceipt.last_read_message_id` to latest |

### Unread Count Query

```sql
SELECT COUNT(*) FROM message
WHERE room_id = :room_id
  AND created_at > (
    SELECT m2.created_at FROM message m2
    WHERE m2.id = :last_read_id
  )
  AND author_id != :user_id   -- don't count own messages as unread
  AND deleted_at IS NULL
```

If no `ReadReceipt` row → all messages are unread.

### WS Event for Badge Update

When a new message arrives, server sends to all room members (except author):
```json
{ "type": "unread.increment", "room_id": "...", "count": 5 }
```

When user marks room as read (opens it), server broadcasts to all tabs of the same user:
```json
{ "type": "unread.cleared", "room_id": "..." }
```

The `unread.cleared` event is sent to all WebSocket connections for the same `user_id` so that opening a chat in one tab clears the badge in all other tabs too.

---

## Frontend

### Unread Store (`frontend/src/lib/unreadStore.ts`)

```typescript
type UnreadStore = Map<string, number>;  // roomId → unread count
```

- Populated on mount: `GET /api/unread`
- Incremented by `unread.increment` WS event
- Cleared by `unread.cleared` WS event
- Also cleared locally when user navigates to that room

### Mark Read Trigger

- When user opens a room/dialog (route change or click): call `POST /api/unread/{room_id}/mark-read`
- Debounce: don't spam if user switches rooms rapidly (300ms debounce)

### Badge Display

```tsx
// In sidebar room/contact item:
<span className="ml-auto bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5">
  {count}
</span>
```

- Show only when count > 0
- Cap display at 99+ if count > 99

### Total Unread (Nav Bar)

- Sum all unread counts → show in browser tab title: `(5) ChatApp`
- And/or a badge on the nav bar icon

---

## Acceptance Criteria

- [x] Receive message while in another room → unread badge appears on that room
- [x] Click on room → badge disappears; `mark-read` call made
- [x] Multiple tabs: open room in tab A → badge clears in tab B as well
- [x] Own messages do not count as unread for the sender
- [x] Unread persists across page reload (backed by DB `ReadReceipt`)
- [x] Badge caps at 99+
- [x] Browser tab title shows total unread count

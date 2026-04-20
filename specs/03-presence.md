# TASK-03: User Presence (Online / AFK / Offline)

**Agent:** `/backend` + `/frontend`  
**Phase:** 1 — Foundation  
**Depends on:** 01-architecture, 02-auth (WebSocket needs auth)  
**Parallel with:** 04-contacts

---

## Overview

Presence has three states: `online`, `afk`, `offline`.  
The tricky part is **multi-tab support**: a user with 3 tabs open must be `online` as long as any one tab is active, and only become `offline` when all tabs disconnect.

---

## Backend

### Connection Registry (`backend/app/core/presence.py`)

```python
# In-memory store (sufficient for single-process; extend with Redis if scaling)
connections: dict[UUID, dict[str, WebSocket]]  # user_id → {tab_id: ws}
tab_status:  dict[str, str]                     # tab_id → "online" | "afk"
```

### Presence Rules

| Condition | Resulting status |
|-----------|-----------------|
| At least one tab with status `online` | `online` |
| All tabs `afk`, ≥1 connected | `afk` |
| No tabs connected | `offline` |

### WebSocket Events (presence-related)

**Client → Server:**
```json
{ "type": "presence.heartbeat", "tab_id": "<uuid>", "status": "online" | "afk" }
```

**Server → Client (broadcast to relevant contacts + room members):**
```json
{ "type": "presence.update", "user_id": "<uuid>", "status": "online" | "afk" | "offline" }
```

### Server Logic

1. On WS connect: register `(user_id, tab_id)` → recompute + broadcast presence
2. On `presence.heartbeat`: update `tab_status[tab_id]` → recompute + broadcast if changed
3. On WS disconnect: remove tab from registry → recompute + broadcast presence
4. Broadcast target: all users who share a room or friendship with the affected user

### REST

```
GET /api/presence/bulk  { user_ids: [...] }  → { user_id: status }
```

Called by frontend on initial load to populate presence for all visible users.

---

## Frontend

### AFK Detection (`frontend/src/hooks/useActivityTracker.ts`)

- Listen to: `mousemove`, `keydown`, `mousedown`, `touchstart`, `scroll`
- Reset idle timer on each event (1 minute = 60 000 ms)
- When timer fires: send `{ type: "presence.heartbeat", status: "afk" }`
- When activity detected after AFK: send `{ type: "presence.heartbeat", status: "online" }`
- Use `crypto.randomUUID()` as stable `tab_id` stored in `sessionStorage` (persists across soft reloads, gone on tab close)

### Presence Store (`frontend/src/lib/presenceStore.ts`)

- Map of `userId → PresenceStatus`
- Updated by incoming `presence.update` WS events
- Populated on mount via `GET /api/presence/bulk`

### Presence Indicator Component

```tsx
<PresenceDot status="online" />   // green filled
<PresenceDot status="afk" />      // half-filled / yellow
<PresenceDot status="offline" />  // gray
```

Used in: sidebar contact list, room member list.

---

## Acceptance Criteria

- [x] User connecting via WS appears as `online` to contacts/room-mates within 2 seconds
- [x] No mouse activity for 60s → user status changes to `afk` (visible to others)
- [x] Activity after AFK → status returns to `online`
- [x] Closing all tabs → status becomes `offline`
- [x] With 2 tabs open: active in tab A, idle in tab B → status is `online`
- [x] With 2 tabs open: idle in both → status becomes `afk`
- [x] Presence dot renders correctly for all 3 states

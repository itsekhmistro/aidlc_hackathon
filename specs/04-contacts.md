# TASK-04: Contacts / Friends & User Bans

**Agent:** `/backend` + `/frontend`  
**Phase:** 1 — Foundation  
**Depends on:** 01-architecture, 02-auth  
**Parallel with:** 03-presence

---

## Overview

Friends system with request/accept flow. Personal messaging is gated on mutual friendship. User-to-user bans freeze existing personal history and block new contact.

---

## Backend

### Routes (`backend/app/api/routes/friends.py`, `user_bans.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/friends` | List accepted friends with presence |
| GET | `/api/friends/requests/incoming` | Pending requests addressed to me |
| POST | `/api/friends/request` | Send request `{ username, message? }` |
| PATCH | `/api/friends/{friendship_id}/accept` | Accept a pending request |
| DELETE | `/api/friends/{friendship_id}` | Remove friend (or decline pending request) |
| GET | `/api/user-bans` | My ban list |
| POST | `/api/user-bans/{user_id}` | Ban a user |
| DELETE | `/api/user-bans/{user_id}` | Unban a user |

### Friendship Rules

- `Friendship` row is canonical; `(requester_id, addressee_id)` is unique.
- To check friendship: `SELECT WHERE (a=me AND b=them) OR (a=them AND b=me) AND status=accepted`.
- On ban: set `status=banned` (or delete friendship + create UserBan); either approach fine.

### Ban Effect

- `POST /api/user-bans/{user_id}`:
  1. Create `UserBan(banner=me, banned=them)`
  2. Delete or mark friendship as terminated
  3. Broadcast WS event `user.banned` to both parties
- Banned user trying to send personal message → 403
- Existing personal room history remains visible, new messages blocked

### Personal Messaging Gate

Before delivering any message to a personal room, verify:
```python
def can_message(sender_id, recipient_id) -> bool:
    # must be friends
    # neither side has banned the other
```

### WS Events

```json
{ "type": "friend.request_received", "friendship": {...} }
{ "type": "friend.accepted", "friendship": {...} }
{ "type": "friend.removed", "friendship_id": "..." }
{ "type": "user.banned", "banner_id": "...", "banned_id": "..." }
```

---

## Frontend

### Contacts Panel (sidebar)

- Section: **CONTACTS** with `● / ◐ / ○` presence dots
- Unread badge next to contact name (from 08-notifications)
- Click contact → opens personal dialog (get/create personal room)
- Context menu on contact: `Send message`, `Remove friend`, `Ban user`

### Friend Requests

- Bell icon or dedicated **Requests** count in nav
- Incoming requests list: accept / decline buttons
- Send request: search by username (typeahead) with optional message field

### User Ban Flow

- Ban confirmation modal: "Ban {username}? They will no longer be able to contact you."
- Banned users list in Profile settings → unban button

---

## Acceptance Criteria

- [x] Send friend request by username; recipient sees it in real-time (WS event)
- [x] Accept/decline request works; friend appears in contacts list immediately
- [x] Remove friend removes them from contacts list for both users
- [x] Banning a user: friendship terminated, personal room becomes read-only for both
- [x] Banned user cannot send new messages in personal room (403)
- [x] Existing personal message history still visible after ban
- [x] Friend request includes optional message
- [x] Cannot send friend request to someone who has banned you

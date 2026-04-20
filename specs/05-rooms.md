# TASK-05: Chat Rooms

**Agent:** `/backend` + `/frontend`  
**Phase:** 2 — Features  
**Depends on:** 01-architecture, 02-auth  
**Parallel with:** 06-messaging

---

## Overview

Rooms are the central entity. Public rooms are discoverable; private rooms are invitation-only. Every room has exactly one owner (always an admin) and zero or more additional admins.

---

## Backend

### Routes (`backend/app/api/routes/rooms.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/rooms` | any | Public catalog with `?search=&cursor=&limit=50` |
| POST | `/api/rooms` | user | Create room |
| GET | `/api/rooms/{room_id}` | member | Room detail |
| PATCH | `/api/rooms/{room_id}` | owner | Update name/desc/visibility |
| DELETE | `/api/rooms/{room_id}` | owner | Delete room + cascade |
| POST | `/api/rooms/{room_id}/join` | user | Join public room (check ban) |
| POST | `/api/rooms/{room_id}/leave` | member | Leave (owner cannot leave) |
| GET | `/api/rooms/{room_id}/members` | member | Member list with roles + presence |
| POST | `/api/rooms/{room_id}/members/{uid}/admin` | owner | Grant admin |
| DELETE | `/api/rooms/{room_id}/members/{uid}/admin` | owner | Remove admin (not owner) |
| DELETE | `/api/rooms/{room_id}/members/{uid}` | admin | Remove + ban member |
| GET | `/api/rooms/{room_id}/bans` | admin | List banned users with banner |
| DELETE | `/api/rooms/{room_id}/bans/{uid}` | admin | Unban |
| POST | `/api/rooms/{room_id}/invitations` | member | Invite user to private room |
| GET | `/api/rooms/invitations/mine` | user | My pending room invitations |
| POST | `/api/rooms/invitations/{inv_id}/accept` | invitee | Accept invitation |

### Business Rules

- `DELETE /rooms/{id}/members/{uid}` is always a ban (not just remove). Admin cannot unban without explicit unban action.
- Owner cannot be removed, cannot have admin stripped, cannot leave.
- Room name uniqueness enforced at DB level (UNIQUE constraint).
- On room delete: cascade delete messages → attachments (files from disk) → memberships → bans.
- Visibility change (public ↔ private) allowed by owner at any time.

### Public Catalog Query

```sql
SELECT r.id, r.name, r.description, COUNT(m.user_id) as member_count
FROM room r
JOIN room_member m ON m.room_id = r.id
WHERE r.visibility = 'public'
  AND r.is_personal = false
  AND (r.name ILIKE :search OR r.description ILIKE :search)
  AND r.id > :cursor   -- keyset pagination
GROUP BY r.id
ORDER BY r.id
LIMIT 50
```

### WS Events

```json
{ "type": "room.member_joined",  "room_id": "...", "user": {...} }
{ "type": "room.member_left",    "room_id": "...", "user_id": "..." }
{ "type": "room.member_banned",  "room_id": "...", "user_id": "...", "banned_by": "..." }
{ "type": "room.member_unbanned","room_id": "...", "user_id": "..." }
{ "type": "room.admin_granted",  "room_id": "...", "user_id": "..." }
{ "type": "room.admin_removed",  "room_id": "...", "user_id": "..." }
{ "type": "room.deleted",        "room_id": "..." }
{ "type": "room.updated",        "room_id": "...", "changes": {...} }
{ "type": "room.invitation",     "room_id": "...", "invited_by": {...} }
```

---

## Frontend

### Public Room Catalog (`/rooms`)

- Search input → debounced API call
- Card grid: room name, description, member count, [Join] button
- Show "Banned" badge if current user is banned from that room

### Create Room Modal

- Fields: name, description, visibility toggle (public/private)
- On success: auto-join + navigate to new room

### Room in Sidebar

- Public and private rooms in collapsible accordion sections
- Unread badge on room name
- Click → opens room; sidebar compacts (accordion collapses others)

### Room Header

- Room name, description, member count
- [Invite user] button (for admins on private rooms)
- [Manage room] button (for admins/owners) → opens Admin Modal (Task 10)

### Members Panel (right sidebar)

- List of members with `●/◐/○` presence dot + role badge
- Owner gets crown icon
- Admin gets shield icon
- Context menu: `Send message`, `Make admin`, `Remove admin`, `Ban from room` (role-gated)

---

## Acceptance Criteria

- [ ] Create public room → appears in catalog immediately
- [ ] Create private room → not visible in catalog
- [ ] Join public room → user added as member; others see `room.member_joined` event
- [ ] Owner cannot leave room
- [ ] Admin banning a member → removed + cannot rejoin
- [ ] Unbanning allows rejoin
- [ ] Room deletion cascades: messages, files, memberships all removed
- [ ] Visibility change by owner works
- [ ] Private room invitation flow: invite → accept → member added
- [ ] Non-member cannot read room messages (403)

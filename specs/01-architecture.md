# TASK-01: Architecture & Data Models

**Agent:** `/architect`  
**Phase:** 1 — Foundation (run first, everything else depends on this)  
**Parallel with:** nothing — must complete before any implementation

---

## Goal

Lock the database schema, API surface, and WebSocket event protocol before any code is written. Produce artifacts that `/backend` and `/frontend` can implement independently without re-negotiating contracts.

---

## Deliverables

### 1. SQLModel table definitions (backend/app/models/)

#### Core entities

```
User
  id: UUID PK
  username: str UNIQUE NOT NULL (immutable)
  email: str UNIQUE NOT NULL
  hashed_password: str
  created_at: datetime
  deleted_at: datetime | None  # soft-delete tombstone

Session
  id: UUID PK
  user_id: FK → User
  token_hash: str UNIQUE  # SHA-256 of bearer token
  user_agent: str
  ip_address: str
  created_at: datetime
  last_seen_at: datetime
  revoked_at: datetime | None

Presence
  user_id: FK → User PK
  status: enum(online, afk, offline)
  updated_at: datetime

Room
  id: UUID PK
  name: str UNIQUE NOT NULL
  description: str
  visibility: enum(public, private)
  owner_id: FK → User
  created_at: datetime
  is_personal: bool DEFAULT false  # personal dialog rooms

RoomMember
  room_id: FK → Room
  user_id: FK → User
  role: enum(member, admin, owner)
  joined_at: datetime
  PRIMARY KEY (room_id, user_id)

RoomBan
  room_id: FK → Room
  user_id: FK → User
  banned_by_id: FK → User
  banned_at: datetime
  PRIMARY KEY (room_id, user_id)

RoomInvitation
  id: UUID PK
  room_id: FK → Room
  invited_by_id: FK → User
  invited_user_id: FK → User
  created_at: datetime
  accepted_at: datetime | None

Friendship
  id: UUID PK
  requester_id: FK → User
  addressee_id: FK → User
  status: enum(pending, accepted)
  message: str | None
  created_at: datetime
  updated_at: datetime
  UNIQUE (requester_id, addressee_id)

UserBan
  banner_id: FK → User
  banned_id: FK → User
  created_at: datetime
  PRIMARY KEY (banner_id, banned_id)

Message
  id: UUID PK
  room_id: FK → Room
  author_id: FK → User
  content: str (max 3072 chars)
  reply_to_id: FK → Message | None
  created_at: datetime
  edited_at: datetime | None
  deleted_at: datetime | None  # soft-delete

Attachment
  id: UUID PK
  message_id: FK → Message
  original_filename: str
  stored_path: str  # relative to UPLOAD_DIR
  mime_type: str
  size_bytes: int
  comment: str | None
  uploaded_by_id: FK → User
  created_at: datetime

ReadReceipt
  room_id: FK → Room
  user_id: FK → User
  last_read_message_id: FK → Message
  updated_at: datetime
  PRIMARY KEY (room_id, user_id)
```

### 2. REST API contract (OpenAPI outline)

```
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/logout
POST   /api/auth/password-reset-request
POST   /api/auth/password-reset
PATCH  /api/auth/password-change
DELETE /api/auth/account

GET    /api/sessions
DELETE /api/sessions/{session_id}

GET    /api/users/me
PATCH  /api/users/me

GET    /api/rooms?search=&visibility=public&limit=&cursor=
POST   /api/rooms
GET    /api/rooms/{room_id}
PATCH  /api/rooms/{room_id}
DELETE /api/rooms/{room_id}
POST   /api/rooms/{room_id}/join
POST   /api/rooms/{room_id}/leave
GET    /api/rooms/{room_id}/members
POST   /api/rooms/{room_id}/members/{user_id}/admin
DELETE /api/rooms/{room_id}/members/{user_id}/admin
DELETE /api/rooms/{room_id}/members/{user_id}   # ban (admin action)
GET    /api/rooms/{room_id}/bans
DELETE /api/rooms/{room_id}/bans/{user_id}       # unban
POST   /api/rooms/{room_id}/invitations
GET    /api/rooms/{room_id}/invitations

GET    /api/messages/{room_id}?before=<message_id>&limit=50
POST   /api/messages/{room_id}
PATCH  /api/messages/{room_id}/{message_id}
DELETE /api/messages/{room_id}/{message_id}

POST   /api/attachments/{room_id}   # multipart upload
GET    /api/attachments/{attachment_id}   # streamed download (auth check)

GET    /api/friends
POST   /api/friends/request
PATCH  /api/friends/{friendship_id}/accept
DELETE /api/friends/{friendship_id}
GET    /api/friends/requests/incoming

GET    /api/user-bans
POST   /api/user-bans/{user_id}
DELETE /api/user-bans/{user_id}

GET    /api/personal-rooms/{user_id}   # get or create personal dialog

GET    /api/unread   # unread counts per room for current user
POST   /api/unread/{room_id}/mark-read
```

### 3. WebSocket event protocol

See [11-websocket-protocol.md](11-websocket-protocol.md) for full event catalogue.

Single endpoint: `ws://host/ws?token=<bearer>`  
All messages are JSON with a `type` discriminator.

### 4. Alembic initial migration

`alembic revision --autogenerate -m "initial schema"` after models are defined.

---

## Acceptance Criteria

- [x] All SQLModel models defined in `backend/app/models/`
- [x] Alembic migration generated and applies cleanly: `alembic upgrade head`
- [x] OpenAPI spec visible at `/docs` with all routes returning correct schemas
- [x] `frontend/src/lib/types.ts` updated with TypeScript equivalents of all server types
- [x] WS event union types defined in `frontend/src/lib/types.ts`

---

## Implementation Notes

- Model personal dialogs as `Room(is_personal=True)` — reuses all message/attachment/read-receipt logic.
- Use `UUID` PKs everywhere (avoids enumeration attacks on attachment endpoints).
- Soft-delete messages (set `deleted_at`) so replies to deleted messages still render as "deleted message" placeholder.
- Index `(room_id, created_at DESC)` on `Message` for efficient keyset pagination.
- Index `(user_id)` on `ReadReceipt` for fast unread count queries.

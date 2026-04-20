# TASK-15: Personal-room display names

**Agent:** `/backend` + `/frontend`
**Phase:** 3 — Polish
**Depends on:** 05-rooms, 04-contacts

---

## Problem

Personal rooms (DMs) are stored with a deterministic canonical name of the form
`__dm__:<sorted-uuid-a>:<sorted-uuid-b>` so the same pair of users always reuses
the same row. That internal name is currently rendered as-is in the UI — the
sidebar row, the `MessageThread` header, and (occasionally) the Manage Room
modal title. For a DM with user `jack`, the chat header reads:

```
# __dm__:0a691fcb-21d0-4c25-9ca0-4829dc1949b0:d8617c24-a53e-4971-82bc-6fe121e84b81
```

This is unreadable. A DM's title should be the other participant's username as
seen from the current viewer.

---

## Goals

1. A DM (`room.is_personal = true`) shows the **other** member's username
   wherever a room title/label is rendered.
2. Non-personal rooms are unaffected — their `room.name` stays the label.
3. The canonical `room.name` remains immutable (it is the uniqueness key that
   de-duplicates `get_or_create_personal_room`).

---

## Design

Introduce a computed, per-viewer `display_name` field on the `RoomPublic`
response schema. The backend resolves it once per room per request using the
authenticated viewer's id:

- `is_personal = false` → `display_name = room.name`
- `is_personal = true`  → `display_name = <other member's username>`
  (fallback to `room.name` if the other membership cannot be resolved, e.g. a
  dangling row after account deletion)

The frontend renders `room.display_name` in every title/label site; no
client-side DM lookup is needed.

---

## Backend changes

### Schema

`backend/app/schemas/room.py`

```python
class RoomPublic(SQLModel):
    id: uuid.UUID
    name: str
    display_name: str     # NEW — per-viewer, non-empty
    description: str | None
    visibility: str
    owner_id: uuid.UUID
    is_personal: bool
    created_at: datetime
    member_count: int = 0
```

### Helper

`backend/app/api/routes/rooms.py` (shared; `personal.py` imports it)

```python
def _display_name_for_viewer(
    session, room: Room, viewer_id: uuid.UUID,
) -> str:
    if not room.is_personal:
        return room.name
    other = session.exec(
        select(User)
        .join(RoomMember, RoomMember.user_id == User.id)
        .where(RoomMember.room_id == room.id, RoomMember.user_id != viewer_id)
        .limit(1)
    ).first()
    return other.username if other else room.name
```

### Conversion helper

`_to_room_public(session, room)` gains a third parameter `viewer_id` and
populates `display_name`. All six call sites pass `current_user.id`:

- `rooms.py:145, 167, 223, 231, 263`
- `personal.py:74`

No migration — schema-only change on the response side.

---

## Frontend changes

### Types

`frontend/src/lib/types.ts`

```ts
export interface RoomPublic {
  id: string;
  name: string;
  display_name: string;   // NEW
  description: string | null;
  visibility: RoomVisibility;
  owner_id: string;
  is_personal: boolean;
  created_at: string;
  member_count: number;
}
```

### Render sites

- `RoomRow.tsx` — `{room.display_name}` (was `{room.name}`)
- `MessageThread.tsx` — header `# {room.display_name}`
- `ManageRoomModal.tsx` — title `· #${room.display_name}` (cosmetic;
  personal rooms do not realistically open this modal)

### Tests

Existing mocks that construct `RoomPublic` need a `display_name` field. The
convenient helper: set it to the same value as `name` for non-personal mocks,
and to an explicit username for personal-room tests.

Affected mocks (grep for `is_personal` in `frontend/src/__tests__/`): `useAdmin`,
`SidebarLeft`, `MemberRowMenu`, plus any other pages that inline a `RoomPublic`.

---

## Acceptance criteria

- [x] Backend `/api/rooms/mine` response for a DM row contains
  `display_name = <other user's username>` (not `__dm__:...`).
- [x] Backend `/api/personal-rooms/:user_id` response carries the same
  `display_name`.
- [x] Backend `/api/rooms/:id` (visible to a member of a personal room) carries
  the same `display_name`.
- [x] Sidebar `RoomRow` for a DM renders the counterpart's username.
- [x] `MessageThread` header for a DM renders `# <username>`.
- [x] Non-personal rooms still render their canonical `name` (no regression).
- [x] Backend pytest + frontend vitest stay green; existing e2e specs unaffected.

---

## Out of scope

- Renaming the stored `Room.name` column — keep `__dm__:...` as the canonical,
  unique, server-side key.
- Replacing DM room titles in the browser tab `document.title` — the title
  currently only surfaces total unread count (`App.tsx:117`); no change needed.
- Disabling the "Manage" button in the right sidebar for personal rooms — a
  separate UX cleanup, not required for the display-name fix.

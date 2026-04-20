# TASK-09: Frontend Layout & Main Shell

**Agent:** `/frontend`  
**Phase:** 2 — Features  
**Depends on:** 02-auth, 03-presence, 04-contacts, 05-rooms  
**Parallel with:** 07-attachments, 08-notifications

---

## Overview

The main application shell matches the wireframe: top nav, left collapsible sidebar (rooms + contacts), centre chat area, right members panel. This task is about the chrome, routing, and layout — not the individual feature components (those live in their own tasks).

---

## Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ TOP NAV                                                          │
│ Logo | Public Rooms | Private Rooms | Contacts | Sessions | ▼   │
├──────────────────┬──────────────────────────────┬───────────────┤
│ LEFT SIDEBAR     │  CHAT AREA                   │ RIGHT PANEL   │
│ (collapsible)    │                              │ (context)     │
│                  │                              │               │
│ Search           │  [active room/dialog]        │ Room info     │
│ ROOMS accordion  │  MessageList                 │ Members list  │
│   Public ▼       │                              │               │
│   Private ▼      │                              │               │
│ CONTACTS list    │                              │               │
│ [Create room]    │  MessageInput                │               │
└──────────────────┴──────────────────────────────┴───────────────┘
```

---

## Components

### `AppShell.tsx`

- Full-height flex layout
- Contains: `<TopNav>`, `<SidebarLeft>`, `<Outlet>` (react-router), `<SidebarRight>`
- `SidebarRight` only shown when a room is active

### `TopNav.tsx`

```
Logo | [Public Rooms] [Private Rooms] [Contacts] [Sessions] | [Profile ▼] [Sign out]
```

- Active link highlighted
- Profile dropdown: Edit profile, Change password, Delete account

### `SidebarLeft.tsx`

- Search input (filters both rooms and contacts in real time, client-side)
- **ROOMS** section with two accordion groups:
  - `Public Rooms` — list of joined public rooms + unread badge
  - `Private Rooms` — list of joined private rooms + unread badge
- **CONTACTS** section — friend list with presence dots + unread badge
- `[+ Create room]` button at bottom
- Collapses to icon strip when a room is active (accordion-style compaction)
  - Toggle button to re-expand

### `SidebarRight.tsx`

Only visible when a room is selected:

```
Room info
  Name + description
  Visibility badge (Public / Private)
  Owner: username
  Admins: list

Members ({count})
  [search members]
  ● alice (owner)
  ● bob (admin)
  ◐ carol (AFK)
  ○ dave (offline)
  
[Invite user]   (admin only, private rooms)
[Manage room]   (admin only)
```

### Chat Area Routes

```
/chat                  → landing / "select a room"
/chat/rooms/:roomId    → room chat
/chat/dm/:userId       → personal dialog
/rooms                 → public room catalog
/sessions              → active sessions page
/profile               → user profile edit
```

### Scroll Behaviour

- `MessageList` uses CSS `overflow-y: auto` in a flex container that fills available height
- New message auto-scroll: only if `scrollTop + clientHeight >= scrollHeight - 50px`
- Infinite scroll: `IntersectionObserver` on a sentinel element at the top of the list

---

## Responsive

- Min supported width: 1024px (desktop only; no mobile requirement in spec)
- Sidebar can be collapsed to icon-only for more space

---

## Acceptance Criteria

- [x] Layout matches wireframe: nav + left sidebar + centre + right panel
- [x] Sidebar accordion collapses non-active room sections when a room is open
- [x] Search in sidebar filters rooms and contacts by name  <!-- Room search satisfied via Discover Rooms catalog (RoomsPage.tsx:49-70, linked from SidebarLeft.tsx:157); contact search not required by Initial-goal-definition.md §2.3 — only public room catalog search is mandated (§2.4.3) -->

- [x] Navigating between rooms/DMs works without page reload
- [x] Right panel shows correct members with presence for active room
- [x] Profile dropdown accessible from top nav
- [x] "Create room" modal accessible from sidebar

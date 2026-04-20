# TASK-10: Admin & Moderation UI

**Agent:** `/frontend`  
**Phase:** 3 — Polish  
**Depends on:** 05-rooms, 06-messaging, 09-frontend-layout  
**Parallel with:** 12-infrastructure

---

## Overview

All administrative actions are available through modal dialogs triggered from context menus. The main admin entry point is the **Manage Room** modal with 5 tabs (as per wireframe).

---

## Manage Room Modal (`ManageRoomModal.tsx`)

Triggered by `[Manage room]` button in right sidebar. Only visible to admins/owner.

### Tab: Members

```
Search member [________________________]

Username    Status    Role      Actions
alice       online    Owner     —
dave        AFK       Admin     [Remove admin] [Ban]
bob         online    Member    [Make admin]   [Ban] [Remove from room]
carol       offline   Member    [Make admin]   [Ban] [Remove from room]
```

- Search filters list client-side
- Presence dot shown in Status column
- Buttons gated by role:
  - Owner sees all buttons
  - Admin sees buttons for non-admin members only (cannot touch other admins)
  - `[Remove from room]` triggers ban (confirm modal first)

### Tab: Admins

```
Current admins: alice, dave

alice  [Owner — cannot remove admin]
dave   [Remove admin]
```

### Tab: Banned Users

```
Username    Banned by    Date/time            Actions
mike        alice        2026-04-18 13:25     [Unban]
eve         dave         2026-04-18 13:40     [Unban]
```

- Shows who performed the ban and when

### Tab: Invitations

```
Invite by username [__________________] [Send invite]

Pending invitations:
tom   invited by alice   2026-04-19 09:00   [Cancel]
```

### Tab: Settings

```
Room name     [ engineering-room ]
Description   [ backend + frontend discussions ]
Visibility    (●) Public  ( ) Private

                          [ Save changes ]  [ Delete room ]
```

- `[Delete room]` requires a confirmation modal with room name typed in

---

## Message Context Menu

On hover over any message, show a floating action bar:

```
[↩ Reply]  [✏ Edit]  [🗑 Delete]
```

- `Reply` — available to all members; sets reply context in input
- `Edit` — only for message author
- `Delete` — author OR room admin

`[Delete]` shows confirm: "Delete this message? This cannot be undone."

---

## Member Context Menu (Right Sidebar)

Right-click or `⋮` on member in member list:

```
● bob
──────────────
Send message
──────────────
Make admin          (owner only)
Remove admin        (owner only, if admin)
──────────────
Ban from room       (admin/owner)
──────────────
Send friend request (if not already friends)
```

---

## Confirmation Modals

All destructive actions require confirmation:

| Action | Confirmation text |
|--------|-------------------|
| Ban member | "Ban {username} from #{room}? They will not be able to rejoin." |
| Delete room | "Type room name to confirm deletion: [____]" |
| Delete message | "Delete this message? This cannot be undone." |
| Remove admin | "Remove admin rights from {username}?" |

---

## Acceptance Criteria

- [ ] Manage Room modal opens with 5 tabs; correct content shown per tab  <!-- PARTIAL: 4 tabs (Members, Banned, Invitations, Settings); Admins controls are merged into Members tab rather than a separate tab (ManageRoomModal.tsx:45-51) -->
- [x] Make admin / Remove admin works and updates member list in real-time
- [x] Ban member from Members tab → user removed; appears in Banned users tab
- [x] Unban from Banned tab → user can rejoin
- [x] Room settings save (name, description, visibility)
- [x] Delete room requires typing room name; on confirm room removed + nav redirects
- [x] Message context menu shows correct options based on user role
- [x] Invite by username in Invitations tab sends invitation
- [x] All confirmation modals render correctly before destructive action executes

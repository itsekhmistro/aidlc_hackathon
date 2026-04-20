Current State & Next Steps

  Phase 1 summary

  ┌──────────────────┬──────────────────────────────────────┐
  │       Task       │                Status                │
  ├──────────────────┼──────────────────────────────────────┤
  │ TASK-02 Auth     │ ✅ Both layers done                  │
  ├──────────────────┼──────────────────────────────────────┤
  │ TASK-03 Presence │ ✅ Both layers done                  │
  ├──────────────────┼──────────────────────────────────────┤
  │ TASK-04 Contacts │ 🟡 Frontend done — backend still 501 │
  ├──────────────────┼──────────────────────────────────────┤
  │ TASK-05 Rooms    │ 🟡 Backend done — no frontend UI yet │
  └──────────────────┴──────────────────────────────────────┘

  93 backend tests passing. 78 frontend tests passing.

  ---
  Architect's plan: 4 waves of work

  Wave 1 — parallel (today, unblocks everything)
  - Backend A: Implement friends.py + user_bans.py. Create app/core/social.py with shared friendship_between / ban_between helpers. Add GET /api/rooms/mine to rooms.py (required
  before any TASK-05 frontend work).
  - Backend B: Implement messages.py (cursor-based keyset pagination, WS broadcasts, soft-delete).

  Wave 2 — after Wave 1 friends done
  - Backend: personal.py (get-or-create personal DM room, friendship gate)
  - Frontend A: useRooms, room sidebar, create/browse modals (TASK-05)

  Wave 3 — after Wave 1 messages done
  - Frontend B: useMessages (infinite scroll), MessageThread, MessageBubble, MessageInput, WS cache updates (TASK-06)

  Wave 4 — unread counts, integration pass

  ---
  Key risks flagged by Architect

  1. GET /api/rooms/mine is a blocker — frontend sidebar can't list joined rooms without it. Must be added in Wave 1.
  2. Circular import — personal.py needs helpers from both rooms.py and friends.py. Fix: extract to app/core/social.py + app/core/room_utils.py before writing personal.py.
  3. async def required — any route that calls await presence_manager.send_to_user() must be async def. Current stubs are all def.
  4. Personal room naming — prefix with __dm__ to prevent collision with user-created room names.

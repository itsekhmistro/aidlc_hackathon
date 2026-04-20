  Current state: TASK-02 through TASK-06 complete ✅

  141 backend tests · 54 frontend unit tests · Playwright e2e scaffolded

  ---
  Architect gap analysis — 3 blockers to fix before Wave A

  ┌─────┬────────────────┬───────────────────────────────────────────────────────────────────────────────────────┐
  │  #  │      File      │                                         Issue                                         │
  ├─────┼────────────────┼───────────────────────────────────────────────────────────────────────────────────────┤
  │ 🔴  │ messages.py    │ message.new broadcast missing top-level room_id → App.tsx invalidates wrong query key │
  ├─────┼────────────────┼───────────────────────────────────────────────────────────────────────────────────────┤
  │ 🔴  │ messages.py    │ send_message emits no unread.increment event → TASK-08 can't work without it          │
  ├─────┼────────────────┼───────────────────────────────────────────────────────────────────────────────────────┤
  │ 🔴  │ ChatLayout.tsx │ "Send message" button in ContactRow is not wired → DM navigation broken               │
  └─────┴────────────────┴───────────────────────────────────────────────────────────────────────────────────────┘

  ---
  Next tasks — Wave plan

  Wave A (parallel — fixes + TASK-07 + TASK-08):
  - Backend: fix the 2 messages.py blockers → Alembic migration (nullable message_id on Attachment) → implement attachments.py (upload/download/delete) + unread.py (GET /api/unread,
   POST /api/unread/:id/mark-read)
  - Frontend: fix types.ts WS shape mismatch + ContactRow navigation → create unreadStore.ts → wire unread WS events + fetch on login → attachment upload UI with paste support +
  progress → attachment display in message bubbles

  Wave B (sequential, after A — TASK-09):
  - Frontend only: AppShell + TopNav + SidebarLeft (with unread badges) + SidebarRight (members + presence) + nested react-router routes (/chat/rooms/:id, /chat/dm/:userId, /rooms,
  /sessions, /profile)

  Wave C: QA pass on TASK-07, 08, 09.

  Ready to dispatch Wave A — say the word.

Lead synthesis — architect's review

  Architect surfaced 3 demo-blockers (one of which solves my earlier migration question — auto-migrate in the backend CMD is cleaner than me running alembic upgrade head manually):

  ┌─────┬──────────┬────────────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────┐
  │  #  │ Severity │                                 Issue                                  │                             Fix                             │
  ├─────┼──────────┼────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
  │ 1   │ 🔴       │ No volume for UPLOAD_DIR=/uploads — attachments vanish on restart      │ docker-compose.yml: add uploads_data named volume           │
  ├─────┼──────────┼────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
  │ 2   │ 🔴       │ DB at 6c8b07407866, app expects a1b2c3d4e5f6 — uploads 500 on fresh DB │ backend/Dockerfile: prefix CMD with alembic upgrade head && │
  ├─────┼──────────┼────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
  │ 3   │ 🔴       │ All 3 Playwright specs assert URL == / — Wave B redirects to /chat     │ Update assertions to /chat                                  │
  └─────┴──────────┴────────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────┘

  Plus 🟡 polish (SessionPublic.is_current, DM URL stabilization via navigate(..., {replace:true})), and 🟢 nice-to-haves (N+1 unread query, sidebar collapse).

  Proposed sequence (T-1 to demo)

  - Wave C1 (sequential, ~45 min) — /docker ships volume + auto-migrate · /qa fixes the 3 e2e URL assertions
  - Wave C2 (parallel, ~60 min) — /backend adds SessionPublic.is_current · /frontend consumes it + adds DM URL replace redirect
  - Wave C3 (parallel after C1, ~90 min, /qa) — new specs: attachments.spec.ts, unread.spec.ts (two contexts), dm.spec.ts, smoke for /rooms /sessions /profile
  - Wave C4 (skip if tight) — N+1 unread → grouped SQL · collapse SidebarRight on non-chat routes

  Stop-ship gates: C1 green + C3 attachment/unread specs green. Everything else can slip.

  ---
  Decision needed: Dispatch C1+C2 in parallel now? (C1 unblocks C3, so C3 fires immediately when C1 finishes.) Or do you want any reordering? Reply "go" to dispatch as proposed.
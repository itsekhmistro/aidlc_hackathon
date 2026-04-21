# Changelog

High-signal summary of every tagged release on `greenbase`, newest first.
Detailed per-release notes live in [`RELEASE-NOTES.md`](./RELEASE-NOTES.md);
the spec-by-spec audit lives in [`current-state.md`](./current-state.md).

Versioning follows `MAJOR.MINOR.PATCH`. Dates are UTC.

---

## `1.1.2` — Hackathon submission polish
**Date:** 2026-04-21 · **Tag:** `1.1.2` on `greenbase`

- Added this `specs/CHANGELOG.md` — one-screen version history for
  reviewers.
- Refreshed `README.md` test counts (**271 pytest · 170 vitest · 12
  Playwright cases across 9 spec files**) and added direct links to
  `CHANGELOG.md` + `RELEASE-NOTES.md` + `current-state.md`.
- Tightened the specs index in `README.md` so every file under
  `specs/` is linked.
- No functional code changes. Ship surface identical to `1.1.1`.

---

## `1.1.1` — Invitee-side room-invitation UI
**Date:** 2026-04-21 · **Tag:** `1.1.1` on `greenbase` · **Commits:**
`85440d2` · `079fb12` · `7919491` · `14e8d92`

- **Fix:** invitees now see incoming room invitations in the sidebar
  ("Room invites (N)" block) for both public and private rooms.
  Pre-fix, the backend stored invites and emitted a `room.invitation`
  WS event, but the frontend had no hook, no UI, and no WS handler.
- New `POST /api/rooms/invitations/{id}/decline` endpoint lets the
  invitee reject without joining (admin-side cancel unchanged).
- `RoomInvitationPublic` enriched with `room_name`,
  `invited_by_username`, `invited_username`. `room.invitation` WS
  payload reshaped to `{ type, invitation }`.
- Carries a 1.1.0 load-test rerun with the Prosody sidecar enabled
  (1.0.0 → 1.1.0 comparison now in `loadtests/RESULTS.md`), `@tag(...)`
  on Locust tasks, and a docker-compose PG-port realignment
  (5433 → 5432).
- Tests: backend `264 → 271`, frontend `156 → 170`.

---

## `1.1.0` — Jabber / XMPP integration (spec §6 Advanced)
**Date:** 2026-04-21 · **Tag:** `1.1.0` on `greenbase` · **Commit:**
`6b0f6fe`

- Embedded Prosody XMPP sidecar; users registered through the FastAPI
  flow are auto-provisioned into Prosody and can sign in with standard
  XMPP clients using the same credentials.
- Two-server federation topology (`docker-compose.federation.yml`) with
  six services, shared `federation_net`, and per-container DNS aliases
  (`server-a.local`, `server-b.local`).
- Admin-only **Jabber Admin** + **Federation** dashboards gated on a
  new `User.is_admin` flag (Alembic `b2c3d4e5f6a7`), polled every 10 s.
- Prosody sidecar is opt-in via `--profile jabber`, so `docker compose
  up` remains byte-identical to `1.0.0` for anyone not enabling XMPP.
- Ships `mod_admin_api.lua` (custom — `prosody:0.11.9` lacks
  `mod_http_api`) and `mod_fastapi_webhook.lua` (pushes S2S + session
  events to FastAPI).
- slixmpp load-test harness (`scripts/federation_load_test.py`, default
  50×50 clients). Tests: backend `241 → 264`, frontend `149 → 156`.

---

## `1.0.0` — Core chat app
**Date:** 2026-04-21 · **Tag:** `1.0.0` on `greenbase` · **Commit:**
`2cfb619`

- All of `Initial-goal-definition.md` §§ 2–5 shipped: accounts + auth,
  presence (online / afk / offline, multi-tab), contacts + user-to-
  user ban, public catalog + private-invite rooms, owner/admin/member
  roles, messaging with edit / reply / delete / 3 KB / UTF-8,
  attachments (20 MB file, 3 MB image), unread badges, three-pane UI,
  modal admin actions.
- NFR §3 independently verified via TASK-16: five Locust + pytest
  scenarios (`steady_state_300`, `fanout_1000`, `presence_propagation`,
  `history_10k_read`, `persistence_restart`) all **PASS** with
  p95/p99 comfortably under budget. See `loadtests/RESULTS.md`.
- Backend mitigations landed with the load run: `asyncio.gather`
  fan-out, `pool_size=50`/`max_overflow=50`, per-room member cache,
  uvicorn `--ws-ping-interval 20`, `client_msg_id` echo-through.
- Tests at tag time: backend `223` pytest, frontend `149` vitest,
  12 Playwright test cases across 9 spec files.

---

## `1.0.0-rc` — Staging verification cut
**Date:** 2026-04-21 · **Tag:** `1.0.0-rc` on `greenbase`

- Pre-release candidate cut immediately before `1.0.0`. Identical
  scope to `1.0.0` (all core requirements) minus the small docs +
  tag-message polish that went into the final tag.
- Used to verify the `docker compose up` path from a clean checkout
  against a staging host before the final tag was applied.
- No consumer-facing differences vs. `1.0.0`; present in the tag list
  purely as the audit trail of the pre-release verification step.

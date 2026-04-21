# Hackathon — Agentic Chat App

Full-stack chat app built end-to-end with autonomous AI agents. Three-person team, repo at `itsekhmistro/hackathon`. Demo: 2026-04-21.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite 7 + TypeScript 5.7 + Tailwind CSS 4.2 + shadcn/ui |
| Backend | Python 3.13 + FastAPI + WebSockets + SQLModel + Alembic |
| Database | PostgreSQL 18 |
| Infra | Docker Compose |

## Quick start (Docker)

```bash
cp .env.example .env
# OptionA. Without jabber
#docker compose up --build
# OptionB. With jabber.
docker compose --profile jabber up -d
```

- Frontend → http://localhost:5173
- Backend + WebSocket → http://localhost:8000
- API docs → http://localhost:8000/docs

The backend container runs `alembic upgrade head` on startup, so a fresh DB is auto-migrated. Attachments persist in the `uploads_data` named volume across restarts.

**Security note:** the default `SECRET_KEY` in `.env.example` is `changeme`. Run the stack on `localhost` only unless you set a real key. Do not expose to the public internet without reviewing `backend/app/core/config.py`.

## Quick start (local dev, no Docker)

```bash
# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

## Running tests

```bash
# Backend pytest (in-memory SQLite)
cd backend && uv run pytest tests/

# Frontend vitest (unit + hook)
cd frontend && npm run test

# Playwright e2e (requires stack running on :5173 / :8000)
cd frontend && npx playwright install chromium   # one-time
cd frontend && npx playwright test --project=chromium
```

Current coverage: **271 pytest · 170 vitest · 12 Playwright test cases across 9 spec files**. Five NFR load-test scenarios all **PASS** — see [`loadtests/RESULTS.md`](loadtests/RESULTS.md).

## Agents (slash commands)

Six pre-built agents for the hackathon loop — see `.claude/commands/` for the prompts.

| Command | Role |
|---|---|
| `/lead` | Orchestrator — break the task down, sequence the others |
| `/architect` | System design, data models, API contracts |
| `/backend` | FastAPI routes, WebSocket handlers, DB models |
| `/frontend` | React components, hooks, WebSocket client |
| `/docker` | Dockerfiles, compose, networking, volumes |
| `/qa` | Test automation + review |

Typical flow: `/lead` → `/architect` → (`/backend` ∥ `/frontend`) → `/docker` → `/qa`.

## Project docs

For hackathon reviewers, the three highest-signal files:

- [`specs/CHANGELOG.md`](specs/CHANGELOG.md) — one-screen version
  history (`1.0.0-rc` → `1.1.2`).
- [`specs/RELEASE-NOTES.md`](specs/RELEASE-NOTES.md) — full per-release
  notes.
- [`specs/current-state.md`](specs/current-state.md) — spec-by-spec
  audit against `specs/Initial-goal-definition.md` (16/16 requirements
  + advanced Jabber shipped).

Per-feature design docs live in `specs/`:

- [`00-overview.md`](specs/00-overview.md) ·
  [`01-architecture.md`](specs/01-architecture.md) ·
  [`02-auth.md`](specs/02-auth.md) ·
  [`03-presence.md`](specs/03-presence.md)
- [`04-contacts.md`](specs/04-contacts.md) ·
  [`05-rooms.md`](specs/05-rooms.md) ·
  [`06-messaging.md`](specs/06-messaging.md) ·
  [`07-attachments.md`](specs/07-attachments.md)
- [`08-notifications.md`](specs/08-notifications.md) ·
  [`09-frontend-layout.md`](specs/09-frontend-layout.md) ·
  [`10-admin-ui.md`](specs/10-admin-ui.md)
- [`11-websocket-protocol.md`](specs/11-websocket-protocol.md) ·
  [`12-infrastructure.md`](specs/12-infrastructure.md) ·
  [`13-jabber-design.md`](specs/13-jabber-design.md) ·
  [`13-jabber.md`](specs/13-jabber.md) ·
  [`JabberIntegrationResults.md`](specs/JabberIntegrationResults.md)
- [`14-post-demo-polish.md`](specs/14-post-demo-polish.md) ·
  [`15-dm-display-names.md`](specs/15-dm-display-names.md) ·
  [`16-nfr-load-testing.md`](specs/16-nfr-load-testing.md)
- Reference: [`Initial-goal-definition.md`](specs/Initial-goal-definition.md)
  (original brief).

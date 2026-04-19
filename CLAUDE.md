# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Hackathon focused on agentic development — building real software with autonomous AI agents.
Team of 3, collaborating via GitHub (`itsekhmistro/hackathon`).

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite 7 + TypeScript 5.7 + Tailwind CSS 4.2.1 + shadcn/ui |
| Backend | Python 3.13 + FastAPI + Uvicorn + WebSockets |
| ORM | SQLModel 0.0.22+ (SQLAlchemy 2.x + Pydantic v2) |
| Migrations | Alembic |
| Database | PostgreSQL 18 |
| Infra | Docker Compose |

## Tooling

- Use `uv` instead of `pip`/`pip3` for Python package management (`uv add`, `uv run`, `uv sync`)
- Frontend: `npm` (standard)
- Never modify `requirements.txt` manually — uv manages `pyproject.toml`

## Project Structure

```
hackathon/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, lifespan, CORS, router mount
│   │   ├── core/
│   │   │   ├── config.py     # pydantic-settings Settings (reads .env)
│   │   │   └── db.py         # engine, SessionDep, create_db_and_tables
│   │   ├── api/
│   │   │   ├── main.py       # APIRouter aggregator
│   │   │   └── routes/
│   │   │       ├── health.py # GET /health
│   │   │       └── ws.py     # WebSocket endpoints + ConnectionManager
│   │   ├── models/           # SQLModel table=True models
│   │   └── schemas/          # Pydantic response/request schemas
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── hooks/useWebSocket.ts  # Generic WS hook with reconnect
│   │   ├── lib/api.ts             # Typed fetch wrappers
│   │   ├── lib/types.ts           # Shared TS types, WS event discriminated unions
│   │   └── App.tsx
│   ├── vite.config.ts        # Proxies /api → :8000 and /ws → ws://:8000
│   └── Dockerfile / Dockerfile.dev
├── docker-compose.yml         # Production-style base
├── docker-compose.override.yml# Dev hot-reload overrides
├── .env.example
└── .claude/commands/          # Agent slash commands (see Agents section)
```

## Agents

Five pre-built slash commands for agentic development:

| Command | Role | When to use |
|---|---|---|
| `/lead` | Orchestrator | Start here — break task down, sequence the other agents |
| `/architect` | System design | Lock data models and API contracts before coding |
| `/backend` | FastAPI expert | Implement routes, WebSocket handlers, DB models |
| `/frontend` | React expert | Implement components, hooks, WebSocket client |
| `/docker` | Infra expert | Wire services, fix compose, Dockerfiles |

**Recommended flow:**
1. Paste the task to `/lead` — it produces a plan
2. Run `/architect` to produce schemas and contracts
3. Run `/backend` and `/frontend` in parallel
4. Run `/docker` to wire everything up

## WebSocket Architecture

- Server: `app/api/routes/ws.py` — `ConnectionManager` singleton + `/ws/{client_id}` endpoint
- Client: `frontend/src/hooks/useWebSocket.ts` — auto-reconnecting hook
- Message format: JSON with a `type` discriminator field
- Events defined in `frontend/src/lib/types.ts` as a discriminated union (`ServerEvent`)

## Quick Start (local dev without Docker)

```bash
# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

## Quick Start (Docker)

```bash
cp .env.example .env
docker compose up --build
```
- Frontend: http://localhost:5173
- Backend API + WS: http://localhost:8000
- API docs: http://localhost:8000/docs

## Adding a new feature (checklist)

- [ ] Run `/architect` to define the data model + API contract
- [ ] Add SQLModel model in `backend/app/models/`
- [ ] Run `uv run alembic revision --autogenerate -m "add <feature>"` for migration
- [ ] Add FastAPI route in `backend/app/api/routes/`
- [ ] Register route in `backend/app/api/main.py`
- [ ] Add WS event type to `frontend/src/lib/types.ts` if real-time needed
- [ ] Implement React component/page
- [ ] Test end-to-end: `docker compose up --build`

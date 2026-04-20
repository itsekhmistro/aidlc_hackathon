# TASK-12: Infrastructure & Docker

**Agent:** `/docker`  
**Phase:** 3 — Polish  
**Depends on:** all backend tasks  
**Parallel with:** 10-admin-ui

---

## Overview

`docker compose up` must build and start the full stack. File uploads must persist across container restarts. CORS, ports, and env vars must be consistent across all layers.

---

## Services

```yaml
services:
  db:
    image: postgres:18
    # PG18+ stores data in a version-specific subdir (e.g. /var/lib/postgresql/18/docker/).
    # Mount the PARENT directory — NOT /var/lib/postgresql/data (that's the pre-PG18 convention).
    volumes: [postgres_data:/var/lib/postgresql]
    environment: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    healthcheck: pg_isready

  backend:
    build: ./backend
    depends_on: db (healthy)
    environment:
      # DATABASE_URL is assembled inside app/core/config.py from POSTGRES_* vars.
      # Driver: postgresql+psycopg (sync) — matches sync Session usage in app/core/db.py.
      POSTGRES_SERVER: db
      POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB: from .env
      SECRET_KEY: (random, set in .env)
      UPLOAD_DIR: /uploads
      BACKEND_CORS_ORIGINS: '["http://localhost:5173", ...]'
    volumes:
      - uploads_data:/uploads
    ports: ["8000:8000"]

  frontend:
    build: ./frontend
    depends_on: backend
    ports: ["5173:80"]   # nginx listens on :80 inside the container (prod build)

volumes:
  postgres_data:
  uploads_data:
```

## .env.example

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=hackathon
POSTGRES_PORT=5432

SECRET_KEY=changeme-generate-with-openssl-rand-hex-32

UPLOAD_DIR=/uploads

BACKEND_CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

Notes:
- `POSTGRES_SERVER` is intentionally NOT in `.env.example` — compose sets it to `db` for the backend service so it resolves to the Postgres container. Overriding it to `localhost` only makes sense when running `uv run uvicorn ...` against a locally exposed Postgres.
- Env var is `BACKEND_CORS_ORIGINS` (not `CORS_ORIGINS`). Must be valid JSON array.

## Backend Dockerfile

```dockerfile
FROM python:3.13-slim

# Pull uv from the official distroless image instead of pip-installing it.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

ENV PYTHONPATH=/app

CMD ["sh", "-c", "uv run alembic upgrade head && exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

## Frontend Dockerfile (prod)

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

## nginx.conf

```nginx
server {
    listen 80;

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## docker-compose.override.yml (dev)

```yaml
services:
  backend:
    volumes:
      - ./backend/app:/app/app
    command:
      ["sh", "-c",
       "uv run alembic upgrade head && exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    # `!override` is REQUIRED: Compose merges `ports` lists by append, so without it
    # the dev `5173:5173` would stack on top of prod `5173:80` and both bindings
    # would fail to publish (host :5173 conflict). `!override` replaces the base list.
    ports: !override
      - "5173:5173"
    volumes:
      - ./frontend/src:/app/src
      - ./frontend/index.html:/app/index.html
    environment:
      BACKEND_URL: "http://backend:8000"
    command: ["npm", "run", "dev", "--", "--host"]
```

## Upload Volume

- Named Docker volume `uploads_data` — persists across `docker compose down`
- `docker compose down -v` removes volumes (destructive, documented in README)
- `UPLOAD_DIR` env var tells backend where to write/read files (defaults to `/uploads` in `app/core/config.py`)

## Migration Strategy

- Alembic runs automatically in the CMD before uvicorn starts
- Idempotent: `alembic upgrade head` is safe to run on every startup
- For dev: `uv run alembic revision --autogenerate -m "..."` from within container or host

---

## Acceptance Criteria

- [x] `cp .env.example .env && docker compose up --build` starts all services
- [x] Frontend accessible at `http://localhost:5173`
- [x] API docs at `http://localhost:8000/docs`
- [x] WebSocket connects through nginx proxy
- [x] Uploaded files survive `docker compose restart`
- [x] `docker compose down && docker compose up` (without -v): data persists
- [x] DB migrations apply automatically on backend start
- [x] No hardcoded credentials in Dockerfiles or docker-compose.yml

**Status: DONE** — smoke-tested 2026-04-20 in prod-only mode (`docker compose -f docker-compose.yml up --build`). `/api/*` and `/ws` both verified reachable through nginx on `http://localhost:5173`.

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
    image: postgres:18-alpine
    volumes: [postgres_data:/var/lib/postgresql/data]
    environment: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    healthcheck: pg_isready

  backend:
    build: ./backend
    depends_on: db (healthy)
    environment:
      DATABASE_URL: postgresql+asyncpg://...
      SECRET_KEY: (random, set in .env)
      UPLOAD_DIR: /uploads
      CORS_ORIGINS: http://localhost:5173
    volumes:
      - uploads:/uploads
    ports: ["8000:8000"]

  frontend:
    build: ./frontend
    depends_on: backend
    ports: ["5173:80"]   # nginx in prod; vite dev server in override

volumes:
  postgres_data:
  uploads:
```

## .env.example

```env
POSTGRES_DB=chatapp
POSTGRES_USER=chatapp
POSTGRES_PASSWORD=changeme
SECRET_KEY=change-me-in-production-use-openssl-rand-hex-32
UPLOAD_DIR=/uploads
CORS_ORIGINS=http://localhost:5173
```

## Backend Dockerfile

```dockerfile
FROM python:3.13-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
CMD ["uv", "run", "sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
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
  root /usr/share/nginx/html;
  index index.html;

  location /api/ {
    proxy_pass http://backend:8000;
  }

  location /ws {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
  }

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

## docker-compose.override.yml (dev)

```yaml
services:
  backend:
    volumes:
      - ./backend:/app
    command: uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports: ["5173:5173"]
    command: npm run dev -- --host
```

## Upload Volume

- Named Docker volume `uploads` — persists across `docker compose down`
- `docker compose down -v` removes volumes (destructive, documented in README)
- UPLOAD_DIR env var tells backend where to write/read files

## Migration Strategy

- Alembic runs automatically in the CMD before uvicorn starts
- Idempotent: `alembic upgrade head` is safe to run on every startup
- For dev: `uv run alembic revision --autogenerate -m "..."` from within container or host

---

## Acceptance Criteria

- [ ] `cp .env.example .env && docker compose up --build` starts all services
- [ ] Frontend accessible at `http://localhost:5173`
- [ ] API docs at `http://localhost:8000/docs`
- [ ] WebSocket connects through nginx proxy
- [ ] Uploaded files survive `docker compose restart`
- [ ] `docker compose down && docker compose up` (without -v): data persists
- [ ] DB migrations apply automatically on backend start
- [ ] No hardcoded credentials in Dockerfiles or docker-compose.yml

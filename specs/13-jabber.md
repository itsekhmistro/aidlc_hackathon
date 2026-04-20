# TASK-13: Jabber / XMPP Integration (Advanced)

**Agent:** `/backend` + `/docker` + `/frontend`  
**Phase:** Advanced (implement only after core requirements are done)  
**Depends on:** 01–12 complete  
**Parallel with:** nothing

---

## Overview

Add XMPP server support so external Jabber clients can connect. Support federation (server-to-server) so two instances of the chat app can exchange messages. Add admin UI screens for Jabber connection status and federation traffic.

---

## Chosen Approach: Prosody XMPP Server

Rather than implementing XMPP from scratch in Python, embed **Prosody** (Lua-based XMPP server) as a sidecar container and bridge it to the FastAPI app.

**Why Prosody:**
- Production-quality XMPP with S2S federation built-in
- Supports standard XMPP clients (Pidgin, Gajim, Conversations)
- REST-like `mod_http_api` for user provisioning from FastAPI
- Active community; well-documented

---

## Architecture

```
External XMPP Client (Pidgin/Gajim)
       │ XMPP (5222)
       ▼
 ┌──────────────┐      S2S (5269)      ┌──────────────┐
 │  Prosody A   │◄────────────────────►│  Prosody B   │
 └──────┬───────┘                      └──────┬───────┘
        │ HTTP API                             │ HTTP API
        ▼                                      ▼
 ┌──────────────┐                      ┌──────────────┐
 │  FastAPI A   │                      │  FastAPI B   │
 └──────────────┘                      └──────────────┘
```

---

## Backend: XMPP Bridge

### User Provisioning

When a user registers in FastAPI, also create them in Prosody via HTTP API:

```python
# backend/app/core/xmpp.py
async def provision_xmpp_user(username: str, password: str):
    await httpx.post(
        f"http://prosody:5280/admin/create_user",
        json={"username": username, "password": password}
    )
```

Hook into `POST /api/auth/register` and `PATCH /api/auth/password-change`.

### Message Bridge (optional, for unified history)

For full integration: configure Prosody `mod_http_upload` webhook to forward messages to FastAPI for storage. This is complex — implement basic user sync first, message sync if time permits.

---

## Docker Compose for Federation

### Two-server setup (`docker-compose.federation.yml`):

```yaml
services:
  prosody_a:
    image: prosody/prosody:0.12
    ports:
      - "5222:5222"   # XMPP client
      - "5269:5269"   # S2S federation
    volumes:
      - ./jabber/prosody_a.cfg.lua:/etc/prosody/prosody.cfg.lua
    networks: [federation_net, internal_a]

  prosody_b:
    image: prosody/prosody:0.12
    ports:
      - "5322:5222"   # second client port
      - "5369:5269"   # second S2S port
    volumes:
      - ./jabber/prosody_b.cfg.lua:/etc/prosody/prosody.cfg.lua
    networks: [federation_net, internal_b]

networks:
  federation_net:    # shared between A and B for S2S
  internal_a:
  internal_b:
```

### Prosody Config (`jabber/prosody_a.cfg.lua`)

```lua
VirtualHost "server-a.local"
  enabled = true
  authentication = "internal_plain"
  modules_enabled = {
    "roster"; "saslauth"; "tls"; "dialback";
    "s2s"; "carbons"; "mam"; "http_api";
  }
  s2s_secure_auth = false  -- for local federation testing
```

---

## Frontend: Jabber Admin Screens

### Connection Dashboard (`/admin/jabber`)

Only accessible to a global admin user (add `is_admin` flag to User).

```
┌─────────────────────────────────────────────────────────────┐
│ Jabber Connection Dashboard                                  │
├──────────────────┬──────────────────┬────────────────────────┤
│ Metric           │ Value            │ Status                 │
├──────────────────┼──────────────────┼────────────────────────┤
│ XMPP Server      │ server-a.local   │ ● Connected            │
│ Connected clients│ 47               │                        │
│ S2S Links        │ 2 active         │ ● Federated            │
│ Uptime           │ 2h 14m           │                        │
└──────────────────┴──────────────────┴────────────────────────┘

Active XMPP Sessions
user@server-a.local    Gajim 1.8   192.168.1.5    Connected 14m
alice@server-a.local   Pidgin      192.168.1.6    Connected 2h
```

Data sourced from Prosody's `mod_http_api` stats endpoint:
`GET http://prosody:5280/api/stats`

### Federation Traffic (`/admin/jabber/federation`)

```
┌─────────────────────────────────────────────────────────────┐
│ Federation Traffic                                           │
├────────────────────────────────────────────────────────────-┤
│ Remote Server       │ Direction │ Messages │ Last Active     │
├────────────────────────────────────────────────────────────-┤
│ server-b.local      │ ↔ Both   │ 1,247    │ 5s ago          │
└─────────────────────────────────────────────────────────────┘

Recent Federation Messages (last 50)
[14:22:01] alice@server-a.local → bob@server-b.local  "Hello from A!"
[14:22:02] bob@server-b.local → alice@server-a.local  "Got it!"
```

Data from a lightweight federation log table in FastAPI DB (populated by Prosody webhook).

---

## Load Test (`scripts/federation_load_test.py`)

```python
# 50 clients on server A, 50 on server B
# Each sends 1 message/sec to a client on the other server
# Measure: delivery latency, message loss, throughput

import asyncio
from slixmpp import ClientXMPP  # or aioxmpp

async def run_client(jid, password, target_jid, message_count=100):
    client = ClientXMPP(jid, password)
    # connect, send messages, measure RTT
```

Run with: `uv run python scripts/federation_load_test.py`

Report output:
```
Clients A: 50 | Clients B: 50
Messages sent: 10,000 | Delivered: 9,998 | Lost: 2
Avg latency: 87ms | p95: 210ms | p99: 450ms
Duration: 120s | Throughput: 83 msg/s
```

---

## Implementation Checklist

- [ ] Prosody container in docker-compose
- [ ] User provisioning on register/password-change
- [ ] External XMPP client can connect and exchange messages with another XMPP client
- [ ] Two Prosody instances federate (docker-compose.federation.yml)
- [ ] `/admin/jabber` dashboard shows connection count + status
- [ ] `/admin/jabber/federation` shows S2S traffic
- [ ] Load test script runs and produces report
- [ ] Nav item `Jabber Admin` visible to admin users only

---

## Risk Notes

- Federation requires proper DNS or `/etc/hosts` aliases in Docker network — configure this in compose.
- `slixmpp` or `aioxmpp` are the two Python async XMPP client libraries; either works for the load test.
- Message bridge (XMPP ↔ FastAPI DB) is optional scope — skip if time is short; basic user sync is sufficient.

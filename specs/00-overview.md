# Online Chat — Task Overview & Execution Plan

## Approach

Build a classic web chat in **three sequential phases**, each gated on the previous:

```
Phase 1 — Foundation      Phase 2 — Features        Phase 3 — Polish + Advanced
─────────────────────     ──────────────────────     ──────────────────────────
01-architecture           05-rooms                   10-admin-ui
02-auth                   06-messaging               11-websocket-protocol
03-presence               07-attachments             12-infrastructure
04-contacts               08-notifications           13-jabber (advanced)
                          09-frontend-layout
```

## Agent Assignment

| Task | Agent | Parallel with |
|------|-------|---------------|
| 01-architecture | `/architect` | — (must be first) |
| 02-auth | `/backend` + `/frontend` | — |
| 03-presence | `/backend` + `/frontend` | 04-contacts |
| 04-contacts | `/backend` + `/frontend` | 03-presence |
| 05-rooms | `/backend` + `/frontend` | 06-messaging |
| 06-messaging | `/backend` + `/frontend` | 05-rooms |
| 07-attachments | `/backend` + `/frontend` | 08-notifications |
| 08-notifications | `/backend` + `/frontend` | 07-attachments |
| 09-frontend-layout | `/frontend` | 07, 08 |
| 10-admin-ui | `/frontend` | 12-infrastructure |
| 11-websocket-protocol | `/backend` | 10-admin-ui |
| 12-infrastructure | `/docker` | 10-admin-ui |
| 13-jabber | `/backend` + `/docker` + `/frontend` | — (last) |
| 16-nfr-load-testing | `/qa` + `/backend` + `/docker` | — (post-feature) |

## Key Risks

1. **Multi-tab presence** — requires a per-user WS connection registry keyed by (user_id, tab_id). The most subtle requirement.
2. **File access control** — membership check must happen at download time, not upload time.
3. **Personal chat = room with 2 fixed members** — model personal dialogs as a special room type to reuse all messaging logic.
4. **Infinite scroll + 10k messages** — must use cursor-based pagination (keyset on `created_at + id`), never offset.
5. **Session management** — tokens stored in `httpOnly` cookies; `localStorage` is forbidden.

## Task Files

- [01-architecture.md](01-architecture.md)
- [02-auth.md](02-auth.md)
- [03-presence.md](03-presence.md)
- [04-contacts.md](04-contacts.md)
- [05-rooms.md](05-rooms.md)
- [06-messaging.md](06-messaging.md)
- [07-attachments.md](07-attachments.md)
- [08-notifications.md](08-notifications.md)
- [09-frontend-layout.md](09-frontend-layout.md)
- [10-admin-ui.md](10-admin-ui.md)
- [11-websocket-protocol.md](11-websocket-protocol.md)
- [12-infrastructure.md](12-infrastructure.md)
- [13-jabber.md](13-jabber.md)
- [16-nfr-load-testing.md](16-nfr-load-testing.md) — load & perf verification against NFR §3

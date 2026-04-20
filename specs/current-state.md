⏺ Architect Gap Analysis: TASK-02, TASK-03, TASK-04

  ---
  TASK-02: Authentication & Session Management

  Backend — Status: ✅ COMPLETE

  All 9 routes implemented and correct:
  - POST /api/auth/register — duplicate check, session cookie, tombstone soft-delete
  - POST /api/auth/login — bcrypt verify, persistent/session cookie
  - POST /api/auth/logout — revokes current session only
  - POST /api/auth/password-reset-request — token returned in body (dev mode)
  - POST /api/auth/password-reset — validates reset token, updates password
  - PATCH /api/auth/password-change — authenticated, old+new password
  - DELETE /api/auth/account — full cascade delete per spec
  - GET /api/sessions — lists active sessions with IP/user-agent
  - DELETE /api/sessions/{session_id} — per-session revocation

  Token strategy is correct: secrets.token_urlsafe(32) → SHA-256 stored, raw in HttpOnly cookie, SameSite=Lax.

  One design note: Reset tokens are stored in UserSession with user_agent="password_reset". Functional but fragile — a revoke_all_sessions operation would accidentally invalidate
  pending resets. Acceptable for hackathon scope; flag for post-hackathon refactor.

  ---
  Frontend — Status: ❌ CRITICAL BLOCKER (complete rewrite needed)

  ┌─────────────────────────┬──────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │          Issue          │ Severity │                                                                 Detail                                                                  │
  ├─────────────────────────┼──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ localStorage for token  │ BLOCKER  │ useAuth.ts stores access_token in localStorage. Backend issues HttpOnly cookie — frontend can't read it and must not try. Auth state =  │
  │                         │          │ "can I hit /api/users/me without 401?"                                                                                                  │
  ├─────────────────────────┼──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Wrong API URLs          │ BLOCKER  │ Calls /api/v1/login/access-token and /api/v1/users/me — these don't exist. Correct: /api/auth/login, /api/users/me                      │
  ├─────────────────────────┼──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Bearer token header     │ BLOCKER  │ Uses Authorization: Bearer <token>. Backend reads Cookie: auth_token. Remove all manual token handling.                                 │
  ├─────────────────────────┼──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ useLogout broken        │ BLOCKER  │ Only removes localStorage item. Must POST /api/auth/logout then redirect to /login.                                                     │
  ├─────────────────────────┼──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Missing persistent in   │ Major    │ No "keep me signed in" checkbox → persistent always falsy. Backend supports it, UI doesn't expose it.                                   │
  │ login                   │          │                                                                                                                                         │
  ├─────────────────────────┼──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Missing pages           │ Major    │ No /register, /forgot-password, /reset-password?token= routes or pages.                                                                 │
  ├─────────────────────────┼──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No Zod + React Hook     │ Major    │ Forms use raw useState. Spec requires RHF + Zod with server-side errors inline.                                                         │
  │ Form                    │          │                                                                                                                                         │
  ├─────────────────────────┼──────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No 401 global redirect  │ Major    │ No interceptor to redirect to /login on 401 from any API call.                                                                          │
  └─────────────────────────┴──────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  Required useAuth.ts rewrite contract:
  // Auth state: inferred from /api/users/me — NO localStorage
  export function useCurrentUser(): { user: UserPublic | null; isLoading: boolean }
  export function useLogin(): MutationFn<{ email: string; password: string; persistent: boolean }>
  export function useLogout(): () => Promise<void>  // calls POST /api/auth/logout
  export function useRegister(): MutationFn<RegisterRequest>

  ---
  TASK-03: Presence (Online / AFK / Offline)

  Backend — Status: ✅ COMPLETE

  PresenceManager correctly implements:
  - connections: dict[UUID, dict[str, WebSocket]] — multi-tab keyed by (user_id, tab_id)
  - compute_status: any tab online → online; all tabs afk → afk; empty → offline
  - broadcast_presence: queries room-mates + accepted friends
  - get_initial_presences: sends bulk state on connect
  - DB Presence upsert for persistence across restarts
  - POST /api/presence/bulk — live status with DB fallback

  One deviation from spec: Spec says GET /api/presence/bulk with query body; implementation uses POST with JSON body. POST is more correct (GET with body is non-standard). No change
   needed.

  WS endpoint at /ws?tab_id=<uuid> — correctly authenticates via auth_token cookie, registers tab, broadcasts on connect/disconnect, handles presence.heartbeat.

  ---
  Frontend — Status: ❌ NOT STARTED

  ┌───────────────────────┬──────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │        Missing        │ Severity │                                                                   Detail                                                                   │
  ├───────────────────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ useActivityTracker.ts │ Blocker  │ No AFK detection. Spec: listen to mousemove/keydown/etc, 60s idle → send presence.heartbeat afk, activity → send online. Tab ID from       │
  │                       │          │ sessionStorage.                                                                                                                            │
  ├───────────────────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ presenceStore.ts      │ Blocker  │ No presence map. Spec: Map<userId, PresenceStatus>, updated by presence.update and presence.bulk WS events.                                │
  ├───────────────────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ PresenceDot component │ Major    │ No visual indicator for online/afk/offline states.                                                                                         │
  ├───────────────────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ WS URL mismatch       │ Major    │ App.tsx uses ws://localhost:8000/ws/${CLIENT_ID} (path param). Backend expects /ws?tab_id=<uuid>. Fix: /ws?tab_id=${tabId}                 │
  ├───────────────────────┼──────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No WS auth            │ Major    │ WS connects before auth is established. Cookie is sent automatically by browser on same-origin — but the hardcoded ws://localhost:8000     │
  │                       │          │ bypasses the Vite proxy. Use /ws?tab_id=... (relative) so the proxy forwards it with the cookie.                                           │
  └───────────────────────┴──────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  Required frontend hooks contract:
  // frontend/src/hooks/useActivityTracker.ts
  export function useActivityTracker(tabId: string, sendMessage: (e: ClientEvent) => void): void

  // frontend/src/lib/presenceStore.ts
  export const presenceStore: Map<string, PresenceStatus>
  export function usePresence(userId: string): PresenceStatus

  // frontend/src/components/PresenceDot.tsx
  export function PresenceDot({ status }: { status: PresenceStatus }): JSX.Element

  ---
  TASK-04: Contacts / Friends & User Bans

  Backend — Status: ❌ NOT STARTED (stubs only)

  All 8 routes in friends.py and user_bans.py return HTTP 501. Models exist (Friendship, UserBan in social.py) — that's the only done work.

  What backend must implement:

  # friends.py — full implementation needed
  GET  /api/friends                       → list[FriendshipPublic]  # status=accepted
  GET  /api/friends/requests/incoming     → list[FriendshipPublic]  # status=pending, addressee=me
  POST /api/friends/request               → FriendshipPublic        # body: {username, message?}
                                          # guard: not banned, no existing friendship
  PATCH /api/friends/{id}/accept          → FriendshipPublic        # only addressee can accept
  DELETE /api/friends/{id}               → 204                      # requester OR addressee

  # user_bans.py — full implementation needed
  GET    /api/user-bans                   → list[UserBanPublic]
  POST   /api/user-bans/{user_id}        → 204   # creates ban, terminates friendship, broadcasts WS
  DELETE /api/user-bans/{user_id}        → 204   # removes ban

  WS broadcasts missing — none of the TASK-04 WS events are fired from backend:
  - friend.request_received → to addressee on POST /api/friends/request
  - friend.accepted → to requester on PATCH accept
  - friend.removed → to both on DELETE
  - user.banned → to both on POST /api/user-bans

  All event types ARE defined in frontend/src/lib/types.ts — wire up the broadcasts using presence_manager.send_to_user().

  Missing can_message() gate — spec requires a guard in personal messaging that checks mutual friendship and no active ban. Route personal.py likely exists but this guard isn't in
  friends.py.

  ---
  Frontend — Status: ❌ NOT STARTED

  ┌─────────────────────────────────────────────────┬──────────┐
  │                     Missing                     │ Severity │
  ├─────────────────────────────────────────────────┼──────────┤
  │ Contacts panel (sidebar) with presence dots     │ Blocker  │
  ├─────────────────────────────────────────────────┼──────────┤
  │ Friend requests: incoming list + accept/decline │ Blocker  │
  ├─────────────────────────────────────────────────┼──────────┤
  │ Send friend request: username typeahead         │ Major    │
  ├─────────────────────────────────────────────────┼──────────┤
  │ Context menu on contact: remove/ban             │ Major    │
  ├─────────────────────────────────────────────────┼──────────┤
  │ Ban confirmation modal                          │ Major    │
  ├─────────────────────────────────────────────────┼──────────┤
  │ Banned users list in settings + unban           │ Minor    │
  └─────────────────────────────────────────────────┴──────────┘

  ---
  Architecture Risks

  ┌─────────────────────────────────────────────┬──────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                    Risk                     │     Severity     │                                                 Mitigation                                                  │
  ├─────────────────────────────────────────────┼──────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ PresenceManager is in-process memory        │ Known/Acceptable │ Single process for hackathon. Flag for Redis pub/sub if scaling.                                            │
  ├─────────────────────────────────────────────┼──────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No can_message() gate for personal rooms    │ High             │ Must be implemented in TASK-04 backend before TASK-06 (messaging) starts.                                   │
  ├─────────────────────────────────────────────┼──────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Frontend completely decoupled from backend  │ Critical         │ The frontend auth layer is from the old scaffold template. Must be fixed before ANY other frontend feature  │
  │ auth                                        │                  │ is functional.                                                                                              │
  ├─────────────────────────────────────────────┼──────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ WS hardcoded to ws://localhost:8000         │ High             │ Breaks in Docker (different hostname) and in staging. Must use relative path through Vite proxy.            │
  └─────────────────────────────────────────────┴──────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  Priority Order (Hackathon Timeline)

  IMMEDIATE (blocks everything else):
    1. Frontend: rewrite useAuth.ts (cookie-based, correct endpoints)
    2. Frontend: fix WS URL to use relative path /ws?tab_id=...
    3. Frontend: add RegisterPage + update LoginPage (persistent checkbox, Zod)

  PHASE 1 COMPLETION:
    4. Frontend: useActivityTracker.ts + presenceStore.ts + PresenceDot
    5. Backend: implement friends.py (all 5 routes + WS broadcasts)
    6. Backend: implement user_bans.py (all 3 routes + WS broadcasts + can_message gate)

  BEFORE PHASE 2:
    7. Frontend: contacts panel (sidebar) — needed for messaging UX
    8. Frontend: friend request flow UI

  DEFER (Phase 2/3):
    9. Frontend: ban management in settings
    10. Backend: password reset token table separation

  ---
  Summary Table

  ┌──────────────────┬───────────────┬─────────────────────┬─────────────────┐
  │       Task       │    Backend    │      Frontend       │     Overall     │
  ├──────────────────┼───────────────┼─────────────────────┼─────────────────┤
  │ TASK-02 Auth     │ ✅ Complete   │ ❌ Critical rewrite │ 🔴 Blocked      │
  ├──────────────────┼───────────────┼─────────────────────┼─────────────────┤
  │ TASK-03 Presence │ ✅ Complete   │ ❌ Not started      │ 🟡 Backend done │
  ├──────────────────┼───────────────┼─────────────────────┼─────────────────┤
  │ TASK-04 Contacts │ ❌ Stubs only │ ❌ Not started      │ 🔴 Not started  │
  └──────────────────┴───────────────┴─────────────────────┴─────────────────┘
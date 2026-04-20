# TASK-02: Authentication & Session Management

**Agent:** `/backend` (API) + `/frontend` (UI)  
**Phase:** 1 — Foundation  
**Depends on:** 01-architecture  
**Parallel with:** nothing (other tasks need auth middleware)

---

## Backend

### Routes (`backend/app/api/routes/auth.py`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create user + return session token |
| POST | `/api/auth/login` | Validate credentials + return session token |
| POST | `/api/auth/logout` | Revoke current session |
| POST | `/api/auth/password-reset-request` | Accepts email, issues reset token (stored in DB, returned in response for dev — no email service) |
| POST | `/api/auth/password-reset` | Accepts reset token + new password |
| PATCH | `/api/auth/password-change` | Authenticated; old + new password |
| DELETE | `/api/auth/account` | Delete account + cascade (see rules below) |
| GET | `/api/sessions` | List active sessions for current user |
| DELETE | `/api/sessions/{session_id}` | Revoke a specific session |

### Token Strategy

- Generate a random 32-byte token (`secrets.token_urlsafe(32)`)
- Store SHA-256 hash in `Session.token_hash`
- Send raw token to client in `Set-Cookie: auth_token=<token>; HttpOnly; SameSite=Lax; Path=/`
- `persistent=true` on login → `Max-Age=30d`; default → session cookie
- `get_current_user` dependency reads cookie, hashes it, looks up `Session`

### Account Deletion Cascade

```
DELETE user:
  1. Find all Room WHERE owner_id = user.id
  2. For each owned room:
     a. DELETE attachments (files from disk)
     b. DELETE messages
     c. DELETE room memberships, bans, invitations
     d. DELETE room
  3. DELETE RoomMember WHERE user_id = user.id (non-owned rooms)
  4. DELETE friendships, user bans involving this user
  5. DELETE sessions
  6. Soft-delete user record (keep username in tombstone to prevent reuse)
```

### Password Security

- `passlib[bcrypt]` with rounds=12
- Never log or return passwords

---

## Frontend

### Pages

- `/` → redirect to `/chat` if authenticated, else `/login`
- `/login` — sign-in form (email + password + "keep me signed in" checkbox)
- `/register` — registration form (email + username + password + confirm)
- `/forgot-password` — email input → triggers reset
- `/reset-password?token=` — new password form

### Auth State

- `useAuth` hook — reads `/api/users/me` on mount; provides `user`, `login()`, `logout()`, `register()`
- Store nothing in `localStorage`; presence of valid cookie determines auth state
- Redirect to `/login` on 401 from any API call

### Forms

- All forms use React Hook Form + Zod validation
- Show server-side errors inline (e.g., "Email already taken")
- Disable submit button while request in flight

---

## Acceptance Criteria

- [x] Register with email/username/password succeeds; duplicate email/username returns 422
- [x] Login sets `HttpOnly` cookie; page refresh preserves session
- [x] "Keep me signed in" sets 30-day cookie; unchecked = session cookie
- [x] Logout revokes only current session; other sessions remain valid
- [x] Password reset flow works (token returned in response body for dev testing)
- [x] Account deletion cascades correctly — owned rooms and content removed, non-owned memberships cleared
- [x] Sessions page shows all active sessions with IP + user-agent; individual logout works
- [x] All protected routes return 401 without valid cookie

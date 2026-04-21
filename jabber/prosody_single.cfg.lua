-- Prosody config — single-server mode (docker-compose.yml + profile `jabber`)
-- TASK-13 (specs/13-jabber-design.md §4.1)
--
-- DEV-ONLY. Plaintext auth + unencrypted c2s so the hackathon demo can run
-- without cert provisioning. See prosody_a.cfg.lua header for the warning.

admins = { "admin@server-a.local" }

plugin_paths = { "/usr/lib/prosody/modules-custom" }

modules_enabled = {
  "roster";
  "saslauth";
  "tls";
  "dialback";
  "carbons";
  "mam";
  "http";
  "posix";
  "disco";
  "version";
  "ping";
  -- "smacks" intentionally omitted: not bundled in prosody/prosody:0.11.9;
  -- pulling it from prosody-modules would add a build step for a feature we
  -- don't demonstrate (auto-resume on brief disconnects).
  "fastapi_webhook";  -- TASK-13: posts federation + session events to FastAPI
  "admin_api";        -- TASK-13: FastAPI -> Prosody user provisioning
}

modules_disabled = {}

allow_registration = false
c2s_require_encryption = false
-- Dev-only: allow PLAIN SASL over plaintext c2s so our stdlib-only probe can
-- authenticate without implementing SCRAM-SHA-1 by hand. A real XMPP client
-- (Gajim, Pidgin) will still happily use SCRAM when available.
allow_unencrypted_plain_auth = true

-- S2S disabled in single-server mode — 5269 is exposed on the host for
-- manual federation smoke tests only. Set s2s_secure_auth = false so a
-- future test can still dial back without cert plumbing.
s2s_secure_auth = false
s2s_require_encryption = false

authentication = "internal_plain"

log = {
  { levels = { min = "info" }, to = "console" };
}

http_ports = { 5280 }
https_ports = {}  -- dev-only: no cert, no TLS variant. Quiets a startup warning.
http_interfaces = { "*" }
-- Accept requests whose Host header is the Docker service name (backend uses
-- `http://prosody:5280/admin/...` internally). Without this Prosody 404s on
-- the /admin/* paths because it can't match "prosody" to a VirtualHost.
http_external_url = "http://prosody:5280/"
http_host = "prosody"
trusted_proxies = { "127.0.0.1", "::1", "172.16.0.0/12", "10.0.0.0/8" }

api_auth_token = "dev-admin-token"

fastapi_webhook_url = "http://backend:8000/api/internal/xmpp/event"
fastapi_webhook_token = "dev-webhook-token"

VirtualHost "server-a.local"
  enabled = true

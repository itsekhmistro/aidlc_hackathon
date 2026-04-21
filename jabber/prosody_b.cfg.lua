-- Prosody config — Server B (federation target "server-b.local")
-- TASK-13 (specs/13-jabber-design.md §4.2)
--
-- DEV-ONLY — identical intent to prosody_a.cfg.lua, just the mirror half of
-- the two-host federation. See that file's header for the security caveat.

admins = { "admin@server-b.local" }

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
  -- "smacks" intentionally omitted: not bundled in prosody/prosody:0.11.9.
  "fastapi_webhook";  -- TASK-13: posts federation + session events to FastAPI
  "admin_api";        -- TASK-13: FastAPI -> Prosody user provisioning
}

modules_disabled = {}

allow_registration = false

c2s_require_encryption = false

s2s_secure_auth = false
s2s_require_encryption = false
s2s_insecure_domains = { "server-a.local" }

authentication = "internal_plain"

log = {
  { levels = { min = "info" }, to = "console" };
}

http_ports = { 5280 }
https_ports = {}  -- dev-only: no cert, no TLS variant. Quiets a startup warning.
http_interfaces = { "*" }
http_external_url = "http://prosody_b:5280/"
http_host = "prosody_b"
trusted_proxies = { "127.0.0.1", "::1", "172.16.0.0/12", "10.0.0.0/8" }

api_auth_token = "dev-admin-token"

fastapi_webhook_url = "http://backend_b:8000/api/internal/xmpp/event"
fastapi_webhook_token = "dev-webhook-token"

VirtualHost "server-b.local"
  enabled = true

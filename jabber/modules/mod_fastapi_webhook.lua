-- mod_fastapi_webhook
--
-- Minimal Prosody module that posts two kinds of events to the FastAPI
-- backend so the /admin/jabber dashboards have data:
--
--   1. Federation messages — every `message` stanza that crosses a server
--      boundary (i.e. whose `to` host is not a local VirtualHost) is posted
--      as {"type":"federation.message", direction, local_jid, remote_jid,
--      remote_server, message_preview, session_id}.
--
--   2. Client sessions — c2s bind/unbind events are posted as
--      {"type":"session.client", event, jid, client, ip, session_id}.
--
-- Target URL + shared secret come from the top-level config keys:
--   fastapi_webhook_url   = "http://backend:8000/api/internal/xmpp/event"
--   fastapi_webhook_token = "dev-webhook-token"
--
-- If either is missing the module loads in a passive no-op state so a
-- misconfigured deploy doesn't take Prosody down.
--
-- This module uses Prosody's bundled `util.http` (0.11+). For 0.10 and
-- earlier, swap `http.request` for `net.http.request` — otherwise the
-- surface is compatible.
--
-- TASK-13 (specs/13-jabber-design.md §4.1, §2.3).

local jid = require "util.jid";
local json = require "util.json";
local http = require "net.http";
local datetime = require "util.datetime";

local webhook_url = module:get_option_string("fastapi_webhook_url");
local webhook_token = module:get_option_string("fastapi_webhook_token");

if not webhook_url or webhook_url == "" or not webhook_token or webhook_token == "" then
    module:log("warn", "mod_fastapi_webhook disabled: fastapi_webhook_url or fastapi_webhook_token missing");
    return;
end

local function is_local_host(host)
    if not host then return false end
    -- `hosts` is a global populated by Prosody with every VirtualHost.
    return hosts[host] ~= nil;
end

local function post_event(payload)
    local body = json.encode(payload);
    http.request(webhook_url, {
        method = "POST",
        headers = {
            ["Content-Type"] = "application/json";
            ["X-XMPP-Webhook-Token"] = webhook_token;
        };
        body = body;
    }, function(response_body, code)
        if code < 200 or code >= 300 then
            module:log("warn", "webhook non-2xx status=%d body=%s", code or -1, tostring(response_body):sub(1, 200));
        end
    end);
end

-- ── Federation messages ─────────────────────────────────────────────────────

-- `message/bare` fires for every incoming/outgoing message through the
-- local routing. Filter to just ones that cross a server boundary.
local function on_message(event)
    local stanza = event.stanza;
    if not stanza or stanza.name ~= "message" then return; end
    local to_jid = stanza.attr.to;
    local from_jid = stanza.attr.from;
    if not to_jid or not from_jid then return; end

    local _, to_host = jid.split(to_jid);
    local _, from_host = jid.split(from_jid);
    if not to_host or not from_host then return; end

    local to_local = is_local_host(to_host);
    local from_local = is_local_host(from_host);
    if to_local == from_local then
        -- Both local (pure c2s) or both remote (relay — rare). Not federation.
        return;
    end

    local direction, local_jid_val, remote_jid_val, remote_server;
    if from_local and not to_local then
        direction, local_jid_val, remote_jid_val, remote_server = "out", from_jid, to_jid, to_host;
    else
        direction, local_jid_val, remote_jid_val, remote_server = "in", to_jid, from_jid, from_host;
    end

    local body_tag = stanza:get_child("body");
    local body_text = body_tag and body_tag:get_text() or nil;
    local preview = body_text and body_text:sub(1, 140) or nil;

    post_event({
        type = "federation.message";
        ts = datetime.datetime();
        direction = direction;
        local_jid = local_jid_val;
        remote_jid = remote_jid_val;
        remote_server = remote_server;
        message_preview = preview;
        session_id = (event.origin and event.origin.streamid) or nil;
    });
end

module:hook("message/bare", on_message, 10);
module:hook("message/full", on_message, 10);

-- ── c2s session events ──────────────────────────────────────────────────────

local function session_info(session)
    local bound_jid = session.full_jid or session.bound_jid
        or (session.username and session.host and (session.username .. "@" .. session.host)) or nil;
    local client_name = nil;
    if session.send and session.features and session.features.client_name then
        client_name = session.features.client_name;
    end
    local ip = session.ip or (session.conn and session.conn.ip and session.conn:ip()) or nil;
    return bound_jid, client_name, ip, session.streamid;
end

module:hook("resource-bind", function(event)
    local session = event.session;
    local bound_jid, client, ip, sid = session_info(session);
    if not bound_jid then return; end
    post_event({
        type = "session.client";
        ts = datetime.datetime();
        event = "login";
        jid = bound_jid;
        client = client;
        ip = ip;
        session_id = sid;
    });
end);

module:hook("resource-unbind", function(event)
    local session = event.session;
    local bound_jid, _, _, sid = session_info(session);
    if not bound_jid then return; end
    post_event({
        type = "session.client";
        ts = datetime.datetime();
        event = "logout";
        jid = bound_jid;
        session_id = sid;
    });
end);

module:log("info", "mod_fastapi_webhook loaded, posting events to %s", webhook_url);

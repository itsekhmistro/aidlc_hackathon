-- mod_admin_api
--
-- Minimal HTTP admin surface for user provisioning. Three POST endpoints,
-- bearer-token auth, JSON in/out:
--
--   POST /admin/create_user          {"username","password"}
--   POST /admin/change_user_password {"username","password"}
--   POST /admin/delete_user          {"username"}
--
-- Auth: `Authorization: Bearer <api_auth_token>` must match the top-level
-- `api_auth_token` config key. An empty token in config means the module
-- refuses every request (no accidental wide-open deployments).
--
-- We ship this ourselves instead of using prosody-modules' `mod_http_rest`
-- or `mod_http_admin_api` because those aren't bundled with
-- `prosody/prosody:0.11.9` and pulling them in would add a build step.
-- The surface we need here is narrow enough to implement directly against
-- `core.usermanager`.
--
-- Path dispatch: `module:provides("http", { default_path = "/admin", ... })`
-- plus setting `http_host = "prosody"` in the vhost config so a request to
-- `http://prosody:5280/admin/...` lands on this VirtualHost's routes.
--
-- TASK-13 (specs/13-jabber-design.md §3.2).

local usermanager = require "core.usermanager";
local json = require "util.json";

local api_token = module:get_option_string("api_auth_token");

local function authorized(event)
    if not api_token or api_token == "" then
        return false, 401, "admin api disabled (no api_auth_token configured)";
    end
    local auth = event.request.headers.authorization;
    if not auth or auth ~= ("Bearer " .. api_token) then
        return false, 401, "invalid bearer token";
    end
    return true;
end

local function parse_body(event)
    local body = event.request.body;
    if not body or body == "" then
        return nil, "empty body";
    end
    local ok, payload = pcall(json.decode, body);
    if not ok or type(payload) ~= "table" then
        return nil, "invalid json";
    end
    return payload;
end

local function reply(event, status_code, tbl)
    event.response.status_code = status_code;
    event.response.headers["Content-Type"] = "application/json";
    return json.encode(tbl);
end

local function handle_create(event)
    local ok_auth, status, reason = authorized(event);
    if not ok_auth then return reply(event, status, { error = reason }); end

    local payload, err = parse_body(event);
    if not payload then return reply(event, 400, { error = err }); end
    if not payload.username or not payload.password then
        return reply(event, 400, { error = "username and password required" });
    end

    local host = payload.host or module.host;
    local ok, create_err = usermanager.create_user(payload.username, payload.password, host);
    if not ok then
        -- create_user returns (false, reason) when the user already exists or
        -- storage fails. 409 for the former is the most honest status here.
        module:log("warn", "create_user(%s@%s) failed: %s", payload.username, host, tostring(create_err));
        return reply(event, 409, { error = tostring(create_err or "create_user failed") });
    end
    module:log("info", "mod_admin_api created user %s@%s", payload.username, host);
    return reply(event, 201, { ok = true, jid = payload.username .. "@" .. host });
end

local function handle_change_password(event)
    local ok_auth, status, reason = authorized(event);
    if not ok_auth then return reply(event, status, { error = reason }); end

    local payload, err = parse_body(event);
    if not payload then return reply(event, 400, { error = err }); end
    if not payload.username or not payload.password then
        return reply(event, 400, { error = "username and password required" });
    end

    local host = payload.host or module.host;
    -- `set_password` argument order: username, password, host, resource.
    -- resource=nil applies to the account itself (not a specific session).
    local ok, change_err = usermanager.set_password(payload.username, payload.password, host, nil);
    if not ok then
        module:log("warn", "set_password(%s@%s) failed: %s", payload.username, host, tostring(change_err));
        return reply(event, 404, { error = tostring(change_err or "set_password failed") });
    end
    return reply(event, 200, { ok = true });
end

local function handle_delete(event)
    local ok_auth, status, reason = authorized(event);
    if not ok_auth then return reply(event, status, { error = reason }); end

    local payload, err = parse_body(event);
    if not payload then return reply(event, 400, { error = err }); end
    if not payload.username then
        return reply(event, 400, { error = "username required" });
    end

    local host = payload.host or module.host;
    local ok, del_err = usermanager.delete_user(payload.username, host);
    if not ok then
        module:log("warn", "delete_user(%s@%s) failed: %s", payload.username, host, tostring(del_err));
        return reply(event, 404, { error = tostring(del_err or "delete_user failed") });
    end
    module:log("info", "mod_admin_api deleted user %s@%s", payload.username, host);
    event.response.status_code = 204;
    return "";
end

-- Server-side credential check. Used by the TASK-13 verification plan to
-- confirm that a JID created via /admin/create_user can actually authenticate,
-- without round-tripping through the XMPP wire. Not intended for production
-- use — it leaks timing about whether a username exists.
local function handle_test_password(event)
    local ok_auth, status, reason = authorized(event);
    if not ok_auth then return reply(event, status, { error = reason }); end

    local payload, err = parse_body(event);
    if not payload then return reply(event, 400, { error = err }); end
    if not payload.username or not payload.password then
        return reply(event, 400, { error = "username and password required" });
    end

    local host = payload.host or module.host;
    local ok = usermanager.test_password(payload.username, host, payload.password);
    return reply(event, 200, { ok = ok and true or false });
end

module:provides("http", {
    default_path = "/admin";
    route = {
        ["POST /create_user"] = handle_create;
        ["POST /change_user_password"] = handle_change_password;
        ["POST /delete_user"] = handle_delete;
        ["POST /test_password"] = handle_test_password;
    };
});

module:log("info", "mod_admin_api loaded under /admin/* (vhost=%s)", module.host);

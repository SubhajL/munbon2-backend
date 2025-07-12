-- Thai Digital ID Authentication Plugin for Kong
-- Integrates with Thai government OAuth 2.0 system

local http = require "resty.http"
local jwt = require "resty.jwt"
local cjson = require "cjson"

local ThaiDigitalIDHandler = {
    PRIORITY = 1500,
    VERSION = "1.0.0",
}

-- Configuration schema
function ThaiDigitalIDHandler:init_config(conf)
    conf.auth_endpoint = conf.auth_endpoint or "https://api.digitalid.go.th/oauth/authorize"
    conf.token_endpoint = conf.token_endpoint or "https://api.digitalid.go.th/oauth/token"
    conf.userinfo_endpoint = conf.userinfo_endpoint or "https://api.digitalid.go.th/userinfo"
    conf.timeout = conf.timeout or 10000
end

-- Main access handler
function ThaiDigitalIDHandler:access(conf)
    local headers = kong.request.get_headers()
    local authorization = headers["Authorization"]
    
    if not authorization then
        return kong.response.exit(401, {
            message = "No Authorization header found"
        })
    end
    
    -- Extract token from Bearer scheme
    local token = authorization:match("^[Bb]earer%s+(.+)$")
    if not token then
        return kong.response.exit(401, {
            message = "Invalid Authorization header format"
        })
    end
    
    -- Validate token with Thai Digital ID
    local is_valid, user_info = self:validate_token(conf, token)
    
    if not is_valid then
        return kong.response.exit(401, {
            message = "Invalid or expired token"
        })
    end
    
    -- Set user info in headers for upstream services
    kong.service.request.set_header("X-User-ID", user_info.sub)
    kong.service.request.set_header("X-User-Name", user_info.name)
    kong.service.request.set_header("X-User-Email", user_info.email)
    kong.service.request.set_header("X-User-Citizen-ID", user_info.citizen_id)
    kong.service.request.set_header("X-User-Roles", table.concat(user_info.roles or {}, ","))
end

-- Validate token with Thai Digital ID service
function ThaiDigitalIDHandler:validate_token(conf, token)
    local httpc = http.new()
    httpc:set_timeout(conf.timeout)
    
    -- First, validate JWT signature locally if possible
    local jwt_obj = jwt:verify(conf.jwt_secret, token)
    if not jwt_obj.verified then
        kong.log.err("JWT verification failed: ", jwt_obj.reason)
        return false, nil
    end
    
    -- Then, validate with Thai Digital ID userinfo endpoint
    local res, err = httpc:request_uri(conf.userinfo_endpoint, {
        method = "GET",
        headers = {
            ["Authorization"] = "Bearer " .. token,
            ["Accept"] = "application/json",
        },
        ssl_verify = true,
    })
    
    if not res then
        kong.log.err("Failed to validate token with Thai Digital ID: ", err)
        return false, nil
    end
    
    if res.status ~= 200 then
        kong.log.err("Thai Digital ID validation failed with status: ", res.status)
        return false, nil
    end
    
    local user_info = cjson.decode(res.body)
    
    -- Additional validation for required fields
    if not user_info.sub or not user_info.citizen_id then
        kong.log.err("Invalid user info received from Thai Digital ID")
        return false, nil
    end
    
    -- Cache user info in Kong cache
    local cache_key = "thai_digital_id:" .. token
    kong.cache:set(cache_key, user_info, conf.cache_ttl or 300)
    
    return true, user_info
end

-- OAuth2 authorization flow
function ThaiDigitalIDHandler:authorize(conf)
    local args = kong.request.get_query()
    
    if not args.code then
        -- Redirect to Thai Digital ID authorization
        local redirect_uri = conf.redirect_uri or kong.request.get_forwarded_scheme() .. "://" .. 
                            kong.request.get_forwarded_host() .. kong.request.get_path()
        
        local auth_url = conf.auth_endpoint .. "?" .. ngx.encode_args({
            response_type = "code",
            client_id = conf.client_id,
            redirect_uri = redirect_uri,
            scope = conf.scope or "openid profile email citizen_id",
            state = args.state or ngx.md5(ngx.time() .. ngx.var.remote_addr),
        })
        
        return kong.response.exit(302, nil, {
            ["Location"] = auth_url
        })
    end
    
    -- Exchange authorization code for access token
    local token_data = self:exchange_code_for_token(conf, args.code)
    if not token_data then
        return kong.response.exit(400, {
            message = "Failed to exchange authorization code"
        })
    end
    
    return kong.response.exit(200, token_data)
end

-- Exchange authorization code for access token
function ThaiDigitalIDHandler:exchange_code_for_token(conf, code)
    local httpc = http.new()
    httpc:set_timeout(conf.timeout)
    
    local res, err = httpc:request_uri(conf.token_endpoint, {
        method = "POST",
        body = ngx.encode_args({
            grant_type = "authorization_code",
            code = code,
            client_id = conf.client_id,
            client_secret = conf.client_secret,
            redirect_uri = conf.redirect_uri,
        }),
        headers = {
            ["Content-Type"] = "application/x-www-form-urlencoded",
            ["Accept"] = "application/json",
        },
        ssl_verify = true,
    })
    
    if not res then
        kong.log.err("Failed to exchange code for token: ", err)
        return nil
    end
    
    if res.status ~= 200 then
        kong.log.err("Token exchange failed with status: ", res.status)
        return nil
    end
    
    return cjson.decode(res.body)
end

return ThaiDigitalIDHandler
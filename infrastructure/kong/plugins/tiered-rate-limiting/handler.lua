-- Tiered Rate Limiting Plugin for Kong
-- Provides different rate limits based on user roles and API tiers

local redis = require "resty.redis"
local cjson = require "cjson"

local TieredRateLimitingHandler = {
    PRIORITY = 910,  -- Higher priority than standard rate-limiting plugin
    VERSION = "1.0.0",
}

-- Default rate limits by tier
local DEFAULT_LIMITS = {
    guest = {
        minute = 10,
        hour = 100,
        day = 1000
    },
    basic = {
        minute = 60,
        hour = 1000,
        day = 10000
    },
    premium = {
        minute = 200,
        hour = 5000,
        day = 50000
    },
    enterprise = {
        minute = 1000,
        hour = 20000,
        day = 200000
    },
    government = {
        minute = 2000,
        hour = 50000,
        day = 500000
    }
}

function TieredRateLimitingHandler:access(conf)
    -- Get user tier from headers (set by auth plugin)
    local headers = kong.request.get_headers()
    local user_id = headers["x-user-id"]
    local user_roles = headers["x-user-roles"]
    local user_tier = self:determine_tier(user_roles, conf)
    
    -- Get rate limits for the tier
    local limits = conf.tiers[user_tier] or DEFAULT_LIMITS[user_tier] or DEFAULT_LIMITS.guest
    
    -- Get Redis connection
    local red = redis:new()
    red:set_timeout(conf.redis_timeout or 2000)
    
    local ok, err = red:connect(conf.redis_host or "redis", conf.redis_port or 6379)
    if not ok then
        kong.log.err("Failed to connect to Redis: ", err)
        -- Fail open if Redis is unavailable
        return
    end
    
    -- Check rate limits for each window
    local identifier = user_id or kong.client.get_forwarded_ip()
    local current_time = ngx.time()
    
    for window, limit in pairs(limits) do
        local exceeded, remaining = self:check_rate_limit(red, identifier, window, limit, current_time)
        
        if exceeded then
            -- Set rate limit headers
            kong.response.set_header("X-RateLimit-Limit-" .. window, tostring(limit))
            kong.response.set_header("X-RateLimit-Remaining-" .. window, "0")
            kong.response.set_header("X-RateLimit-Reset-" .. window, tostring(self:get_reset_time(window, current_time)))
            
            return kong.response.exit(429, {
                message = "Rate limit exceeded",
                error = "rate_limit_exceeded",
                tier = user_tier,
                window = window,
                limit = limit,
                retry_after = self:get_retry_after(window, current_time)
            })
        else
            -- Set rate limit headers
            kong.response.set_header("X-RateLimit-Limit-" .. window, tostring(limit))
            kong.response.set_header("X-RateLimit-Remaining-" .. window, tostring(remaining))
            kong.response.set_header("X-RateLimit-Reset-" .. window, tostring(self:get_reset_time(window, current_time)))
        end
    end
    
    -- Set user tier header for logging
    kong.response.set_header("X-User-Tier", user_tier)
    
    -- Close Redis connection
    local ok, err = red:set_keepalive(10000, 100)
    if not ok then
        kong.log.err("Failed to set Redis keepalive: ", err)
    end
end

function TieredRateLimitingHandler:determine_tier(user_roles, conf)
    if not user_roles then
        return "guest"
    end
    
    local roles = {}
    for role in string.gmatch(user_roles, "[^,]+") do
        roles[role:match("^%s*(.-)%s*$")] = true
    end
    
    -- Check for tier based on roles (highest tier wins)
    if conf.role_mapping then
        for tier, required_roles in pairs(conf.role_mapping) do
            for _, required_role in ipairs(required_roles) do
                if roles[required_role] then
                    return tier
                end
            end
        end
    end
    
    -- Default tier mappings
    if roles["government_official"] or roles["rid_admin"] then
        return "government"
    elseif roles["enterprise_user"] or roles["organization_admin"] then
        return "enterprise"
    elseif roles["premium_user"] or roles["farmer_premium"] then
        return "premium"
    elseif roles["basic_user"] or roles["farmer"] then
        return "basic"
    else
        return "guest"
    end
end

function TieredRateLimitingHandler:check_rate_limit(red, identifier, window, limit, current_time)
    local window_start = self:get_window_start(window, current_time)
    local key = string.format("rl:%s:%s:%s", identifier, window, window_start)
    
    -- Increment counter
    local count, err = red:incr(key)
    if err then
        kong.log.err("Failed to increment rate limit counter: ", err)
        return false, limit  -- Fail open
    end
    
    -- Set expiry on first request
    if count == 1 then
        local ttl = self:get_window_duration(window)
        red:expire(key, ttl)
    end
    
    local remaining = math.max(0, limit - count)
    return count > limit, remaining
end

function TieredRateLimitingHandler:get_window_start(window, current_time)
    if window == "minute" then
        return math.floor(current_time / 60) * 60
    elseif window == "hour" then
        return math.floor(current_time / 3600) * 3600
    elseif window == "day" then
        return math.floor(current_time / 86400) * 86400
    end
end

function TieredRateLimitingHandler:get_window_duration(window)
    if window == "minute" then
        return 60
    elseif window == "hour" then
        return 3600
    elseif window == "day" then
        return 86400
    end
end

function TieredRateLimitingHandler:get_reset_time(window, current_time)
    local window_start = self:get_window_start(window, current_time)
    return window_start + self:get_window_duration(window)
end

function TieredRateLimitingHandler:get_retry_after(window, current_time)
    return self:get_reset_time(window, current_time) - current_time
end

return TieredRateLimitingHandler
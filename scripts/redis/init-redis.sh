#!/bin/bash

# Redis initialization script for Munbon Irrigation System
# This script sets up Redis data structures and initial configurations

REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_PASSWORD=${REDIS_PASSWORD:-""}

# Function to run Redis commands
redis_exec() {
    if [ -n "$REDIS_PASSWORD" ]; then
        redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD "$@"
    else
        redis-cli -h $REDIS_HOST -p $REDIS_PORT "$@"
    fi
}

echo "Initializing Redis for Munbon Irrigation System..."

# Test connection
redis_exec ping
if [ $? -ne 0 ]; then
    echo "Failed to connect to Redis"
    exit 1
fi

# Create namespaced keys for different services
echo "Setting up cache namespaces..."

# Session store configuration
redis_exec CONFIG SET save "900 1 300 10 60 10000"
redis_exec CONFIG SET maxmemory-policy "allkeys-lru"

# Set up cache key patterns
cat <<EOF | redis_exec
# User sessions (24 hour TTL)
SET config:session:ttl 86400

# API rate limiting (1 hour window)
SET config:ratelimit:window 3600

# Sensor data cache (5 minute TTL)
SET config:cache:sensor:ttl 300

# GIS data cache (1 hour TTL)
SET config:cache:gis:ttl 3600

# Report cache (30 minute TTL)
SET config:cache:report:ttl 1800

# Feature flags cache (5 minute TTL)
SET config:cache:features:ttl 300
EOF

# Create Lua scripts for atomic operations

# Script for rate limiting
RATE_LIMIT_SCRIPT=$(cat <<'EOF'
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = redis.call("INCR", key)
if current == 1 then
    redis.call("EXPIRE", key, window)
end
if current > limit then
    return 0
else
    return current
end
EOF
)

# Script for sliding window rate limiting
SLIDING_WINDOW_SCRIPT=$(cat <<'EOF'
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local clearBefore = now - window

redis.call("ZREMRANGEBYSCORE", key, 0, clearBefore)
local current = redis.call("ZCARD", key)
if current < limit then
    redis.call("ZADD", key, now, now)
    redis.call("EXPIRE", key, window)
    return 1
else
    return 0
end
EOF
)

# Script for distributed lock
LOCK_SCRIPT=$(cat <<'EOF'
local key = KEYS[1]
local token = ARGV[1]
local ttl = tonumber(ARGV[2])
local result = redis.call("SET", key, token, "NX", "PX", ttl)
if result then
    return 1
else
    return 0
end
EOF
)

# Script for releasing distributed lock
UNLOCK_SCRIPT=$(cat <<'EOF'
local key = KEYS[1]
local token = ARGV[1]
if redis.call("GET", key) == token then
    return redis.call("DEL", key)
else
    return 0
end
EOF
)

# Load scripts
echo "Loading Lua scripts..."
RATE_LIMIT_SHA=$(echo "$RATE_LIMIT_SCRIPT" | redis_exec SCRIPT LOAD)
echo "Rate limit script SHA: $RATE_LIMIT_SHA"

SLIDING_WINDOW_SHA=$(echo "$SLIDING_WINDOW_SCRIPT" | redis_exec SCRIPT LOAD)
echo "Sliding window script SHA: $SLIDING_WINDOW_SHA"

LOCK_SHA=$(echo "$LOCK_SCRIPT" | redis_exec SCRIPT LOAD)
echo "Lock script SHA: $LOCK_SHA"

UNLOCK_SHA=$(echo "$UNLOCK_SCRIPT" | redis_exec SCRIPT LOAD)
echo "Unlock script SHA: $UNLOCK_SHA"

# Store script SHAs for application use
redis_exec HSET scripts:sha rate_limit "$RATE_LIMIT_SHA"
redis_exec HSET scripts:sha sliding_window "$SLIDING_WINDOW_SHA"
redis_exec HSET scripts:sha lock "$LOCK_SHA"
redis_exec HSET scripts:sha unlock "$UNLOCK_SHA"

# Create initial data structures

# System status
redis_exec HSET system:status api "online"
redis_exec HSET system:status scada "online"
redis_exec HSET system:status sensors "online"

# Default rate limits (requests per hour)
redis_exec HSET ratelimits:default guest 100
redis_exec HSET ratelimits:default user 1000
redis_exec HSET ratelimits:default api_key 5000

# Cache warming - load frequently accessed data
echo "Setting up cache warming lists..."
redis_exec SADD cache:warmup:keys "zones:list" "sensors:active" "gates:status"

# Real-time metrics tracking
redis_exec HSET metrics:counters api_requests 0
redis_exec HSET metrics:counters sensor_readings 0
redis_exec HSET metrics:counters control_commands 0

# Pub/Sub channels
echo "Configured Pub/Sub channels:"
echo "  - alerts:critical"
echo "  - alerts:warning"
echo "  - sensors:data"
echo "  - control:status"
echo "  - system:events"

echo "Redis initialization completed successfully!"

# Display configuration summary
echo -e "\nConfiguration Summary:"
echo "====================="
redis_exec INFO server | grep -E "redis_version|tcp_port|config_file"
redis_exec CONFIG GET maxmemory
redis_exec CONFIG GET maxmemory-policy
redis_exec DBSIZE
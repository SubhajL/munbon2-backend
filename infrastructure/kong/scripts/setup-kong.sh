#!/bin/bash

# Kong Setup Script for Munbon Backend
# This script configures Kong routes and plugins

set -e

KONG_ADMIN_URL=${KONG_ADMIN_URL:-http://localhost:8001}

echo "🚀 Setting up Kong API Gateway for Munbon Backend..."

# Wait for Kong to be ready
echo "⏳ Waiting for Kong to be ready..."
until curl -s ${KONG_ADMIN_URL} > /dev/null; do
    echo "Kong is not ready yet. Waiting..."
    sleep 5
done

echo "✅ Kong is ready!"

# Function to create or update a service
create_service() {
    local name=$1
    local url=$2
    local port=$3
    
    echo "📦 Creating service: $name"
    curl -X PUT ${KONG_ADMIN_URL}/services/${name} \
        -H "Content-Type: application/json" \
        -d '{
            "name": "'${name}'",
            "url": "'${url}'",
            "port": '${port}',
            "retries": 5,
            "connect_timeout": 60000,
            "write_timeout": 60000,
            "read_timeout": 60000
        }'
}

# Function to create a route
create_route() {
    local name=$1
    local service=$2
    local path=$3
    local methods=$4
    
    echo "🛣️  Creating route: $name"
    curl -X PUT ${KONG_ADMIN_URL}/routes/${name} \
        -H "Content-Type: application/json" \
        -d '{
            "name": "'${name}'",
            "service": {"name": "'${service}'"},
            "paths": ["'${path}'"],
            "methods": '${methods:-null}',
            "strip_path": false
        }'
}

# Function to enable a plugin
enable_plugin() {
    local name=$1
    local config=$2
    local service=$3
    local route=$4
    
    echo "🔌 Enabling plugin: $name"
    
    local data='{"name": "'${name}'"'
    
    if [ ! -z "$config" ]; then
        data+=', "config": '${config}
    fi
    
    if [ ! -z "$service" ]; then
        data+=', "service": {"name": "'${service}'"}'
    fi
    
    if [ ! -z "$route" ]; then
        data+=', "route": {"name": "'${route}'"}'
    fi
    
    data+='}'
    
    curl -X POST ${KONG_ADMIN_URL}/plugins \
        -H "Content-Type: application/json" \
        -d "${data}"
}

# Create services
echo "📦 Creating services..."
create_service "auth-service" "http://auth-service:3001" 3001
create_service "sensor-data-service" "http://sensor-data-service:3002" 3002
create_service "gis-service" "http://gis-service:3003" 3003
create_service "user-management-service" "http://user-management-service:3004" 3004
create_service "weather-service" "http://weather-service:3005" 3005
create_service "scada-service" "http://scada-service:3006" 3006
create_service "water-control-service" "http://water-control-service:3007" 3007
create_service "ai-model-service" "http://ai-model-service:3008" 3008
create_service "notification-service" "http://notification-service:3009" 3009
create_service "reporting-service" "http://reporting-service:3010" 3010

# Create routes
echo "🛣️  Creating routes..."

# Auth routes
create_route "auth-login" "auth-service" "/api/v1/auth/login" '["POST"]'
create_route "auth-logout" "auth-service" "/api/v1/auth/logout" '["POST"]'
create_route "auth-refresh" "auth-service" "/api/v1/auth/refresh" '["POST"]'
create_route "auth-profile" "auth-service" "/api/v1/auth/profile" '["GET"]'
create_route "auth-oauth" "auth-service" "/api/v1/auth/oauth/(.*)"

# Sensor routes
create_route "sensor-data" "sensor-data-service" "/api/v1/sensors/(.*)"
create_route "sensor-moisture" "sensor-data-service" "/api/v1/moisture/(.*)"
create_route "sensor-water-level" "sensor-data-service" "/api/v1/water-levels/(.*)"

# GIS routes
create_route "gis-data" "gis-service" "/api/v1/gis/(.*)"
create_route "gis-tiles" "gis-service" "/api/v1/tiles/(.*)"

# Other service routes
create_route "users" "user-management-service" "/api/v1/users/(.*)"
create_route "weather" "weather-service" "/api/v1/weather/(.*)"
create_route "scada" "scada-service" "/api/v1/scada/(.*)"
create_route "water-control" "water-control-service" "/api/v1/water-control/(.*)"
create_route "ai-models" "ai-model-service" "/api/v1/ai/(.*)"
create_route "notifications" "notification-service" "/api/v1/notifications/(.*)"
create_route "reports" "reporting-service" "/api/v1/reports/(.*)"

# Enable global plugins
echo "🔌 Enabling global plugins..."

# CORS
enable_plugin "cors" '{
    "origins": ["http://localhost:3000", "http://localhost:8080", "https://*.munbon.go.th"],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    "headers": ["Accept", "Accept-Version", "Content-Length", "Content-MD5", "Content-Type", "Date", "X-Auth-Token", "Authorization", "X-Requested-With"],
    "exposed_headers": ["X-Auth-Token", "X-Total-Count", "X-Page", "X-Page-Size"],
    "credentials": true,
    "max_age": 3600
}'

# Rate limiting
enable_plugin "rate-limiting" '{
    "minute": 200,
    "hour": 10000,
    "policy": "local",
    "fault_tolerant": true,
    "hide_client_headers": false
}'

# Request size limiting
enable_plugin "request-size-limiting" '{
    "allowed_payload_size": 10,
    "size_unit": "megabytes",
    "require_content_length": false
}'

# Prometheus metrics
enable_plugin "prometheus" '{
    "per_consumer": true,
    "status_code_metrics": true,
    "latency_metrics": true,
    "bandwidth_metrics": true,
    "upstream_health_metrics": true
}'

# Bot detection
enable_plugin "bot-detection" '{
    "allow": ["(Uptime-Kuma)"],
    "deny": ["(C|c)rawler", "SpeedySpider", "Scrapy"]
}'

# Enable JWT plugin for protected routes
echo "🔐 Enabling JWT authentication for protected routes..."

# Skip auth for login/register routes
PROTECTED_ROUTES=(
    "auth-profile"
    "sensor-data"
    "sensor-moisture"
    "sensor-water-level"
    "gis-data"
    "gis-tiles"
    "users"
    "weather"
    "scada"
    "water-control"
    "ai-models"
    "notifications"
    "reports"
)

for route in "${PROTECTED_ROUTES[@]}"; do
    enable_plugin "jwt" '{
        "secret_is_base64": false,
        "claims_to_verify": ["exp"],
        "header_names": ["Authorization"],
        "cookie_names": ["token"],
        "maximum_expiration": 86400
    }' "" "${route}"
done

# Create consumers
echo "👥 Creating consumers..."

curl -X PUT ${KONG_ADMIN_URL}/consumers/munbon-frontend \
    -d "username=munbon-frontend&custom_id=frontend-001"

curl -X PUT ${KONG_ADMIN_URL}/consumers/munbon-mobile \
    -d "username=munbon-mobile&custom_id=mobile-001"

curl -X PUT ${KONG_ADMIN_URL}/consumers/munbon-iot \
    -d "username=munbon-iot&custom_id=iot-001"

curl -X PUT ${KONG_ADMIN_URL}/consumers/munbon-scada \
    -d "username=munbon-scada&custom_id=scada-001"

# Create API keys
echo "🔑 Creating API keys..."

curl -X POST ${KONG_ADMIN_URL}/consumers/munbon-frontend/key-auth \
    -d "key=frontend-dev-key-change-in-production"

curl -X POST ${KONG_ADMIN_URL}/consumers/munbon-mobile/key-auth \
    -d "key=mobile-dev-key-change-in-production"

curl -X POST ${KONG_ADMIN_URL}/consumers/munbon-iot/key-auth \
    -d "key=iot-dev-key-change-in-production"

curl -X POST ${KONG_ADMIN_URL}/consumers/munbon-scada/key-auth \
    -d "key=scada-dev-key-change-in-production"

echo "✅ Kong setup completed successfully!"
echo "🌐 Kong Gateway: http://localhost:8000"
echo "🔧 Kong Admin API: http://localhost:8001"
echo "📊 Kong Manager: http://localhost:8002"
echo "🎛️  Konga Dashboard: http://localhost:1337"
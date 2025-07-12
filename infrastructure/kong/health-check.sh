#!/bin/bash

# Kong Health Check Script

KONG_ADMIN_URL=${KONG_ADMIN_URL:-http://localhost:8001}
KONG_PROXY_URL=${KONG_PROXY_URL:-http://localhost:8000}

echo "🏥 Kong Health Check"
echo "===================="

# Check Kong Admin API
echo -n "Admin API: "
if curl -s ${KONG_ADMIN_URL}/status > /dev/null; then
    echo "✅ Healthy"
    STATUS=$(curl -s ${KONG_ADMIN_URL}/status)
    echo "Database: $(echo $STATUS | jq -r '.database.reachable')"
else
    echo "❌ Unreachable"
    exit 1
fi

# Check Kong Proxy
echo -n "Proxy: "
if curl -s ${KONG_PROXY_URL} > /dev/null; then
    echo "✅ Healthy"
else
    echo "❌ Unreachable"
    exit 1
fi

# List services
echo -e "\n📦 Services:"
curl -s ${KONG_ADMIN_URL}/services | jq -r '.data[] | "\(.name) -> \(.host):\(.port)"'

# List routes
echo -e "\n🛣️  Routes:"
curl -s ${KONG_ADMIN_URL}/routes | jq -r '.data[] | "\(.name) -> \(.paths[])"'

# List plugins
echo -e "\n🔌 Enabled Plugins:"
curl -s ${KONG_ADMIN_URL}/plugins | jq -r '.data[] | "\(.name) (\(.enabled))"' | sort | uniq

# Metrics
echo -e "\n📊 Metrics:"
curl -s ${KONG_ADMIN_URL}/metrics

echo -e "\n✅ Health check completed"
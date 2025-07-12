#!/bin/bash

echo "Testing tunnel connection..."

# Test direct localhost first
echo "1. Testing local API directly:"
curl -H "X-Internal-Key: munbon-internal-f3b89263126548" http://localhost:3000/health

echo -e "\n2. Testing tunnel connection:"
curl -H "X-Internal-Key: munbon-internal-f3b89263126548" https://munbon-api.copilet.tech.beautifyai.io/health

echo -e "\n3. Checking tunnel status:"
cloudflared tunnel info munbon-api

echo -e "\n4. Checking DNS:"
nslookup munbon-api.copilet.tech.beautifyai.io
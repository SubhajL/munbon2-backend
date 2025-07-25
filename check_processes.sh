#!/bin/bash

echo "=== Checking Running Processes ==="
echo ""

echo "1. Docker containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Docker not available or no containers running"

echo ""
echo "2. Node.js processes:"
ps aux | grep -E "node.*munbon|npm.*munbon|yarn.*munbon" | grep -v grep || echo "No Node.js processes found"

echo ""
echo "3. Python processes:"
ps aux | grep -E "python.*munbon|python.*sensor|python.*flow" | grep -v grep || echo "No Python processes found"

echo ""
echo "4. PostgreSQL processes:"
ps aux | grep -E "postgres.*543[234]" | grep -v grep || echo "No local PostgreSQL on ports 5432-5434"

echo ""
echo "5. Port usage:"
echo "Checking ports 3000-3020 (typical for Node services):"
lsof -i :3000-3020 2>/dev/null | grep LISTEN || echo "No services on ports 3000-3020"

echo ""
echo "Checking ports 5432-5434 (PostgreSQL):"
lsof -i :5432-5434 2>/dev/null | grep LISTEN || echo "No services on ports 5432-5434"

echo ""
echo "Checking ports 8000-8020 (typical for Python services):"
lsof -i :8000-8020 2>/dev/null | grep LISTEN || echo "No services on ports 8000-8020"
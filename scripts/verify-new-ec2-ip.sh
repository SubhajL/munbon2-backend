#!/bin/bash

# Verify all services are using the new EC2 IP address
NEW_IP="43.209.22.250"
OLD_IP="43.209.12.182"

echo "=== Verifying EC2 IP Update ==="
echo "New IP: $NEW_IP"
echo "Old IP: $OLD_IP (should not be found)"
echo ""

# Check if old IP still exists in any files
echo "1. Checking for old IP in files..."
if grep -r "$OLD_IP" . --include="*.sh" --include="*.sql" --include="*.md" --include="*.yml" --include="*.yaml" --include="*.json" --include="*.env*" --include="*.py" --include="*.ts" --include="*.js" --exclude-dir=".git" --exclude-dir="node_modules" --exclude-dir="venv" --exclude-dir=".venv" 2>/dev/null | grep -v "OLD_IP="; then
    echo "❌ Found old IP in some files!"
else
    echo "✅ Old IP not found in any files"
fi

echo ""
echo "2. Testing PostgreSQL connection to new IP..."
if command -v psql &> /dev/null; then
    if PGPASSWORD='P@ssw0rd123!' psql -h $NEW_IP -p 5432 -U postgres -d postgres -c "SELECT version();" > /dev/null 2>&1; then
        echo "✅ PostgreSQL connection successful"
    else
        echo "❌ PostgreSQL connection failed"
    fi
else
    echo "⚠️  psql not found, using Python to test..."
    python3 << EOF
import psycopg2
try:
    conn = psycopg2.connect(
        host='$NEW_IP',
        port=5432,
        user='postgres',
        password='P@ssw0rd123!',
        database='postgres'
    )
    print("✅ PostgreSQL connection successful")
    conn.close()
except Exception as e:
    print(f"❌ PostgreSQL connection failed: {e}")
EOF
fi

echo ""
echo "3. Checking GitHub secrets..."
if command -v gh &> /dev/null && gh auth status &> /dev/null; then
    EC2_HOST_SECRET=$(gh secret list -R SubhajL/munbon2-backend 2>/dev/null | grep EC2_HOST || echo "")
    if [ -n "$EC2_HOST_SECRET" ]; then
        echo "✅ EC2_HOST secret exists (value not shown for security)"
        echo "   Please verify manually that it's set to: $NEW_IP"
    else
        echo "⚠️  Could not verify EC2_HOST secret"
    fi
else
    echo "⚠️  GitHub CLI not available or not authenticated"
    echo "   Please manually verify EC2_HOST secret is set to: $NEW_IP"
fi

echo ""
echo "4. Service endpoints using new IP:"
echo "   - Sensor Data Consumer: http://$NEW_IP:3004"
echo "   - Sensor Data API: http://$NEW_IP:3003"
echo "   - Moisture HTTP: http://$NEW_IP:8080"
echo "   - PostgreSQL: postgresql://postgres:***@$NEW_IP:5432"

echo ""
echo "5. SSH connection command:"
echo "   ssh -i th-lab01.pem ubuntu@$NEW_IP"

echo ""
echo "=== Summary ==="
echo "IP update appears to be complete. All references should now use: $NEW_IP"
echo "Please manually verify GitHub secrets and test service connections."
#!/bin/bash

# Verify EC2 IP update was successful
OLD_IP="43.209.12.182"
NEW_IP="43.209.22.250"

echo "=== EC2 IP Update Verification ==="
echo "Old IP: $OLD_IP"
echo "New IP: $NEW_IP"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check for any remaining old IP references
echo "Checking for old IP references..."
OLD_IP_COUNT=$(grep -r "$OLD_IP" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude-dir=build --exclude="*.log" 2>/dev/null | wc -l | tr -d ' ')

if [ "$OLD_IP_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ No references to old IP found${NC}"
else
    echo -e "${RED}❌ Found $OLD_IP_COUNT references to old IP${NC}"
    echo "Files containing old IP:"
    grep -r "$OLD_IP" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude-dir=build --exclude="*.log" -l 2>/dev/null
fi

echo ""

# Check that new IP is in key files
echo "Verifying new IP in key configuration files..."
declare -a KEY_FILES=(
    ".env.ec2"
    "pm2-ecosystem.config.js"
    "services/sensor-data/.env.dual-write"
    "services/sensor-data/.env.ec2"
    "services/sensor-data/src/config/dual-write.config.ts"
)

MISSING_COUNT=0
for file in "${KEY_FILES[@]}"; do
    if [ -f "$file" ]; then
        if grep -q "$NEW_IP" "$file" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} $file"
        else
            echo -e "${RED}✗${NC} $file - NEW IP NOT FOUND"
            ((MISSING_COUNT++))
        fi
    else
        echo -e "${YELLOW}?${NC} $file - FILE NOT FOUND"
    fi
done

echo ""

# Summary
if [ "$OLD_IP_COUNT" -eq 0 ] && [ "$MISSING_COUNT" -eq 0 ]; then
    echo -e "${GREEN}=== SUCCESS ===${NC}"
    echo "All IP references have been successfully updated from $OLD_IP to $NEW_IP"
    echo ""
    echo "Next steps:"
    echo "1. Test database connections to the new IP"
    echo "2. Restart any running services that may have cached the old IP"
    echo "3. Update any external systems or documentation"
else
    echo -e "${RED}=== ISSUES FOUND ===${NC}"
    if [ "$OLD_IP_COUNT" -gt 0 ]; then
        echo "- $OLD_IP_COUNT files still contain the old IP"
    fi
    if [ "$MISSING_COUNT" -gt 0 ]; then
        echo "- $MISSING_COUNT key files don't have the new IP"
    fi
    echo ""
    echo "Please review and fix these issues before proceeding."
fi
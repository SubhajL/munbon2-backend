#!/bin/bash

# Update all EC2 IP references from old to new
set -e

OLD_IP="43.209.22.250"
NEW_IP="43.209.22.250"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== UPDATING EC2 IP REFERENCES ===${NC}"
echo -e "Old IP: $OLD_IP"
echo -e "New IP: $NEW_IP"
echo ""

# Find all files containing the old IP
echo -e "${BLUE}Finding files with old IP...${NC}"
FILES=$(grep -r "$OLD_IP" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude="*.log" -l 2>/dev/null | sort | uniq)

# Count files
FILE_COUNT=$(echo "$FILES" | wc -l)
echo -e "Found ${YELLOW}$FILE_COUNT${NC} files to update"
echo ""

# Update each file
for file in $FILES; do
    if [ -f "$file" ]; then
        echo -e "Updating: ${GREEN}$file${NC}"
        # Use sed to replace the IP
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/$OLD_IP/$NEW_IP/g" "$file"
        else
            # Linux
            sed -i "s/$OLD_IP/$NEW_IP/g" "$file"
        fi
    fi
done

echo ""
echo -e "${GREEN}✅ All files updated!${NC}"

# Verify no old IPs remain
echo ""
echo -e "${BLUE}Verifying update...${NC}"
REMAINING=$(grep -r "$OLD_IP" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude="*.log" -l 2>/dev/null | wc -l)

if [ "$REMAINING" -eq 0 ]; then
    echo -e "${GREEN}✓ No references to old IP found${NC}"
else
    echo -e "${YELLOW}⚠ Warning: $REMAINING files still contain old IP${NC}"
    grep -r "$OLD_IP" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude="*.log" -l
fi
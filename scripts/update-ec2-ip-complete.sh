#!/bin/bash

# Complete EC2 IP Update Script
# Updates all references from old IP to new IP

set -e

OLD_IP="43.209.12.182"
NEW_IP="43.209.22.250"
PROJECT_ROOT="/Users/subhajlimanond/dev/munbon2-backend"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== EC2 IP Address Update ===${NC}"
echo -e "Old IP: ${RED}$OLD_IP${NC}"
echo -e "New IP: ${GREEN}$NEW_IP${NC}"
echo ""

# Create backup directory
BACKUP_DIR="$PROJECT_ROOT/backup_before_ip_change_$(date +%Y%m%d_%H%M%S)"
echo -e "${YELLOW}Creating backup directory: $BACKUP_DIR${NC}"
mkdir -p "$BACKUP_DIR"

# Function to update IP in a file
update_ip_in_file() {
    local file=$1
    if grep -q "$OLD_IP" "$file"; then
        # Create backup
        cp "$file" "$BACKUP_DIR/$(basename "$file").bak"
        
        # Update the IP
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/$OLD_IP/$NEW_IP/g" "$file"
        else
            # Linux
            sed -i "s/$OLD_IP/$NEW_IP/g" "$file"
        fi
        
        echo -e "${GREEN}✓${NC} Updated: $file"
        return 0
    fi
    return 1
}

# Find all files containing the old IP
echo -e "\n${BLUE}Finding files with old IP address...${NC}"
FILES_WITH_OLD_IP=$(grep -r "$OLD_IP" "$PROJECT_ROOT" --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=venv --exclude-dir=__pycache__ --exclude-dir=dist --exclude-dir=build --exclude-dir=backup_before_ip_change_* 2>/dev/null | cut -d: -f1 | sort | uniq || true)

if [ -z "$FILES_WITH_OLD_IP" ]; then
    echo -e "${GREEN}No files found with the old IP address.${NC}"
    exit 0
fi

# Count files
FILE_COUNT=$(echo "$FILES_WITH_OLD_IP" | wc -l | tr -d ' ')
echo -e "${YELLOW}Found $FILE_COUNT files containing the old IP${NC}"

# Update each file
UPDATED_COUNT=0
echo -e "\n${BLUE}Updating files...${NC}"
while IFS= read -r file; do
    if [ -f "$file" ]; then
        if update_ip_in_file "$file"; then
            ((UPDATED_COUNT++))
        fi
    fi
done <<< "$FILES_WITH_OLD_IP"

echo -e "\n${GREEN}Updated $UPDATED_COUNT files${NC}"

# Verify no old IPs remain
echo -e "\n${BLUE}Verifying update...${NC}"
REMAINING=$(grep -r "$OLD_IP" "$PROJECT_ROOT" --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=venv --exclude-dir=__pycache__ --exclude-dir=dist --exclude-dir=build --exclude-dir=backup_before_ip_change_* 2>/dev/null | wc -l || true)

if [ "$REMAINING" -eq 0 ]; then
    echo -e "${GREEN}✓ All IP addresses successfully updated!${NC}"
else
    echo -e "${RED}⚠ Warning: Found $REMAINING remaining instances of old IP${NC}"
    echo "Run the following to see remaining instances:"
    echo "grep -r \"$OLD_IP\" \"$PROJECT_ROOT\" --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=venv --exclude-dir=__pycache__ --exclude-dir=dist --exclude-dir=build --exclude-dir=backup_before_ip_change_*"
fi

# Create a summary report
REPORT_FILE="$PROJECT_ROOT/EC2_IP_UPDATE_REPORT_$(date +%Y%m%d_%H%M%S).md"
cat > "$REPORT_FILE" << EOF
# EC2 IP Address Update Report

Date: $(date)

## Summary
- Old IP: $OLD_IP
- New IP: $NEW_IP
- Files Updated: $UPDATED_COUNT
- Backup Location: $BACKUP_DIR

## Updated Files
$(echo "$FILES_WITH_OLD_IP" | while read -r file; do echo "- $file"; done)

## Verification
- Remaining instances of old IP: $REMAINING

## Next Steps
1. Test database connections to the new IP
2. Update any environment variables in production
3. Update any DNS records if applicable
4. Restart services that cache the IP address
EOF

echo -e "\n${BLUE}Report saved to: $REPORT_FILE${NC}"

# Provide specific update instructions
echo -e "\n${YELLOW}=== Important Post-Update Steps ===${NC}"
echo "1. Update any .env files not in version control"
echo "2. Update environment variables in AWS Lambda, EC2, etc."
echo "3. Update any hardcoded IPs in deployment scripts"
echo "4. Test database connections:"
echo "   - PostgreSQL: psql -h $NEW_IP -U postgres -d munbon_dev"
echo "   - TimescaleDB: psql -h $NEW_IP -p 5433 -U postgres -d munbon_timescale"
echo "5. Restart any services that may have cached the old IP"

echo -e "\n${GREEN}IP update script completed!${NC}"
#!/bin/bash

# Script to update EC2 IP address from ${EC2_HOST:-43.208.201.191} to ${EC2_HOST:-43.208.201.191}

OLD_IP="${EC2_HOST:-43.208.201.191}"
NEW_IP="${EC2_HOST:-43.208.201.191}"
PROJECT_ROOT="/Users/subhajlimanond/dev/munbon2-backend"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Updating EC2 IP address from ${OLD_IP} to ${NEW_IP}${NC}"
echo ""

# Count total files to update
TOTAL_FILES=$(grep -r "$OLD_IP" "$PROJECT_ROOT" --exclude-dir=node_modules --exclude-dir=.git --exclude="*.log" | wc -l)
echo -e "${YELLOW}Found ${TOTAL_FILES} occurrences to update${NC}"
echo ""

# Function to update files by extension
update_by_extension() {
    local ext=$1
    local desc=$2
    
    echo -e "${GREEN}Updating ${desc} files (*.${ext})...${NC}"
    
    find "$PROJECT_ROOT" -type f -name "*.${ext}" ! -path "*/node_modules/*" ! -path "*/.git/*" | while read -r file; do
        if grep -q "$OLD_IP" "$file" 2>/dev/null; then
            echo "  Updating: ${file#$PROJECT_ROOT/}"
            sed -i '' "s/$OLD_IP/$NEW_IP/g" "$file"
        fi
    done
}

# Update different file types
update_by_extension "env" "Environment"
update_by_extension "sh" "Shell script"
update_by_extension "py" "Python"
update_by_extension "ts" "TypeScript"
update_by_extension "js" "JavaScript"
update_by_extension "yml" "YAML"
update_by_extension "yaml" "YAML"
update_by_extension "json" "JSON"
update_by_extension "md" "Markdown"
update_by_extension "sql" "SQL"

# Special handling for .env.* files
echo -e "${GREEN}Updating .env.* files...${NC}"
find "$PROJECT_ROOT" -type f -name ".env.*" ! -path "*/node_modules/*" | while read -r file; do
    if grep -q "$OLD_IP" "$file" 2>/dev/null; then
        echo "  Updating: ${file#$PROJECT_ROOT/}"
        sed -i '' "s/$OLD_IP/$NEW_IP/g" "$file"
    fi
done

# Update pm2 ecosystem config
echo -e "${GREEN}Updating PM2 ecosystem config...${NC}"
if [ -f "$PROJECT_ROOT/pm2-ecosystem.config.js" ]; then
    sed -i '' "s/$OLD_IP/$NEW_IP/g" "$PROJECT_ROOT/pm2-ecosystem.config.js"
    echo "  Updated: pm2-ecosystem.config.js"
fi

# Summary
echo ""
echo -e "${GREEN}✅ IP address update complete!${NC}"
echo ""
echo "Summary:"
echo "  - Old IP: ${OLD_IP}"
echo "  - New IP: ${NEW_IP}"
echo "  - Files updated successfully"
echo ""
echo "Next steps:"
echo "1. Review changes: git diff"
echo "2. Test services with new IP"
echo "3. Restart any running services"
echo "4. Commit changes when verified"
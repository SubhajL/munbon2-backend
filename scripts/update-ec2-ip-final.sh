#!/bin/bash

# Script to update EC2 IP address from 43.209.22.250 to 43.209.22.250

OLD_IP="43.209.22.250"
NEW_IP="43.209.22.250"
PROJECT_ROOT="/Users/subhajlimanond/dev/munbon2-backend"

echo "Updating EC2 IP from $OLD_IP to $NEW_IP..."

# Count occurrences
COUNT=$(grep -r "$OLD_IP" "$PROJECT_ROOT" --exclude-dir=node_modules --exclude-dir=.git --exclude="*.log" 2>/dev/null | wc -l | tr -d ' ')

if [ "$COUNT" -eq 0 ]; then
    echo "No occurrences of $OLD_IP found. The update may have already been completed."
    exit 0
fi

echo "Found $COUNT occurrences of $OLD_IP to update"
echo ""

# Update all files
echo "Updating files..."
find "$PROJECT_ROOT" -type f \( -name "*.env" -o -name "*.env.*" -o -name "*.sh" -o -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.md" -o -name "*.sql" -o -name "*.config.js" \) ! -path "*/node_modules/*" ! -path "*/.git/*" | while read -r file; do
    if grep -q "$OLD_IP" "$file" 2>/dev/null; then
        echo "  Updating: ${file#$PROJECT_ROOT/}"
        sed -i '' "s/$OLD_IP/$NEW_IP/g" "$file"
    fi
done

echo ""
echo "✅ Update complete!"
echo ""
echo "Summary:"
echo "  - Old IP: $OLD_IP"
echo "  - New IP: $NEW_IP"
echo ""
echo "Please:"
echo "1. Review changes with: git diff"
echo "2. Test database connections"
echo "3. Restart any running services"
echo "4. Commit when verified"
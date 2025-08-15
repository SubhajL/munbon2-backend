#!/bin/bash

# Script to update EC2 IP address from 43.209.22.250 to 43.209.22.250

set -e

OLD_IP="43.209.22.250"
NEW_IP="43.209.22.250"

echo "Updating EC2 IP from $OLD_IP to $NEW_IP"

# Find all files containing the old IP
echo "Finding files with old IP..."
FILES=$(grep -rl "$OLD_IP" /Users/subhajlimanond/dev/munbon2-backend/ --exclude-dir=node_modules --exclude-dir=.git --exclude="*.log" 2>/dev/null || true)

# Count files
FILE_COUNT=$(echo "$FILES" | wc -l)
echo "Found $FILE_COUNT files to update"

# Update each file
for file in $FILES; do
    if [ -f "$file" ]; then
        echo "Updating: $file"
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

echo "✅ IP update complete!"
echo ""
echo "⚠️  Don't forget to:"
echo "1. Update AWS Systems Manager Parameter Store"
echo "2. Update any AWS Lambda environment variables"
echo "3. Update GitHub secrets if needed"
echo "4. Update any DNS records pointing to the old IP"
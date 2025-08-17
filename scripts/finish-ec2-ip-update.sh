#!/bin/bash

# Simple script to finish updating EC2 IP addresses
OLD_IP="${EC2_HOST:-43.208.201.191}"
NEW_IP="${EC2_HOST:-43.208.201.191}"

echo "Finishing EC2 IP update from $OLD_IP to $NEW_IP..."

# Update remaining files
find . -type f \( -name "*.js" -o -name "*.ts" -o -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.env*" -o -name "*.md" -o -name "*.sql" -o -name "*.py" \) \
  -not -path "./node_modules/*" \
  -not -path "./.git/*" \
  -not -path "./services/*/node_modules/*" \
  -exec grep -l "$OLD_IP" {} \; | while read -r file; do
    echo "Updating: $file"
    if [[ "$OSTYPE" == "darwin"* ]]; then
      sed -i '' "s/$OLD_IP/$NEW_IP/g" "$file"
    else
      sed -i "s/$OLD_IP/$NEW_IP/g" "$file"
    fi
done

echo "Update complete!"
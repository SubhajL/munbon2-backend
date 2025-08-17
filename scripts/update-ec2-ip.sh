#!/bin/bash

# Update EC2 IP from old to new
OLD_IP="${EC2_HOST:-43.208.201.191}"  # Previous IP (already updated)
NEW_IP="${EC2_HOST:-43.208.201.191}"  # New IP

echo "Updating EC2 IP from $OLD_IP to $NEW_IP..."

# Find all files containing the old IP (excluding git files and this script)
FILES=$(grep -rl "$OLD_IP" . --exclude-dir=.git --exclude-dir=node_modules --exclude="update-ec2-ip.sh" 2>/dev/null)

if [ -z "$FILES" ]; then
  echo "No files found containing $OLD_IP"
  exit 0
fi

echo "Found $(echo "$FILES" | wc -l | tr -d ' ') files to update"

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

echo "Update complete!"

# Show summary of changes
echo -e "\nSummary of updated files:"
for file in $FILES; do
  if [ -f "$file" ]; then
    echo "  ✓ $file"
  fi
done

echo -e "\nPlease review the changes and test connections to ensure everything works correctly."
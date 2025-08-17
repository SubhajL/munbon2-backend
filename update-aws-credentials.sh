#!/bin/bash

# Script to update AWS credentials in all .env files

echo "AWS Credential Update Script"
echo "============================"
echo ""
echo "This script will help you update AWS credentials in all .env files"
echo "Make sure you have your new AWS Access Key ID and Secret Access Key ready"
echo ""

# Prompt for new credentials
read -p "Enter your NEW AWS Access Key ID: " NEW_AWS_ACCESS_KEY_ID
read -s -p "Enter your NEW AWS Secret Access Key: " NEW_AWS_SECRET_ACCESS_KEY
echo ""

# Find all .env files
ENV_FILES=$(find . -name ".env" -type f -not -path "*/node_modules/*" -not -path "*/venv/*" -not -path "*/docs/*")

echo ""
echo "Found the following .env files:"
echo "$ENV_FILES"
echo ""

# Create backup directory
mkdir -p .env-backups
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)

# Update each .env file
for file in $ENV_FILES; do
    if [ -f "$file" ]; then
        echo "Processing: $file"
        
        # Create backup
        cp "$file" ".env-backups/$(basename $file).backup.$BACKUP_DATE"
        
        # Update AWS credentials
        if grep -q "AWS_ACCESS_KEY_ID" "$file"; then
            # Use sed to update the credentials
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                sed -i '' "s/AWS_ACCESS_KEY_ID=.*/AWS_ACCESS_KEY_ID=$NEW_AWS_ACCESS_KEY_ID/" "$file"
                sed -i '' "s/AWS_SECRET_ACCESS_KEY=.*/AWS_SECRET_ACCESS_KEY=$NEW_AWS_SECRET_ACCESS_KEY/" "$file"
            else
                # Linux
                sed -i "s/AWS_ACCESS_KEY_ID=.*/AWS_ACCESS_KEY_ID=$NEW_AWS_ACCESS_KEY_ID/" "$file"
                sed -i "s/AWS_SECRET_ACCESS_KEY=.*/AWS_SECRET_ACCESS_KEY=$NEW_AWS_SECRET_ACCESS_KEY/" "$file"
            fi
            echo "✅ Updated AWS credentials in $file"
        else
            echo "⏭️  No AWS credentials found in $file"
        fi
    fi
done

echo ""
echo "✅ Local .env files updated!"
echo "📁 Backups saved in .env-backups/"
echo ""
echo "Next steps:"
echo "1. Update GitHub Actions secrets"
echo "2. Update Lambda environment variables"
echo "3. Test all services to ensure they work with new credentials"
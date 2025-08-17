#!/bin/bash

# Script to remove hardcoded AWS credentials from scripts

echo "Removing Hardcoded AWS Credentials"
echo "=================================="
echo ""
echo "Found hardcoded credentials in the following files:"
echo ""

# Files with hardcoded credentials
FILES_TO_UPDATE=(
    "./scripts/deploy-to-ec2-docker.sh"
    "./scripts/start-all-docker-services.sh"
    "./scripts/deploy-via-docker-commands.sh"
    "./scripts/deploy-all-services.sh"
)

# Old credentials to remove (found in your files)
OLD_ACCESS_KEY="AKIARSUGAPRU5GWX5G6I"
OLD_SECRET_KEY="eKb90hW6hXeuvPbEx7A1FjWEp+7VSVJV5YSXMHbc"

for file in "${FILES_TO_UPDATE[@]}"; do
    if [ -f "$file" ]; then
        echo "Updating: $file"
        
        # Replace with environment variable references
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/AWS_ACCESS_KEY_ID=$OLD_ACCESS_KEY/AWS_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID/" "$file"
            sed -i '' "s/AWS_SECRET_ACCESS_KEY=$OLD_SECRET_KEY/AWS_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY/" "$file"
            sed -i '' "s/-e AWS_ACCESS_KEY_ID=$OLD_ACCESS_KEY/-e AWS_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID/" "$file"
            sed -i '' "s/-e AWS_SECRET_ACCESS_KEY=$OLD_SECRET_KEY/-e AWS_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY/" "$file"
        else
            # Linux
            sed -i "s/AWS_ACCESS_KEY_ID=$OLD_ACCESS_KEY/AWS_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID/" "$file"
            sed -i "s/AWS_SECRET_ACCESS_KEY=$OLD_SECRET_KEY/AWS_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY/" "$file"
            sed -i "s/-e AWS_ACCESS_KEY_ID=$OLD_ACCESS_KEY/-e AWS_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID/" "$file"
            sed -i "s/-e AWS_SECRET_ACCESS_KEY=$OLD_SECRET_KEY/-e AWS_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY/" "$file"
        fi
        
        echo "✅ Removed hardcoded credentials from $file"
    fi
done

echo ""
echo "✅ Hardcoded credentials removed!"
echo ""
echo "These scripts now expect AWS credentials from environment variables."
echo "Before running these scripts, make sure to export your credentials:"
echo ""
echo "export AWS_ACCESS_KEY_ID=your-new-access-key"
echo "export AWS_SECRET_ACCESS_KEY=your-new-secret-key"
#!/bin/bash

# Script to update all hardcoded EC2 IPs to use environment variables
# This makes future IP changes easier - just update .env file

echo "EC2 IP Migration Script"
echo "======================"
echo ""
echo "This script will update all hardcoded EC2 IPs to use environment variables"
echo ""

# Old and new IPs
OLD_IP="${EC2_HOST:-43.208.201.191}"
NEW_IP="43.208.201.191"

# Source the .env file to get EC2_HOST
if [ -f .env ]; then
    export $(grep -E '^EC2_HOST=' .env | xargs)
    echo "Using EC2_HOST from .env: $EC2_HOST"
else
    echo "Warning: .env file not found"
    EC2_HOST=$NEW_IP
fi

# Find all files with the old IP (excluding .git, node_modules, venv, docs)
echo ""
echo "Finding files with hardcoded IP $OLD_IP..."
FILES=$(grep -r "$OLD_IP" . \
    --exclude-dir=.git \
    --exclude-dir=node_modules \
    --exclude-dir=venv \
    --exclude-dir=test-venv \
    --exclude-dir=test_venv \
    --exclude-dir=docs \
    --exclude-dir=.env-backups \
    --exclude="*.log" \
    --exclude="*.pyc" \
    -l)

if [ -z "$FILES" ]; then
    echo "No files found with IP $OLD_IP"
else
    echo "Found $(echo "$FILES" | wc -l) files with hardcoded IP"
    echo ""
    
    # Update each file
    for file in $FILES; do
        echo "Updating: $file"
        
        # Determine file type and update accordingly
        case "$file" in
            *.sh|*.bash)
                # For shell scripts, use environment variable
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    sed -i '' "s/$OLD_IP/\${EC2_HOST:-$NEW_IP}/g" "$file"
                else
                    sed -i "s/$OLD_IP/\${EC2_HOST:-$NEW_IP}/g" "$file"
                fi
                ;;
            *.ts|*.js)
                # For TypeScript/JavaScript, use process.env
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    sed -i '' "s/'$OLD_IP'/process.env.EC2_HOST || '$NEW_IP'/g" "$file"
                    sed -i '' "s/\"$OLD_IP\"/process.env.EC2_HOST || \"$NEW_IP\"/g" "$file"
                else
                    sed -i "s/'$OLD_IP'/process.env.EC2_HOST || '$NEW_IP'/g" "$file"
                    sed -i "s/\"$OLD_IP\"/process.env.EC2_HOST || \"$NEW_IP\"/g" "$file"
                fi
                ;;
            *.py)
                # For Python, use os.environ
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    sed -i '' "s/'$OLD_IP'/os.environ.get('EC2_HOST', '$NEW_IP')/g" "$file"
                    sed -i '' "s/\"$OLD_IP\"/os.environ.get('EC2_HOST', '$NEW_IP')/g" "$file"
                else
                    sed -i "s/'$OLD_IP'/os.environ.get('EC2_HOST', '$NEW_IP')/g" "$file"
                    sed -i "s/\"$OLD_IP\"/os.environ.get('EC2_HOST', '$NEW_IP')/g" "$file"
                fi
                ;;
            *.yml|*.yaml|*.json|*.env|*.md)
                # For config files and markdown, just update the IP
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    sed -i '' "s/$OLD_IP/$NEW_IP/g" "$file"
                else
                    sed -i "s/$OLD_IP/$NEW_IP/g" "$file"
                fi
                ;;
            *)
                # For other files, just update the IP
                if [[ "$OSTYPE" == "darwin"* ]]; then
                    sed -i '' "s/$OLD_IP/$NEW_IP/g" "$file"
                else
                    sed -i "s/$OLD_IP/$NEW_IP/g" "$file"
                fi
                ;;
        esac
    done
fi

echo ""
echo "Creating service environment setup script..."

# Create a script to help services load EC2 configuration
cat > load-ec2-config.sh << 'EOF'
#!/bin/bash
# Source this file in your scripts to get EC2 configuration
# Usage: source ./load-ec2-config.sh

# Load from .env file if it exists
if [ -f .env ]; then
    export $(grep -E '^EC2_HOST=|^POSTGRES_|^TIMESCALE_|^DATABASE_URL=|^TIMESCALE_URL=' .env | xargs)
fi

# Set defaults if not already set
export EC2_HOST="${EC2_HOST:-43.208.201.191}"
export EC2_SSH_USER="${EC2_SSH_USER:-ubuntu}"
export EC2_SSH_KEY_PATH="${EC2_SSH_KEY_PATH:-./th-lab01.pem}"

# Database configurations
export POSTGRES_HOST="${POSTGRES_HOST:-$EC2_HOST}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_DB="${POSTGRES_DB:-munbon_dev}"

export TIMESCALE_HOST="${TIMESCALE_HOST:-$EC2_HOST}"
export TIMESCALE_PORT="${TIMESCALE_PORT:-5432}"
export TIMESCALE_USER="${TIMESCALE_USER:-postgres}"
export TIMESCALE_DB="${TIMESCALE_DB:-sensor_data}"

# URLs
export DATABASE_URL="${DATABASE_URL:-postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB}"
export TIMESCALE_URL="${TIMESCALE_URL:-postgresql://$TIMESCALE_USER:$TIMESCALE_PASSWORD@$TIMESCALE_HOST:$TIMESCALE_PORT/$TIMESCALE_DB}"

echo "EC2 Configuration Loaded:"
echo "  EC2_HOST: $EC2_HOST"
echo "  POSTGRES_HOST: $POSTGRES_HOST"
echo "  TIMESCALE_HOST: $TIMESCALE_HOST"
EOF

chmod +x load-ec2-config.sh

echo ""
echo "✅ Update complete!"
echo ""
echo "Next steps:"
echo "1. Review the changes"
echo "2. Test database connections"
echo "3. Update any service-specific .env files to use \${EC2_HOST}"
echo "4. Use 'source ./load-ec2-config.sh' in scripts to load EC2 configuration"
echo ""
echo "To change EC2 IP in the future, just update EC2_HOST in .env file!"
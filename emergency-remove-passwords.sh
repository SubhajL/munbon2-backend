#!/bin/bash

echo "Emergency Password Removal Script"
echo "================================="
echo ""
echo "This will remove all .env files and update configurations to use environment variables"
echo ""

# Remove all .env files
echo "Removing all .env files..."
find . -name ".env*" -type f -not -path "./node_modules/*" -not -path "./venv/*" -not -path "./docs/*" -delete

# Update .gitignore to ensure .env files are ignored
echo "Updating .gitignore..."
if ! grep -q "^\\.env\*$" .gitignore; then
    echo -e "\n# Ignore ALL .env files\n.env*\n!.env.example\n!.env.template" >> .gitignore
fi

# Create a secure configuration loader
cat > load-credentials.sh << 'EOF'
#!/bin/bash
# Source this file to load credentials from environment
# Usage: source ./load-credentials.sh

echo "Loading credentials from environment..."
echo "Make sure you have set:"
echo "  export POSTGRES_PASSWORD='your-password'"
echo "  export JWT_SECRET='your-jwt-secret'"
echo "  export REDIS_PASSWORD='your-redis-password'"

# Database configurations use environment variables
export DATABASE_URL="postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD}@${EC2_HOST:-43.208.201.191}:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-munbon_dev}"
export TIMESCALE_URL="postgresql://${TIMESCALE_USER:-postgres}:${POSTGRES_PASSWORD}@${EC2_HOST:-43.208.201.191}:${TIMESCALE_PORT:-5432}/${TIMESCALE_DB:-sensor_data}"
EOF

chmod +x load-credentials.sh

echo ""
echo "✅ Removed all .env files containing passwords"
echo "✅ Updated .gitignore"
echo ""
echo "NEXT STEPS:"
echo "1. Change your PostgreSQL password on EC2"
echo "2. Set environment variables locally:"
echo "   export POSTGRES_PASSWORD='new-password'"
echo "3. Commit these changes"
echo "4. Use GitHub Secrets for CI/CD"
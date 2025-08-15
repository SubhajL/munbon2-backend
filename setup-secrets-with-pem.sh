#!/bin/bash

# Setup GitHub secrets for EC2 deployment using th-lab01.pem

echo "=== GitHub Secrets Setup for EC2 Deployment ==="
echo ""

# Configuration
REPO="SubhajL/munbon2-backend"
EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"
PEM_FILE="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"

# Check if PEM file exists
if [ ! -f "$PEM_FILE" ]; then
    echo "❌ PEM file not found at: $PEM_FILE"
    echo "Looking for th-lab01.pem in other locations..."
    PEM_FILE="/Users/subhajlimanond/dev/th-lab01.pem"
    if [ ! -f "$PEM_FILE" ]; then
        echo "❌ PEM file not found. Please provide the correct path."
        exit 1
    fi
fi

echo "✅ Found PEM file at: $PEM_FILE"
echo ""

# Check if gh CLI is authenticated
echo "Checking GitHub CLI authentication..."
gh auth status 2>/dev/null
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ GitHub CLI is not authenticated."
    echo ""
    echo "Please run: gh auth login"
    echo "Then run this script again."
    echo ""
    echo "Alternatively, you can set the secrets manually:"
    echo ""
    echo "1. Go to: https://github.com/$REPO/settings/secrets/actions"
    echo "2. Click 'New repository secret' and add:"
    echo "   - Name: EC2_HOST"
    echo "   - Value: $EC2_HOST"
    echo ""
    echo "3. Click 'New repository secret' and add:"
    echo "   - Name: EC2_USER"
    echo "   - Value: $EC2_USER"
    echo ""
    echo "4. Click 'New repository secret' and add:"
    echo "   - Name: EC2_SSH_KEY"
    echo "   - Value: (paste the contents of $PEM_FILE)"
    echo ""
    echo "To view the PEM file contents:"
    echo "cat $PEM_FILE"
    exit 1
fi

echo "✅ GitHub CLI is authenticated"
echo ""

# Set secrets
echo "Setting GitHub secrets..."
echo ""

# Set EC2_HOST
echo -n "Setting EC2_HOST... "
echo "$EC2_HOST" | gh secret set EC2_HOST -R "$REPO"
if [ $? -eq 0 ]; then
    echo "✅"
else
    echo "❌"
fi

# Set EC2_USER
echo -n "Setting EC2_USER... "
echo "$EC2_USER" | gh secret set EC2_USER -R "$REPO"
if [ $? -eq 0 ]; then
    echo "✅"
else
    echo "❌"
fi

# Set EC2_SSH_KEY
echo -n "Setting EC2_SSH_KEY... "
cat "$PEM_FILE" | gh secret set EC2_SSH_KEY -R "$REPO"
if [ $? -eq 0 ]; then
    echo "✅"
else
    echo "❌"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Secrets configured:"
echo "- EC2_HOST: $EC2_HOST"
echo "- EC2_USER: $EC2_USER"
echo "- EC2_SSH_KEY: Set from $PEM_FILE"
echo ""
echo "Next steps:"
echo "1. Push to main branch to trigger deployment:"
echo "   git push origin main"
echo ""
echo "2. Monitor deployment at:"
echo "   https://github.com/$REPO/actions"
echo ""
echo "3. Or trigger manually:"
echo "   gh workflow run 'Deploy to EC2 with Docker' -R $REPO"
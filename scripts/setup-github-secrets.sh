#!/bin/bash

# Setup GitHub secrets for EC2 deployment

echo "=== Setting up GitHub Secrets for EC2 Deployment ==="
echo ""
echo "This script will help you set up the required GitHub secrets."
echo ""

# Configuration
REPO="SubhajL/munbon2-backend"
EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"  # Default user for Ubuntu EC2 instances

echo "Repository: $REPO"
echo "EC2 Host: $EC2_HOST"
echo "EC2 User: $EC2_USER"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed."
    echo "Please install it first:"
    echo "  brew install gh"
    echo "  or visit: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
gh auth status 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Not authenticated with GitHub."
    echo "Please run: gh auth login"
    exit 1
fi

echo "✅ GitHub CLI is installed and authenticated"
echo ""

# Function to set secret
set_secret() {
    local name=$1
    local value=$2
    echo -n "Setting $name... "
    echo "$value" | gh secret set "$name" -R "$REPO"
    if [ $? -eq 0 ]; then
        echo "✅"
    else
        echo "❌"
    fi
}

# Set EC2_HOST
set_secret "EC2_HOST" "$EC2_HOST"

# Set EC2_USER
set_secret "EC2_USER" "$EC2_USER"

# Set EC2_SSH_KEY
echo ""
echo "For EC2_SSH_KEY, you need to provide the private SSH key content."
echo "If you have SSH access to the EC2 instance, please provide the path to your private key."
echo ""
read -p "Path to your EC2 SSH private key (or press Enter to skip): " SSH_KEY_PATH

if [ -n "$SSH_KEY_PATH" ] && [ -f "$SSH_KEY_PATH" ]; then
    echo -n "Setting EC2_SSH_KEY... "
    cat "$SSH_KEY_PATH" | gh secret set "EC2_SSH_KEY" -R "$REPO"
    if [ $? -eq 0 ]; then
        echo "✅"
    else
        echo "❌"
    fi
else
    echo "⚠️  Skipping EC2_SSH_KEY. You'll need to set this manually in GitHub."
    echo ""
    echo "To set it manually:"
    echo "1. Go to https://github.com/$REPO/settings/secrets/actions"
    echo "2. Click 'New repository secret'"
    echo "3. Name: EC2_SSH_KEY"
    echo "4. Value: Paste your entire private key content"
fi

echo ""
echo "=== GitHub Secrets Setup Complete ==="
echo ""
echo "Secrets configured:"
echo "- EC2_HOST: $EC2_HOST"
echo "- EC2_USER: $EC2_USER"
echo "- EC2_SSH_KEY: $([ -n "$SSH_KEY_PATH" ] && echo "✅ Set" || echo "❌ Not set")"
echo ""
echo "Next steps:"
echo "1. If EC2_SSH_KEY is not set, add it manually in GitHub settings"
echo "2. Trigger the deployment workflow:"
echo "   - Push to main branch, or"
echo "   - Go to Actions tab and manually trigger 'Deploy to EC2 with Docker'"
echo ""
echo "Alternative: Trigger deployment now with:"
echo "gh workflow run 'Deploy to EC2 with Docker' -R $REPO"
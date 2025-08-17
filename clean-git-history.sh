#!/bin/bash

echo "⚠️  WARNING: This script will rewrite git history to remove sensitive files"
echo "⚠️  This is a DESTRUCTIVE operation. Make sure you have a backup!"
echo ""
echo "This script will remove the following from git history:"
echo "- All .env files"
echo "- All .pem, .key files"
echo "- Files containing passwords"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo "Creating backup branch..."
git branch backup-before-cleanup

echo "Installing git-filter-repo if not present..."
if ! command -v git-filter-repo &> /dev/null; then
    echo "Please install git-filter-repo first:"
    echo "brew install git-filter-repo"
    exit 1
fi

echo "Removing sensitive files from history..."

# Create a file with paths to remove
cat > paths-to-remove.txt << 'EOF'
.env
**/.env
**/*.env
.env.*
*.pem
**/*.pem
*.key
**/*.key
th-lab01.pem
.aws/
aws-exports.js
credentials
.aws-credentials
*.sql
*.dump
EXPOSED_CREDENTIALS_LIST.md
EOF

# Remove files from history
git filter-repo --invert-paths --paths-from-file paths-to-remove.txt --force

# Clean up
rm paths-to-remove.txt

echo ""
echo "✅ Git history cleaned!"
echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "1. Force push to remote: git push --force-with-lease origin main"
echo "2. All team members must delete their local repos and clone fresh"
echo "3. Immediately rotate all exposed credentials"
echo "4. Check GitHub's 'Settings > Security > Secrets scanning' for any alerts"
echo ""
echo "Your old history is saved in branch: backup-before-cleanup"
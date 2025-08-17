#!/bin/bash

# Trigger EC2 deployment via GitHub Actions

echo "=== Triggering EC2 Deployment via GitHub Actions ==="
echo ""

# Since we just pushed to main, the workflow should trigger automatically
echo "The deployment workflow should have been triggered automatically by the push to main."
echo ""
echo "To check the workflow status:"
echo "1. Go to: https://github.com/SubhajL/munbon2-backend/actions"
echo "2. Look for 'Deploy to EC2 with Docker' workflow"
echo ""
echo "If the workflow hasn't started or you need to run it manually:"
echo "1. Go to: https://github.com/SubhajL/munbon2-backend/actions/workflows/deploy-ec2.yml"
echo "2. Click 'Run workflow' button"
echo "3. Select 'main' branch"
echo "4. Click 'Run workflow'"
echo ""
echo "Note: You need to set up these GitHub secrets first:"
echo "- EC2_HOST: ${EC2_HOST:-43.208.201.191}"
echo "- EC2_USER: ubuntu (or your EC2 username)"
echo "- EC2_SSH_KEY: Your private SSH key content"
echo ""
echo "To add secrets:"
echo "1. Go to: https://github.com/SubhajL/munbon2-backend/settings/secrets/actions"
echo "2. Click 'New repository secret' for each secret"
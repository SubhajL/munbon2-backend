#!/bin/bash
# This script helps encode your SSH key for GitHub Secrets

echo "Encode your SSH key for GitHub Secrets"
echo "======================================"
echo ""
echo "1. First, base64 encode your key:"
echo "   base64 -i th-lab01.pem | tr -d '\n'"
echo ""
echo "2. Copy the output and update EC2_SSH_KEY secret in GitHub"
echo ""
echo "3. The workflow will decode it automatically"
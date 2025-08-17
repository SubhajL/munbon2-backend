#!/bin/bash
set -euo pipefail

# Script to rotate SSH keys for EC2 instance
# Run this IMMEDIATELY as the current key was exposed

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}=== URGENT: SSH Key Rotation ===${NC}"
echo -e "${RED}The current SSH key was exposed in documentation!${NC}"
echo

# Check if we have AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${YELLOW}AWS CLI not found. Manual steps required:${NC}"
    echo
    echo "1. Generate new key pair:"
    echo "   ssh-keygen -t ed25519 -f ./munbon-new-key -C 'munbon-deploy'"
    echo
    echo "2. On EC2 instance (using current compromised key):"
    echo "   ssh -i th-lab01.pem ubuntu@${EC2_HOST:-43.208.201.191}"
    echo "   echo 'YOUR_NEW_PUBLIC_KEY' >> ~/.ssh/authorized_keys"
    echo
    echo "3. Test new key:"
    echo "   ssh -i munbon-new-key ubuntu@${EC2_HOST:-43.208.201.191}"
    echo
    echo "4. Remove old key from EC2:"
    echo "   # Edit ~/.ssh/authorized_keys and remove old key"
    echo
    echo "5. Update GitHub Secrets with new private key"
    exit 1
fi

# Generate new key pair
echo -e "${YELLOW}Generating new SSH key pair...${NC}"
KEY_NAME="munbon-deploy-$(date +%Y%m%d)"
ssh-keygen -t ed25519 -f "./$KEY_NAME" -C "munbon-deploy" -N ""

echo -e "${GREEN}New key pair generated:${NC}"
echo "Private key: $KEY_NAME"
echo "Public key: $KEY_NAME.pub"

# Show public key
echo
echo -e "${YELLOW}Public key content:${NC}"
cat "$KEY_NAME.pub"

# Instructions for manual update
echo
echo -e "${YELLOW}=== Manual Steps Required ===${NC}"
echo
echo "1. Add new public key to EC2:"
echo "   ssh -i th-lab01.pem ubuntu@${EC2_HOST:-43.208.201.191}"
echo "   echo '$(cat "$KEY_NAME.pub")' >> ~/.ssh/authorized_keys"
echo
echo "2. Test new key:"
echo "   ssh -i $KEY_NAME ubuntu@${EC2_HOST:-43.208.201.191} 'echo Success!'"
echo
echo "3. Remove old key from EC2:"
echo "   ssh -i $KEY_NAME ubuntu@${EC2_HOST:-43.208.201.191}"
echo "   # Edit ~/.ssh/authorized_keys and remove the old RSA key"
echo
echo "4. Update GitHub Secret EC2_SSH_KEY:"
echo "   cat $KEY_NAME | base64 | pbcopy"
echo "   # Paste in GitHub Settings → Secrets → EC2_SSH_KEY"
echo
echo "5. Delete old key file:"
echo "   rm -f th-lab01.pem"
echo
echo -e "${RED}IMPORTANT: Complete these steps immediately!${NC}"
#!/bin/bash

echo "=== GitHub Actions Deployment Fix ==="
echo ""
echo "Common failure reasons and fixes:"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${YELLOW}1. Check if GitHub Secrets are set:${NC}"
echo "   Go to: https://github.com/SubhajL/munbon2-backend/settings/secrets/actions"
echo "   You should see:"
echo "   - EC2_HOST"
echo "   - EC2_USER"
echo "   - EC2_SSH_KEY"
echo ""

echo -e "${YELLOW}2. If secrets are missing, add them:${NC}"
echo ""
echo "   ${BLUE}EC2_HOST:${NC} ${EC2_HOST:-43.208.201.191}"
echo "   ${BLUE}EC2_USER:${NC} ubuntu"
echo "   ${BLUE}EC2_SSH_KEY:${NC} Copy entire content from th-lab01.pem including:"
echo "   -----BEGIN RSA PRIVATE KEY-----"
echo "   [key content]"
echo "   -----END RSA PRIVATE KEY-----"
echo ""

echo -e "${YELLOW}3. Test SSH connection locally:${NC}"
echo "   ssh -i th-lab01.pem ubuntu@${EC2_HOST:-43.208.201.191}"
echo ""

echo -e "${YELLOW}4. Manual deployment option:${NC}"
echo "   If GitHub Actions keeps failing, deploy manually:"
echo ""
cat << 'EOF'
# SSH to EC2
ssh -i th-lab01.pem ubuntu@${EC2_HOST:-43.208.201.191}

# Once connected, run:
cd munbon2-backend
git pull origin main
cp .env.ec2 .env
docker-compose -f docker-compose.ec2-consolidated.yml down
docker-compose -f docker-compose.ec2-consolidated.yml up -d --build
docker-compose -f docker-compose.ec2-consolidated.yml ps
EOF

echo ""
echo -e "${YELLOW}5. Check GitHub Actions logs:${NC}"
echo "   1. Go to: https://github.com/SubhajL/munbon2-backend/actions"
echo "   2. Click on the failed workflow"
echo "   3. Click on 'deploy' job"
echo "   4. Look for error messages like:"
echo "      - 'Error: Input required and not supplied: key'"
echo "      - 'Permission denied (publickey)'"
echo "      - 'Host key verification failed'"
echo ""

echo -e "${YELLOW}6. After adding secrets, trigger deployment:${NC}"
echo "   Option A: Push a small change"
echo "   git add . && git commit -m 'Trigger deployment' && git push"
echo ""
echo "   Option B: Manually trigger workflow"
echo "   - Go to Actions tab"
echo "   - Click 'Deploy to EC2 with Docker'"
echo "   - Click 'Run workflow' button"
echo ""

echo -e "${GREEN}Quick Manual Deployment Script:${NC}"
echo "Copy and run this on EC2:"
echo ""
echo '#!/bin/bash'
echo 'cd ~/munbon2-backend'
echo 'git pull origin main'
echo 'cp .env.ec2 .env'
echo 'docker-compose -f docker-compose.ec2-consolidated.yml down'
echo 'docker-compose -f docker-compose.ec2-consolidated.yml up -d --build'
echo 'sleep 30'
echo 'docker-compose -f docker-compose.ec2-consolidated.yml ps'
echo 'echo "Checking consumer logs..."'
echo 'docker-compose -f docker-compose.ec2-consolidated.yml logs --tail 50 sensor-data-consumer'
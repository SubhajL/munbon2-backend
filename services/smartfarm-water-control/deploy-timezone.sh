#!/bin/bash
set -e

echo "============================================"
echo "Deploying Timezone Conversion to Production"
echo "============================================"
echo ""

# Configuration
SERVER="43.208.201.191"
USER="ubuntu"
APP_PATH="/home/ubuntu/munbon2-backend-smartfarm/services/smartfarm-water-control"

echo "Server: $SERVER"
echo "User: $USER"
echo "Path: $APP_PATH"
echo ""

# Check if we can connect
echo "Checking SSH connection..."
ssh -o ConnectTimeout=5 $USER@$SERVER "echo 'SSH connection successful'" || {
    echo "ERROR: Cannot connect to server"
    echo "Please check:"
    echo "  1. Server is running"
    echo "  2. You have SSH key configured"
    echo "  3. Run: ssh-add ~/.ssh/your-key.pem"
    exit 1
}

echo ""
echo "Deploying changes..."
ssh $USER@$SERVER << 'ENDSSH'
set -e

# Navigate to app directory
cd /home/ubuntu/munbon2-backend-smartfarm/services/smartfarm-water-control || {
    echo "ERROR: Application directory not found"
    echo "Please provide the correct path where smartfarm-water-control is deployed"
    exit 1
}

echo "Current directory: $(pwd)"
echo ""

# Backup current version
echo "Creating backup..."
git branch backup-before-timezone-$(date +%Y%m%d-%H%M%S) 2>/dev/null || echo "Warning: Could not create backup branch"

# Pull latest changes
echo "Pulling latest changes..."
git fetch origin
git checkout feature/smartfarm-debug
git pull origin feature/smartfarm-debug

# Check if timezone files exist
echo ""
echo "Verifying timezone files..."
if [ -f "src/utils/timezone.js" ]; then
    echo "✓ src/utils/timezone.js exists"
else
    echo "✗ ERROR: src/utils/timezone.js not found!"
    exit 1
fi

# Test timezone conversion
echo ""
echo "Testing timezone conversion..."
node test-timezone-conversion.js || {
    echo "ERROR: Timezone test failed"
    exit 1
}

# Find and restart the process
echo ""
echo "Restarting service..."

# Check if PM2 is being used
if command -v pm2 &> /dev/null; then
    echo "Using PM2 to restart..."
    pm2 restart smartfarm-water-control || pm2 restart all
elif systemctl list-units --type=service | grep -q smartfarm; then
    echo "Using systemd to restart..."
    sudo systemctl restart smartfarm-water-control
else
    echo "Looking for running process..."
    if pkill -f "node.*smartfarm-water-control\|node.*listen-worker"; then
        echo "Killed existing process"
        sleep 2
        # Start in background
        nohup npm run worker > logs/worker.log 2>&1 &
        echo "Started new worker process"
    else
        echo "WARNING: No running process found - you may need to start it manually"
    fi
fi

# Wait a bit for restart
sleep 3

# Check if process is running
echo ""
echo "Checking process status..."
if pgrep -f "node.*smartfarm-water-control\|node.*listen-worker" > /dev/null; then
    echo "✓ Service is running"
    ps aux | grep -E "smartfarm-water-control|listen-worker" | grep -v grep
else
    echo "⚠ WARNING: Could not detect running process"
    echo "Please check logs and start manually if needed"
fi

echo ""
echo "============================================"
echo "Deployment Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Monitor the logs for any errors"
echo "2. Wait for next valve command"
echo "3. Check MSSQL - timestamps should be UTC+7"
echo ""
echo "To verify in MSSQL:"
echo "  SELECT TOP 5 id, valve_name, startdatetime"
echo "  FROM tb_valve_command_v2_test"
echo "  ORDER BY id DESC"
echo ""

ENDSSH

echo ""
echo "Deployment script finished!"
echo ""
echo "To monitor logs, run:"
echo "  ssh $USER@$SERVER 'tail -f /home/ubuntu/munbon2-backend-smartfarm/services/smartfarm-water-control/logs/*.log'"

#!/bin/bash

echo "=================================================="
echo "EC2 HTTP 8080 Log Analysis for Gateway 0001"
echo "=================================================="
echo ""

EC2_HOST="43.208.201.191"
SSH_KEY="$HOME/.ssh/munbon-ec2.pem"

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ SSH key not found at $SSH_KEY"
    echo "Please provide the correct path to your EC2 SSH key"
    exit 1
fi

echo "Connecting to EC2 instance: $EC2_HOST"
echo ""

# Function to run remote commands
run_remote() {
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@$EC2_HOST "$1" 2>/dev/null
}

echo "1. Checking PM2 processes"
echo "-----------------------------------------------------------"
run_remote "pm2 list" || echo "⚠️  PM2 not available or connection failed"

echo ""
echo "2. Finding moisture HTTP service logs"
echo "-----------------------------------------------------------"
run_remote "ls -lh /var/log/*moisture* 2>/dev/null" || echo "No logs in /var/log/"
run_remote "ls -lh ~/.pm2/logs/*moisture* 2>/dev/null | head -10" || echo "No PM2 logs found"

echo ""
echo "3. Checking systemd journal for moisture service"
echo "-----------------------------------------------------------"
run_remote "sudo journalctl -u moisture-http -n 50 --no-pager 2>/dev/null | tail -20" || echo "No systemd service logs"

echo ""
echo "4. Searching PM2 logs for gateway 0001 (last 100 lines)"
echo "-----------------------------------------------------------"
run_remote "tail -100 ~/.pm2/logs/*moisture*out*.log 2>/dev/null | grep -E '(0001|gateway_id|gw_id)' | tail -20" || echo "No gateway 0001 found in recent logs"

echo ""
echo "5. Searching PM2 error logs for gateway 0001"
echo "-----------------------------------------------------------"
run_remote "tail -100 ~/.pm2/logs/*moisture*error*.log 2>/dev/null | grep -E '(0001|gateway_id|gw_id|error)' | tail -20" || echo "No errors related to gateway 0001"

echo ""
echo "6. Checking last 200 lines for ANY gateway activity"
echo "-----------------------------------------------------------"
run_remote "tail -200 ~/.pm2/logs/*moisture*out*.log 2>/dev/null | grep -E '(gateway_id|gw_id)' | tail -30" || echo "No gateway data found"

echo ""
echo "7. Counting gateway mentions in recent logs"
echo "-----------------------------------------------------------"
run_remote "tail -1000 ~/.pm2/logs/*moisture*out*.log 2>/dev/null | grep -c 'gw_id.*0001'" && echo "mentions of gateway 0001"
run_remote "tail -1000 ~/.pm2/logs/*moisture*out*.log 2>/dev/null | grep -c 'gw_id.*0002'" && echo "mentions of gateway 0002"

echo ""
echo "8. Checking HTTP access logs (nginx/apache if available)"
echo "-----------------------------------------------------------"
run_remote "sudo tail -100 /var/log/nginx/access.log 2>/dev/null | grep -E '8080|moisture' | tail -10" || echo "No nginx logs"
run_remote "sudo tail -100 /var/log/apache2/access.log 2>/dev/null | grep -E '8080|moisture' | tail -10" || echo "No apache logs"

echo ""
echo "9. Check service status"
echo "-----------------------------------------------------------"
run_remote "sudo systemctl status moisture-http 2>/dev/null | head -20" || echo "Not a systemd service"

echo ""
echo "10. Last incoming requests (if service logs HTTP requests)"
echo "-----------------------------------------------------------"
run_remote "tail -500 ~/.pm2/logs/*moisture*out*.log 2>/dev/null | grep -E 'POST.*moisture|Received.*moisture' | tail -20" || echo "No HTTP request logs found"

echo ""
echo "=================================================="
echo "Alternative: Check Application Logs Directly"
echo "=================================================="
echo ""
echo "If PM2 logs aren't showing data, try these commands on EC2:"
echo ""
echo "  # Find the actual log file"
echo "  ubuntu@ec2: find /var/log -name '*moisture*' -o -name '*8080*'"
echo "  ubuntu@ec2: find ~ -name '*.log' | grep moisture"
echo ""
echo "  # Check PM2 logs"
echo "  ubuntu@ec2: pm2 logs moisture-http --lines 100"
echo ""
echo "  # Check if service is even running"
echo "  ubuntu@ec2: sudo netstat -tlnp | grep 8080"
echo "  ubuntu@ec2: curl http://localhost:8080/health"
echo ""

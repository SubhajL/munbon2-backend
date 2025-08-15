#!/bin/bash

# Expert-level debugging strategy for missing moisture data

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="43.209.22.250"

echo "=== EXPERT-LEVEL DEBUGGING STRATEGY ==="
echo "Date: $(date)"
echo "======================================"
echo ""

# 1. NETWORK LAYER ANALYSIS
echo "1. NETWORK LAYER - PACKET CAPTURE ANALYSIS:"
echo "==========================================="
echo "Setting up tcpdump to capture ALL traffic to port 8080..."
ssh -i $SSH_KEY ubuntu@$EC2_HOST "sudo timeout 60 tcpdump -i any -w /tmp/moisture-capture.pcap port 8080 -c 1000 2>/dev/null && echo 'Capture complete' || echo 'No traffic captured'"

echo ""
echo "Analyzing capture for HTTP POST requests:"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "sudo tcpdump -r /tmp/moisture-capture.pcap -A 2>/dev/null | grep -E 'POST|gw_id|sensor_id' | head -20 || echo 'No moisture data in packet capture'"

# 2. NGINX/REVERSE PROXY LOGS
echo ""
echo "2. CHECKING FOR NGINX/APACHE ACCESS LOGS:"
echo "=========================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "ls -la /var/log/nginx/access.log /var/log/apache2/access.log 2>/dev/null || echo 'No web server logs found'"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "sudo grep -E '8080|moisture' /var/log/nginx/access.log 2>/dev/null | tail -10 || echo 'No nginx logs'"

# 3. SYSTEM-LEVEL MONITORING
echo ""
echo "3. SYSTEM METRICS DURING DATA GAPS:"
echo "===================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "dmesg | grep -E 'Out of memory|killed process' | tail -5 || echo 'No OOM events'"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "free -h && echo '' && df -h /"

# 4. IPTABLES/FIREWALL RULES
echo ""
echo "4. FIREWALL ANALYSIS:"
echo "====================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "sudo iptables -L -n -v | grep -E '8080|REJECT|DROP' || echo 'No blocking rules for port 8080'"

# 5. CONNECTION TRACKING
echo ""
echo "5. ACTIVE CONNECTIONS TO PORT 8080:"
echo "==================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "sudo ss -tnp | grep :8080 || echo 'No active connections to port 8080'"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "sudo netstat -an | grep :8080 | grep -c ESTABLISHED || echo '0'"

# 6. DNS RESOLUTION CHECK
echo ""
echo "6. DNS RESOLUTION TEST:"
echo "======================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "nslookup $EC2_HOST || echo 'DNS lookup failed'"
echo "Reverse DNS:"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "nslookup 43.209.22.250 || echo 'Reverse DNS lookup failed'"

# 7. APPLICATION METRICS
echo ""
echo "7. NODE.JS PROCESS ANALYSIS:"
echo "============================"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "ps aux | grep 'moisture-http' | grep -v grep"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "sudo lsof -p \$(pgrep -f moisture-http) 2>/dev/null | grep -E 'LISTEN|ESTABLISHED' | head -10"

# 8. RATE LIMITING CHECK
echo ""
echo "8. RATE LIMITING ANALYSIS:"
echo "=========================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "sudo grep -i 'rate' /etc/nginx/nginx.conf /etc/nginx/sites-enabled/* 2>/dev/null || echo 'No rate limiting in nginx'"

# 9. SECURITY GROUP ANALYSIS
echo ""
echo "9. AWS SECURITY GROUP RULES:"
echo "============================"
aws ec2 describe-security-groups --filters "Name=ip-permission.from-port,Values=8080" --query 'SecurityGroups[*].[GroupId,GroupName,IpPermissions[?FromPort==`8080`]]' 2>/dev/null || echo "Cannot check security groups"

# 10. FAILED CONNECTION ATTEMPTS
echo ""
echo "10. FAILED CONNECTION ANALYSIS:"
echo "==============================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "sudo journalctl -u ssh -n 100 | grep -i 'failed\\|error' | grep -v 'pam_unix' | tail -5 || echo 'No SSH errors'"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "sudo grep -i 'connection reset\\|timeout' /var/log/syslog | tail -10 || echo 'No connection errors in syslog'"

echo ""
echo "=== RECOMMENDATIONS ==="
echo "1. Install request-level logging with unique request IDs"
echo "2. Add prometheus metrics for every HTTP request"
echo "3. Implement webhook to notify on data receipt"
echo "4. Set up Grafana dashboard for real-time monitoring"
echo "5. Use AWS ALB access logs if available"
echo "6. Implement client certificate validation"
echo "7. Add source IP tracking and geolocation"
echo ""
#!/bin/bash

# Professional Network Traffic Analysis for Moisture Data
# This script provides deep network-level debugging

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="43.209.22.250"

echo "=== PROFESSIONAL NETWORK TRAFFIC ANALYSIS ==="
echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "============================================="
echo ""

# 1. Install necessary tools if not present
echo "1. ENSURING ANALYSIS TOOLS ARE AVAILABLE:"
echo "========================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "
which tcpdump >/dev/null || { echo 'Installing tcpdump...'; sudo apt-get update && sudo apt-get install -y tcpdump; }
which tshark >/dev/null || { echo 'Installing tshark...'; sudo DEBIAN_FRONTEND=noninteractive apt-get install -y tshark; }
which ngrep >/dev/null || { echo 'Installing ngrep...'; sudo apt-get install -y ngrep; }
echo 'Tools ready.'
"

# 2. Capture HTTP traffic on port 8080
echo ""
echo "2. CAPTURING HTTP TRAFFIC (30 seconds):"
echo "======================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "
echo 'Starting packet capture on port 8080...'
sudo timeout 30 tcpdump -i any -s 0 -A -nn 'tcp port 8080' 2>/dev/null | grep -E 'POST|GET|gw_id|sensor_id|HTTP' > /tmp/http-capture.txt &
TCPDUMP_PID=\$!
echo \"Capture PID: \$TCPDUMP_PID\"
sleep 30
echo \"Captured lines: \$(wc -l < /tmp/http-capture.txt)\"
"

# 3. Analyze captured traffic
echo ""
echo "3. TRAFFIC ANALYSIS RESULTS:"
echo "==========================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "
if [ -s /tmp/http-capture.txt ]; then
    echo 'HTTP Requests found:'
    grep -E 'POST|GET' /tmp/http-capture.txt | head -10
    echo ''
    echo 'Gateway IDs detected:'
    grep -o 'gw_id[^,}]*' /tmp/http-capture.txt | sort | uniq -c
else
    echo 'No HTTP traffic captured on port 8080'
fi
"

# 4. Check for traffic on other ports
echo ""
echo "4. CHECKING FOR MISROUTED TRAFFIC:"
echo "=================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "
echo 'Checking common HTTP/HTTPS ports for moisture data...'
sudo timeout 10 tcpdump -i any -nn 'tcp port 80 or tcp port 443 or tcp port 8081 or tcp port 8082' -c 100 2>/dev/null | grep -i moisture || echo 'No moisture data on other common ports'
"

# 5. Connection state analysis
echo ""
echo "5. TCP CONNECTION STATES:"
echo "========================"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "
echo 'Current connections to port 8080:'
sudo ss -tan | grep :8080 | awk '{print \$1}' | sort | uniq -c
echo ''
echo 'Historical connection attempts (last 100 from syslog):'
sudo grep -i 'port 8080' /var/log/syslog 2>/dev/null | tail -5 || echo 'No port 8080 entries in syslog'
"

# 6. Bandwidth and packet analysis
echo ""
echo "6. NETWORK INTERFACE STATISTICS:"
echo "================================"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "
echo 'Interface statistics:'
ip -s link show | grep -A 5 'eth0\\|ens'
echo ''
echo 'Dropped packets:'
netstat -i | grep -E 'eth|ens'
"

# 7. DNS and routing verification
echo ""
echo "7. DNS AND ROUTING VERIFICATION:"
echo "================================"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "
echo 'DNS resolution test (from EC2):'
nslookup google.com | grep -A1 'Name:'
echo ''
echo 'Routing table:'
ip route | head -5
echo ''
echo 'Can reach common endpoints:'
nc -zv google.com 80 2>&1 | grep -E 'succeeded|failed'
"

# 8. Process listening verification
echo ""
echo "8. PROCESS PORT BINDING VERIFICATION:"
echo "====================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "
echo 'Processes listening on port 8080:'
sudo lsof -i :8080 -P -n | grep LISTEN
echo ''
echo 'All listening ports:'
sudo netstat -tlnp | grep -E ':80|node'
"

# 9. Firewall and iptables detailed check
echo ""
echo "9. DETAILED FIREWALL ANALYSIS:"
echo "=============================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "
echo 'iptables INPUT chain:'
sudo iptables -L INPUT -n -v --line-numbers | grep -E '8080|ACCEPT|DROP|REJECT' | head -10
echo ''
echo 'iptables nat table:'
sudo iptables -t nat -L -n -v | grep -E '8080|DNAT|REDIRECT' || echo 'No NAT rules for port 8080'
"

# 10. AWS-specific checks
echo ""
echo "10. AWS INFRASTRUCTURE CHECKS:"
echo "=============================="
# Check if we can access AWS metadata
ssh -i $SSH_KEY ubuntu@$EC2_HOST "
echo 'EC2 instance metadata:'
curl -s http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo 'Cannot access instance metadata'
echo ''
echo 'Public IP from metadata:'
curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'Cannot get public IP'
"

# 11. Create continuous monitoring script
echo ""
echo "11. CREATING CONTINUOUS MONITOR:"
echo "================================"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "
cat > /home/ubuntu/monitor-moisture-traffic.sh << 'EOF'
#!/bin/bash
echo \"Starting continuous moisture traffic monitor...\"
echo \"Timestamp: \$(date)\" > /home/ubuntu/moisture-traffic-monitor.log
echo \"===================\" >> /home/ubuntu/moisture-traffic-monitor.log

# Monitor for 5 minutes
sudo timeout 300 tcpdump -i any -nn 'tcp port 8080' -l 2>/dev/null | while read line; do
    echo \"\$(date '+%Y-%m-%d %H:%M:%S'): \$line\" >> /home/ubuntu/moisture-traffic-monitor.log
    if echo \"\$line\" | grep -q 'gw_id\\|sensor_id'; then
        echo \"MOISTURE DATA DETECTED: \$(date)\" >> /home/ubuntu/moisture-traffic-monitor.log
        echo \"\$line\" >> /home/ubuntu/moisture-traffic-monitor.log
    fi
done &

echo \"Monitor running in background. Check /home/ubuntu/moisture-traffic-monitor.log\"
EOF
chmod +x /home/ubuntu/monitor-moisture-traffic.sh
"

echo ""
echo "=== EXPERT RECOMMENDATIONS ==="
echo ""
echo "1. Run continuous packet capture:"
echo "   ssh ubuntu@$EC2_HOST 'sudo tcpdump -i any -w /home/ubuntu/moisture-full-capture.pcap port 8080'"
echo ""
echo "2. Analyze with Wireshark locally:"
echo "   scp -i $SSH_KEY ubuntu@$EC2_HOST:/home/ubuntu/moisture-full-capture.pcap ."
echo "   wireshark moisture-full-capture.pcap"
echo ""
echo "3. Set up netflow/sflow monitoring for long-term analysis"
echo ""
echo "4. Consider using AWS VPC Flow Logs for complete traffic visibility"
echo ""
echo "5. Implement application-level request signing to verify source"
echo ""
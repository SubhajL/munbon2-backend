#!/bin/bash

# Network Traffic Monitor - 30 minute background capture
# This script runs packet capture for 30 minutes and analyzes moisture data traffic

OUTPUT_DIR="/home/ubuntu/network-analysis-$(date +%Y%m%d-%H%M%S)"
CAPTURE_FILE="$OUTPUT_DIR/moisture-30min.pcap"
LOG_FILE="$OUTPUT_DIR/analysis.log"
SUMMARY_FILE="$OUTPUT_DIR/summary.txt"

echo "=== STARTING 30-MINUTE NETWORK MONITOR ==="
echo "Start time: $(date)"
echo "Output directory: $OUTPUT_DIR"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Start packet capture in background (30 minutes = 1800 seconds)
echo "Starting packet capture for 30 minutes..."
sudo tcpdump -i any -w "$CAPTURE_FILE" \
    'tcp port 8080 and (tcp[((tcp[12:1] & 0xf0) >> 2):4] = 0x504f5354 or tcp[((tcp[12:1] & 0xf0) >> 2):4] = 0x47455420 or tcp[((tcp[12:1] & 0xf0) >> 2):4] = 0x50555420)' \
    -G 1800 -W 1 &

TCPDUMP_PID=$!
echo "Packet capture started with PID: $TCPDUMP_PID"

# Create analysis script that will run after capture
cat > "$OUTPUT_DIR/analyze.sh" << 'EOF'
#!/bin/bash
CAPTURE_FILE="$1"
OUTPUT_DIR="$2"

echo "=== ANALYZING CAPTURED DATA ==="
echo "Analysis started: $(date)"

# Extract HTTP requests
echo -e "\n1. HTTP REQUESTS SUMMARY:" > "$OUTPUT_DIR/http_requests.txt"
sudo tcpdump -r "$CAPTURE_FILE" -A 2>/dev/null | grep -E "POST|GET|PUT" >> "$OUTPUT_DIR/http_requests.txt"

# Extract unique source IPs
echo -e "\n2. UNIQUE SOURCE IPS:" > "$OUTPUT_DIR/source_ips.txt"
sudo tcpdump -r "$CAPTURE_FILE" -nn 2>/dev/null | grep -oE "IP [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" | cut -d' ' -f2 | sort -u >> "$OUTPUT_DIR/source_ips.txt"

# Look for moisture endpoint hits
echo -e "\n3. MOISTURE ENDPOINT REQUESTS:" > "$OUTPUT_DIR/moisture_requests.txt"
sudo tcpdump -r "$CAPTURE_FILE" -A 2>/dev/null | grep -B5 -A10 "munbon-m2m-moisture" >> "$OUTPUT_DIR/moisture_requests.txt"

# Extract gateway IDs
echo -e "\n4. GATEWAY IDS FOUND:" > "$OUTPUT_DIR/gateway_ids.txt"
sudo tcpdump -r "$CAPTURE_FILE" -A 2>/dev/null | grep -oE '"gw_id"[[:space:]]*:[[:space:]]*"[^"]*"' | sort -u >> "$OUTPUT_DIR/gateway_ids.txt"

# Count requests per minute
echo -e "\n5. REQUESTS PER MINUTE:" > "$OUTPUT_DIR/requests_timeline.txt"
sudo tcpdump -r "$CAPTURE_FILE" -nn 2>/dev/null | grep "HTTP" | awk '{print $1}' | cut -d'.' -f1 | uniq -c >> "$OUTPUT_DIR/requests_timeline.txt"

# Generate summary
echo "=== 30-MINUTE CAPTURE SUMMARY ===" > "$OUTPUT_DIR/summary.txt"
echo "Capture duration: 30 minutes" >> "$OUTPUT_DIR/summary.txt"
echo "Total packets: $(sudo tcpdump -r "$CAPTURE_FILE" 2>/dev/null | wc -l)" >> "$OUTPUT_DIR/summary.txt"
echo "HTTP requests: $(grep -c "HTTP" "$OUTPUT_DIR/http_requests.txt" 2>/dev/null || echo 0)" >> "$OUTPUT_DIR/summary.txt"
echo "Moisture endpoint hits: $(grep -c "munbon-m2m-moisture" "$OUTPUT_DIR/moisture_requests.txt" 2>/dev/null || echo 0)" >> "$OUTPUT_DIR/summary.txt"
echo "Unique source IPs: $(wc -l < "$OUTPUT_DIR/source_ips.txt" 2>/dev/null || echo 0)" >> "$OUTPUT_DIR/summary.txt"
echo "Gateway IDs detected: $(wc -l < "$OUTPUT_DIR/gateway_ids.txt" 2>/dev/null || echo 0)" >> "$OUTPUT_DIR/summary.txt"

echo -e "\nTop 10 source IPs:" >> "$OUTPUT_DIR/summary.txt"
sudo tcpdump -r "$CAPTURE_FILE" -nn 2>/dev/null | grep -oE "IP [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" | cut -d' ' -f2 | sort | uniq -c | sort -rn | head -10 >> "$OUTPUT_DIR/summary.txt"

echo -e "\nAnalysis complete: $(date)" >> "$OUTPUT_DIR/summary.txt"
EOF

chmod +x "$OUTPUT_DIR/analyze.sh"

# Create monitoring script
cat > "$OUTPUT_DIR/monitor.sh" << 'EOF'
#!/bin/bash
OUTPUT_DIR="$1"
TCPDUMP_PID="$2"

# Monitor for 30 minutes
for i in {1..30}; do
    echo "[$(date)] Minute $i/30 - Capture in progress..." >> "$OUTPUT_DIR/monitor.log"
    sleep 60
done

echo "[$(date)] Capture complete. Waiting for tcpdump to finish..." >> "$OUTPUT_DIR/monitor.log"
wait $TCPDUMP_PID

echo "[$(date)] Starting analysis..." >> "$OUTPUT_DIR/monitor.log"
"$OUTPUT_DIR/analyze.sh" "$OUTPUT_DIR/moisture-30min.pcap" "$OUTPUT_DIR"

echo "[$(date)] Monitor complete!" >> "$OUTPUT_DIR/monitor.log"
echo "Results saved in: $OUTPUT_DIR" >> "$OUTPUT_DIR/monitor.log"
EOF

chmod +x "$OUTPUT_DIR/monitor.sh"

# Start the monitor in background
nohup "$OUTPUT_DIR/monitor.sh" "$OUTPUT_DIR" "$TCPDUMP_PID" > "$OUTPUT_DIR/monitor.out" 2>&1 &
MONITOR_PID=$!

echo ""
echo "=== BACKGROUND MONITOR STARTED ==="
echo "Monitor PID: $MONITOR_PID"
echo "Capture PID: $TCPDUMP_PID"
echo "Duration: 30 minutes"
echo "Output directory: $OUTPUT_DIR"
echo ""
echo "To check status:"
echo "  tail -f $OUTPUT_DIR/monitor.log"
echo ""
echo "To stop early:"
echo "  sudo kill $TCPDUMP_PID"
echo ""
echo "Results will be available in ~30 minutes at:"
echo "  $OUTPUT_DIR/summary.txt"
echo ""
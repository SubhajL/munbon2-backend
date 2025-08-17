#!/bin/bash

# Start 1-hour packet capture for moisture data on EC2
# Captures all HTTP traffic to port 8080 from external sources

set -e

echo "🚀 Starting 1-hour moisture packet capture on EC2..."

# Server details
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"

# Create capture directory with timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
CAPTURE_DIR="moisture-capture-$TIMESTAMP"

echo "📁 Creating capture directory: $CAPTURE_DIR"

# Create the capture script
cat > /tmp/capture-script.sh << 'EOF'
#!/bin/bash
set -e

CAPTURE_DIR="$1"
DURATION="3600"  # 1 hour in seconds

echo "Starting 1-hour packet capture..."
echo "Capture directory: /home/ubuntu/$CAPTURE_DIR"
echo "Duration: $DURATION seconds (1 hour)"
echo "Start time: $(date)"

# Create directory
mkdir -p /home/ubuntu/$CAPTURE_DIR
cd /home/ubuntu/$CAPTURE_DIR

# Create monitoring script
cat > monitor.sh << 'MONITOR'
#!/bin/bash
PCAP_FILE="moisture-1hr.pcap"
LOG_FILE="capture.log"

echo "=== MOISTURE DATA CAPTURE STARTED ===" | tee $LOG_FILE
echo "Start time: $(date)" | tee -a $LOG_FILE
echo "Duration: 1 hour" | tee -a $LOG_FILE
echo "Capture file: $PCAP_FILE" | tee -a $LOG_FILE
echo "" | tee -a $LOG_FILE

# Start packet capture in background
sudo tcpdump -i any -w $PCAP_FILE \
  'tcp port 8080 and not src host 10.0.0.0/8 and not src host 172.16.0.0/12' \
  -s 0 2>&1 &

TCPDUMP_PID=$!
echo "tcpdump PID: $TCPDUMP_PID" | tee -a $LOG_FILE

# Monitor for 1 hour with progress updates
END_TIME=$(($(date +%s) + 3600))
UPDATE_INTERVAL=300  # Update every 5 minutes

while [ $(date +%s) -lt $END_TIME ]; do
  CURRENT_TIME=$(date +%s)
  ELAPSED=$((CURRENT_TIME - $(date +%s) + 3600))
  REMAINING=$((END_TIME - CURRENT_TIME))
  
  # Convert to minutes
  ELAPSED_MIN=$((3600 - REMAINING))
  REMAINING_MIN=$((REMAINING / 60))
  
  # Get file size
  if [ -f $PCAP_FILE ]; then
    FILE_SIZE=$(ls -lh $PCAP_FILE | awk '{print $5}')
  else
    FILE_SIZE="0B"
  fi
  
  echo "[$(date '+%H:%M:%S')] Progress: $((ELAPSED_MIN / 60))m elapsed, ${REMAINING_MIN}m remaining | Capture size: $FILE_SIZE" | tee -a $LOG_FILE
  
  # Sleep for update interval or remaining time, whichever is shorter
  SLEEP_TIME=$((REMAINING < UPDATE_INTERVAL ? REMAINING : UPDATE_INTERVAL))
  sleep $SLEEP_TIME
done

# Stop capture
echo "" | tee -a $LOG_FILE
echo "Stopping capture..." | tee -a $LOG_FILE
sudo kill $TCPDUMP_PID 2>/dev/null || true
sleep 2

# Generate summary
echo "" | tee -a $LOG_FILE
echo "=== CAPTURE COMPLETED ===" | tee -a $LOG_FILE
echo "End time: $(date)" | tee -a $LOG_FILE

if [ -f $PCAP_FILE ]; then
  FILE_SIZE=$(ls -lh $PCAP_FILE | awk '{print $5}')
  PACKET_COUNT=$(sudo tcpdump -r $PCAP_FILE 2>/dev/null | wc -l)
  
  echo "File size: $FILE_SIZE" | tee -a $LOG_FILE
  echo "Total packets: $PACKET_COUNT" | tee -a $LOG_FILE
  
  # Quick analysis
  echo "" | tee -a $LOG_FILE
  echo "=== QUICK ANALYSIS ===" | tee -a $LOG_FILE
  
  # Count moisture endpoint hits
  MOISTURE_HITS=$(sudo tcpdump -r $PCAP_FILE -n 'tcp dst port 8080' 2>/dev/null | grep -c 'moisture' || echo "0")
  echo "Moisture endpoint hits: $MOISTURE_HITS" | tee -a $LOG_FILE
  
  # Get unique source IPs
  echo "Unique source IPs:" | tee -a $LOG_FILE
  sudo tcpdump -r $PCAP_FILE -n 'tcp dst port 8080' 2>/dev/null | \
    grep -oE 'IP [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | \
    awk '{print $2}' | sort -u | tee -a $LOG_FILE
    
  # Create analysis script for later
  cat > analyze.sh << 'ANALYZE'
#!/bin/bash
echo "Analyzing capture file..."

# Extract moisture requests with timestamps
echo "=== MOISTURE REQUESTS ==="
sudo tcpdump -r moisture-1hr.pcap -n -A 'tcp dst port 8080' 2>/dev/null | \
  grep -B5 -A20 'moisture/munbon-m2m-moisture' > moisture-requests.txt
  
# Count requests per minute
echo "=== REQUESTS PER MINUTE ==="
sudo tcpdump -r moisture-1hr.pcap -n 'tcp dst port 8080' 2>/dev/null | \
  awk '{print substr($1,1,5)}' | sort | uniq -c > requests-per-minute.txt
  
echo "Analysis complete. Check moisture-requests.txt and requests-per-minute.txt"
ANALYZE
  chmod +x analyze.sh
  
else
  echo "ERROR: Capture file not found!" | tee -a $LOG_FILE
fi

echo "" | tee -a $LOG_FILE
echo "Capture directory: $(pwd)" | tee -a $LOG_FILE
echo "To analyze later, run: ./analyze.sh" | tee -a $LOG_FILE
MONITOR

chmod +x monitor.sh

# Run the monitor script
./monitor.sh

EOF

# Copy and execute the script on EC2
echo "📤 Uploading capture script to EC2..."
scp -i "$SSH_KEY" /tmp/capture-script.sh "$EC2_USER@$EC2_HOST:/tmp/"

echo "🎬 Starting capture on EC2..."
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "bash /tmp/capture-script.sh $CAPTURE_DIR" &

SSH_PID=$!

echo ""
echo "✅ Packet capture started!"
echo ""
echo "📊 Capture details:"
echo "   Duration: 1 hour"
echo "   Directory: /home/ubuntu/$CAPTURE_DIR"
echo "   Process: Running in background (PID: $SSH_PID)"
echo ""
echo "📋 To check progress:"
echo "   ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'tail -f /home/ubuntu/$CAPTURE_DIR/capture.log'"
echo ""
echo "📥 To download results after 1 hour:"
echo "   scp -i $SSH_KEY -r $EC2_USER@$EC2_HOST:/home/ubuntu/$CAPTURE_DIR ./"
echo ""
echo "🔍 To analyze on EC2:"
echo "   ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'cd /home/ubuntu/$CAPTURE_DIR && ./analyze.sh'"

# Save connection info
cat > /tmp/moisture-capture-info.txt << EOF
Capture Start Time: $(date)
EC2 Host: $EC2_HOST
Capture Directory: /home/ubuntu/$CAPTURE_DIR
Local PID: $SSH_PID
EOF

echo ""
echo "💾 Connection info saved to: /tmp/moisture-capture-info.txt"

# Cleanup
rm -f /tmp/capture-script.sh
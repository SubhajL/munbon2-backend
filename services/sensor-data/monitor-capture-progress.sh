#!/bin/bash

# Monitor the 1-hour capture progress

EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"
CAPTURE_DIR="/home/ubuntu/moisture-capture-20250802-172529"

echo "📊 Monitoring moisture packet capture progress..."
echo "Started at: $(cat /tmp/moisture-capture-info.txt | grep 'Start Time' | cut -d: -f2-)"
echo ""

# Function to get capture stats
check_capture() {
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "
        if [ -f $CAPTURE_DIR/moisture-1hr.pcap ]; then
            FILE_SIZE=\$(ls -lh $CAPTURE_DIR/moisture-1hr.pcap | awk '{print \$5}')
            PACKET_COUNT=\$(sudo tcpdump -r $CAPTURE_DIR/moisture-1hr.pcap 2>/dev/null | wc -l || echo '0')
            MOISTURE_COUNT=\$(sudo tcpdump -r $CAPTURE_DIR/moisture-1hr.pcap -n 2>/dev/null | grep -c 'moisture' || echo '0')
            echo \"File size: \$FILE_SIZE\"
            echo \"Total packets: \$PACKET_COUNT\"
            echo \"Moisture requests: \$MOISTURE_COUNT\"
        else
            echo 'Capture file not found!'
        fi
    "
}

# Check every 5 minutes
ELAPSED=0
while [ $ELAPSED -lt 60 ]; do
    echo "⏱️  Time elapsed: ${ELAPSED} minutes"
    check_capture
    echo "---"
    
    if [ $ELAPSED -lt 55 ]; then
        echo "Next update in 5 minutes..."
        sleep 300
        ELAPSED=$((ELAPSED + 5))
    else
        break
    fi
done

echo ""
echo "✅ Capture should be complete after 1 hour!"
echo ""
echo "📥 To download the capture file:"
echo "   scp -i $SSH_KEY $EC2_USER@$EC2_HOST:$CAPTURE_DIR/moisture-1hr.pcap ./"
echo ""
echo "🔍 To analyze on EC2:"
echo "   ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'cd $CAPTURE_DIR && ./analyze.sh'"
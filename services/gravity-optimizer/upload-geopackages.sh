#!/bin/bash

echo "=== Upload GeoPackage Files to EC2 Processor ==="
echo "Date: $(date)"

# Configuration
EC2_IP="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"
UPLOAD_DIR="/home/ubuntu/geopackage-uploads"

# Check if we have the data folders
if [ ! -d "../../data_ridplan" ] && [ ! -d "../../data_water_level" ]; then
    echo "Error: Data folders not found. Please extract the zip file first."
    echo "Run: unzip data_upload__20250905.zip"
    exit 1
fi

# Find and upload geopackage files
echo "Searching for geopackage files..."

# Find RID-MS files
if [ -d "../../data_ridplan" ]; then
    echo "Uploading RID-MS parcels data..."
    find ../../data_ridplan -name "*.gpkg" -type f | while read file; do
        echo "  Uploading: $file"
        scp -i $SSH_KEY "$file" ubuntu@$EC2_IP:$UPLOAD_DIR/
    done
fi

# Find water level files
if [ -d "../../data_water_level" ]; then
    echo "Uploading water level data..."
    find ../../data_water_level -name "*.gpkg" -type f | while read file; do
        echo "  Uploading: $file"
        scp -i $SSH_KEY "$file" ubuntu@$EC2_IP:$UPLOAD_DIR/
    done
fi

# Check worker status
echo ""
echo "Checking worker status..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
echo "Worker status:"
pm2 status geopackage-processor

echo ""
echo "Files in upload directory:"
ls -la /home/ubuntu/geopackage-uploads/

echo ""
echo "Recent logs:"
pm2 logs geopackage-processor --lines 10 --nostream
EOF

echo ""
echo "=== Upload Complete ==="
echo "The worker will automatically process the files within 30 seconds."
echo "Check progress with: ssh -i $SSH_KEY ubuntu@$EC2_IP 'pm2 logs geopackage-processor'"
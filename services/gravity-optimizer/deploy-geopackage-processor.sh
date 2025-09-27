#!/bin/bash

echo "=== Deploying GeoPackage Processor Worker to EC2 ==="
echo "Date: $(date)"

# Configuration
EC2_IP="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"
REMOTE_PATH="/home/ubuntu/geopackage-processor"
SERVICE_NAME="geopackage-processor"

# Step 1: Create remote directory structure
echo "1. Creating remote directories..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
mkdir -p /home/ubuntu/geopackage-processor
mkdir -p /home/ubuntu/geopackage-uploads
mkdir -p /home/ubuntu/geopackage-processed
mkdir -p /tmp/geopackage-processing
EOF

# Step 2: Copy worker files to EC2
echo "2. Copying worker files to EC2..."
scp -i $SSH_KEY geopackage-processor-worker.js ubuntu@$EC2_IP:$REMOTE_PATH/
scp -i $SSH_KEY ecosystem.geopackage.config.js ubuntu@$EC2_IP:$REMOTE_PATH/
scp -i $SSH_KEY package.json ubuntu@$EC2_IP:$REMOTE_PATH/

# Step 3: Install dependencies and start worker
echo "3. Installing dependencies and starting worker..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
cd /home/ubuntu/geopackage-processor

# Install Node.js dependencies
echo "Installing dependencies..."
npm install pg csv-parser

# Check if ogr2ogr is installed
if ! command -v ogr2ogr &> /dev/null; then
    echo "Installing GDAL tools..."
    sudo apt-get update
    sudo apt-get install -y gdal-bin
fi

# Stop existing service if running
pm2 stop geopackage-processor 2>/dev/null || true
pm2 delete geopackage-processor 2>/dev/null || true

# Start the worker with PM2
echo "Starting GeoPackage Processor Worker..."
pm2 start ecosystem.geopackage.config.js

# Save PM2 configuration
pm2 save

# Show status
pm2 list
pm2 logs geopackage-processor --lines 20
EOF

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "To upload geopackage files for processing:"
echo "  scp -i $SSH_KEY your_file.gpkg ubuntu@$EC2_IP:/home/ubuntu/geopackage-uploads/"
echo ""
echo "To check worker status:"
echo "  ssh -i $SSH_KEY ubuntu@$EC2_IP 'pm2 status geopackage-processor'"
echo ""
echo "To view logs:"
echo "  ssh -i $SSH_KEY ubuntu@$EC2_IP 'pm2 logs geopackage-processor'"
echo ""
echo "Processed files will be moved to: /home/ubuntu/geopackage-processed/"
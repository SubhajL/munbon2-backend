#!/bin/bash

echo "=== Deploying Shapefile Queue Processor to EC2 ==="
echo "Date: $(date)"
echo ""

# Configuration
EC2_IP="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"
EC2_USER="ubuntu"
SERVICE_NAME="shapefile-queue-processor"
REMOTE_DIR="/home/ubuntu/munbon2-backend/services/gis"

echo "1. Building the GIS service locally..."
cd /Users/subhajlimanond/dev/munbon2-backend/services/gis

# Check if we need to compile TypeScript
if [ ! -d "dist" ]; then
    echo "Building from TypeScript..."
    npm run build
fi

echo ""
echo "2. Creating remote directory structure on EC2..."
ssh -i $SSH_KEY $EC2_USER@$EC2_IP << 'EOF'
mkdir -p /home/ubuntu/munbon2-backend/services/gis/dist/workers
mkdir -p /home/ubuntu/munbon2-backend/services/gis/dist/services
mkdir -p /home/ubuntu/munbon2-backend/services/gis/dist/models
mkdir -p /home/ubuntu/munbon2-backend/services/gis/dist/config
mkdir -p /home/ubuntu/munbon2-backend/services/gis/dist/utils
echo "Remote directories created"
EOF

echo ""
echo "3. Copying compiled files to EC2..."
# Copy the entire dist directory
scp -i $SSH_KEY -r dist/* $EC2_USER@$EC2_IP:$REMOTE_DIR/dist/

# Copy PM2 ecosystem file
scp -i $SSH_KEY ecosystem.ec2.config.js $EC2_USER@$EC2_IP:$REMOTE_DIR/

# Copy package files
scp -i $SSH_KEY package.json $EC2_USER@$EC2_IP:$REMOTE_DIR/
scp -i $SSH_KEY package-lock.json $EC2_USER@$EC2_IP:$REMOTE_DIR/

echo ""
echo "4. Installing dependencies on EC2..."
ssh -i $SSH_KEY $EC2_USER@$EC2_IP << EOF
cd $REMOTE_DIR
echo "Installing production dependencies..."
npm ci --production
echo "Dependencies installed"
EOF

echo ""
echo "5. Setting up database on EC2..."
ssh -i $SSH_KEY $EC2_USER@$EC2_IP << 'EOF'
# Use existing munbon_dev database
echo "Using existing munbon_dev database"

# Enable PostGIS extensions in munbon_dev
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "CREATE EXTENSION IF NOT EXISTS postgis;"
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "CREATE EXTENSION IF NOT EXISTS postgis_topology;"
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "CREATE SCHEMA IF NOT EXISTS gis;"

# Create tables in munbon_dev database
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev << 'EOSQL'
SET search_path TO gis, public;

-- Shape file uploads table
CREATE TABLE IF NOT EXISTS shape_file_uploads (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) UNIQUE NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    s3_key VARCHAR(1000),
    status VARCHAR(50) DEFAULT 'pending',
    parcel_count INTEGER DEFAULT 0,
    zone_count INTEGER DEFAULT 0,
    metadata JSONB,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Parcels table
CREATE TABLE IF NOT EXISTS parcels (
    id SERIAL PRIMARY KEY,
    plot_code VARCHAR(255) UNIQUE NOT NULL,
    zone_id INTEGER,
    farmer_id VARCHAR(255),
    boundary GEOMETRY(Polygon, 4326),
    area_hectares DECIMAL(10,4),
    current_crop_type VARCHAR(100),
    soil_type VARCHAR(100),
    planting_date DATE,
    expected_harvest_date DATE,
    properties JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Zones table  
CREATE TABLE IF NOT EXISTS zones (
    id SERIAL PRIMARY KEY,
    zone_code VARCHAR(50) UNIQUE NOT NULL,
    zone_name VARCHAR(255),
    zone_type VARCHAR(100),
    boundary GEOMETRY(Polygon, 4326),
    area_hectares DECIMAL(10,4),
    properties JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial indexes
CREATE INDEX IF NOT EXISTS idx_parcels_boundary ON parcels USING GIST (boundary);
CREATE INDEX IF NOT EXISTS idx_zones_boundary ON zones USING GIST (boundary);
CREATE INDEX IF NOT EXISTS idx_parcels_plot_code ON parcels(plot_code);
CREATE INDEX IF NOT EXISTS idx_zones_zone_code ON zones(zone_code);

EOSQL

echo "Database setup completed"
EOF

echo ""
echo "6. Starting shapefile queue processor with PM2..."
ssh -i $SSH_KEY $EC2_USER@$EC2_IP << EOF
cd $REMOTE_DIR

# Stop existing processor if running
pm2 stop $SERVICE_NAME 2>/dev/null || true
pm2 delete $SERVICE_NAME 2>/dev/null || true

# Start the processor
pm2 start ecosystem.ec2.config.js
pm2 save

echo ""
echo "PM2 Status:"
pm2 list | grep -E "(shapefile|$SERVICE_NAME)"
EOF

echo ""
echo "7. Setting up PM2 startup script..."
ssh -i $SSH_KEY $EC2_USER@$EC2_IP << 'EOF'
pm2 startup | grep -v "PM2" | bash
pm2 save
EOF

echo ""
echo "8. Checking processor logs..."
ssh -i $SSH_KEY $EC2_USER@$EC2_IP "pm2 logs $SERVICE_NAME --lines 20"

echo ""
echo "=== Deployment Complete ==="
echo "Shapefile queue processor is now running on EC2"
echo ""
echo "Useful commands:"
echo "- Check status: ssh -i $SSH_KEY $EC2_USER@$EC2_IP 'pm2 status'"
echo "- View logs: ssh -i $SSH_KEY $EC2_USER@$EC2_IP 'pm2 logs shapefile-queue-processor'"
echo "- Restart: ssh -i $SSH_KEY $EC2_USER@$EC2_IP 'pm2 restart shapefile-queue-processor'"
echo ""
echo "Queue URL: https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue"
echo "S3 Bucket: munbon-gis-shape-files"
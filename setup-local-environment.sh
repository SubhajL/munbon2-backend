#!/bin/bash

# Comprehensive local setup script for Munbon Backend
# This script sets up the complete local environment step by step

set -e  # Exit on error

echo "=== Munbon Local Environment Setup ==="
echo "This script will set up your local development environment"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Start Docker Infrastructure
setup_infrastructure() {
    echo "📦 Step 1: Starting Docker Infrastructure..."
    
    # Check Docker
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
        exit 1
    fi
    
    # Start databases
    echo "Starting databases and infrastructure..."
    make up-min  # Start minimal setup first
    
    echo "Waiting for databases to be ready..."
    sleep 30
    
    # Check database connections
    echo "Checking database connections..."
    
    # PostgreSQL
    if docker exec postgres psql -U postgres -c "SELECT 1" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
    else
        echo -e "${RED}❌ PostgreSQL is not ready${NC}"
        exit 1
    fi
    
    # TimescaleDB
    if docker exec timescaledb psql -U postgres -c "SELECT 1" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ TimescaleDB is ready${NC}"
    else
        echo -e "${RED}❌ TimescaleDB is not ready${NC}"
        exit 1
    fi
    
    # Redis
    if docker exec redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis is ready${NC}"
    else
        echo -e "${RED}❌ Redis is not ready${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Infrastructure is ready${NC}"
    echo ""
}

# Step 2: Initialize Databases
initialize_databases() {
    echo "🗄️ Step 2: Initializing Databases..."
    
    # Initialize PostgreSQL with PostGIS
    echo "Setting up PostgreSQL with PostGIS..."
    docker exec -i postgres psql -U postgres << EOF
-- Create databases if not exists
CREATE DATABASE IF NOT EXISTS gis_data;
CREATE DATABASE IF NOT EXISTS rid_ms;

-- Enable PostGIS
\c gis_data
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

\c rid_ms
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOF
    
    # Initialize TimescaleDB
    echo "Setting up TimescaleDB..."
    docker exec -i timescaledb psql -U postgres << EOF
-- Create sensor data database
CREATE DATABASE IF NOT EXISTS sensor_data;

\c sensor_data
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create sensor data tables
CREATE TABLE IF NOT EXISTS water_levels (
    time TIMESTAMPTZ NOT NULL,
    sensor_id VARCHAR(50) NOT NULL,
    sensor_name VARCHAR(100),
    zone VARCHAR(20),
    location GEOGRAPHY(POINT, 4326),
    water_level_m DECIMAL(10,2),
    flow_rate_m3s DECIMAL(10,2),
    quality INTEGER
);

CREATE TABLE IF NOT EXISTS moisture_readings (
    time TIMESTAMPTZ NOT NULL,
    sensor_id VARCHAR(50) NOT NULL,
    sensor_name VARCHAR(100),
    zone VARCHAR(20),
    location GEOGRAPHY(POINT, 4326),
    moisture_percentage DECIMAL(5,2),
    temperature_celsius DECIMAL(5,2),
    quality INTEGER
);

CREATE TABLE IF NOT EXISTS aos_readings (
    time TIMESTAMPTZ NOT NULL,
    station_id VARCHAR(50) NOT NULL,
    station_name VARCHAR(100),
    zone VARCHAR(20),
    location GEOGRAPHY(POINT, 4326),
    rainfall_mm DECIMAL(10,2),
    temperature_celsius DECIMAL(5,2),
    humidity_percentage DECIMAL(5,2),
    wind_speed_ms DECIMAL(5,2),
    wind_direction_degrees DECIMAL(5,2),
    pressure_hpa DECIMAL(10,2)
);

-- Convert to hypertables
SELECT create_hypertable('water_levels', 'time', if_not_exists => TRUE);
SELECT create_hypertable('moisture_readings', 'time', if_not_exists => TRUE);
SELECT create_hypertable('aos_readings', 'time', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_water_levels_sensor_time ON water_levels (sensor_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_moisture_sensor_time ON moisture_readings (sensor_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_aos_station_time ON aos_readings (station_id, time DESC);
EOF
    
    echo -e "${GREEN}✅ Databases initialized${NC}"
    echo ""
}

# Step 3: Set up RID-MS Service
setup_rid_ms() {
    echo "🗺️ Step 3: Setting up RID-MS Service..."
    
    cd services/rid-ms
    
    # Create environment file
    cat > .env << EOF
NODE_ENV=development
PORT=3002

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rid_ms

# JWT Secret (shared with auth service)
JWT_SECRET=munbon-local-jwt-secret-2024

# AWS LocalStack (for local testing)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_ENDPOINT=http://localhost:4566
S3_BUCKET=munbon-rid-shapefiles

# API Authentication
EXTERNAL_API_TOKEN=munbon-ridms-shape
API_KEYS=rid-ms-test,test-key-123
EOF
    
    # Install dependencies
    echo "Installing RID-MS dependencies..."
    npm install
    
    # Create database schema
    echo "Creating RID-MS database schema..."
    docker exec -i postgres psql -U postgres -d rid_ms << 'EOF'
-- Shape files table
CREATE TABLE IF NOT EXISTS shapefiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'uploaded',
    upload_date TIMESTAMPTZ DEFAULT NOW(),
    process_date TIMESTAMPTZ,
    s3_url VARCHAR(500),
    parcel_count INTEGER,
    total_area_rai DECIMAL(15,2),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Parcels table
CREATE TABLE IF NOT EXISTS parcels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shapefile_id UUID REFERENCES shapefiles(id),
    parcel_id VARCHAR(100) UNIQUE,
    zone VARCHAR(20),
    area_rai DECIMAL(10,2),
    crop_type VARCHAR(50),
    watering_method VARCHAR(50),
    owner_name VARCHAR(200),
    geometry GEOMETRY(Polygon, 4326),
    properties JSONB,
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_parcels_zone ON parcels(zone);
CREATE INDEX idx_parcels_shapefile ON parcels(shapefile_id);
CREATE INDEX idx_parcels_geom ON parcels USING GIST(geometry);
CREATE INDEX idx_parcels_valid ON parcels(valid_from, valid_to);
EOF
    
    # Build the service
    echo "Building RID-MS service..."
    npm run build
    
    cd ../..
    
    echo -e "${GREEN}✅ RID-MS Service configured${NC}"
    echo ""
}

# Step 4: Set up Sensor Data Service
setup_sensor_data() {
    echo "📊 Step 4: Setting up Sensor Data Service..."
    
    cd services/sensor-data
    
    # Create environment file
    cat > .env << EOF
NODE_ENV=development
PORT=3001

# TimescaleDB for sensor data
DB_HOST=localhost
DB_PORT=5433
DB_NAME=sensor_data
DB_USER=postgres
DB_PASSWORD=postgres

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# JWT Secret (shared with auth service)
JWT_SECRET=munbon-local-jwt-secret-2024

# External API Keys
EXTERNAL_API_KEYS=test-key-123,rid-ms-test,mobile-app-test

# MQTT (optional, for real sensor integration)
MQTT_BROKER_URL=mqtt://localhost:1883
MQTT_USERNAME=
MQTT_PASSWORD=

# AWS LocalStack (for local SQS testing)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
SQS_ENDPOINT=http://localhost:4566
SQS_QUEUE_URL=http://localhost:4566/000000000000/sensor-data-queue
EOF
    
    # Install dependencies
    echo "Installing Sensor Data dependencies..."
    npm install
    
    # Insert sample data
    echo "Inserting sample sensor data..."
    docker exec -i timescaledb psql -U postgres -d sensor_data << 'EOF'
-- Insert sample water level data
INSERT INTO water_levels (time, sensor_id, sensor_name, zone, location, water_level_m, flow_rate_m3s, quality)
VALUES
    (NOW() - INTERVAL '1 hour', 'wl001', 'คลองส่งน้ำสาย 1', 'Zone 1', ST_MakePoint(102.1234, 14.5678), 12.5, 1.2, 100),
    (NOW() - INTERVAL '30 minutes', 'wl001', 'คลองส่งน้ำสาย 1', 'Zone 1', ST_MakePoint(102.1234, 14.5678), 12.6, 1.3, 100),
    (NOW(), 'wl001', 'คลองส่งน้ำสาย 1', 'Zone 1', ST_MakePoint(102.1234, 14.5678), 12.7, 1.4, 100),
    (NOW(), 'wl002', 'คลองส่งน้ำสาย 2', 'Zone 2', ST_MakePoint(102.2345, 14.6789), 10.2, 0.8, 100);

-- Insert sample moisture data
INSERT INTO moisture_readings (time, sensor_id, sensor_name, zone, location, moisture_percentage, temperature_celsius, quality)
VALUES
    (NOW() - INTERVAL '1 hour', 'm001', 'แปลงนา A1', 'Zone 1', ST_MakePoint(102.1111, 14.5555), 65.5, 28.3, 100),
    (NOW() - INTERVAL '30 minutes', 'm001', 'แปลงนา A1', 'Zone 1', ST_MakePoint(102.1111, 14.5555), 64.2, 29.1, 100),
    (NOW(), 'm001', 'แปลงนา A1', 'Zone 1', ST_MakePoint(102.1111, 14.5555), 63.8, 30.2, 100),
    (NOW(), 'm002', 'แปลงนา B2', 'Zone 2', ST_MakePoint(102.2222, 14.6666), 72.1, 27.5, 100);

-- Insert sample AOS weather data
INSERT INTO aos_readings (time, station_id, station_name, zone, location, rainfall_mm, temperature_celsius, humidity_percentage, wind_speed_ms, wind_direction_degrees, pressure_hpa)
VALUES
    (NOW(), 'aos001', 'สถานีตรวจอากาศมูลบน', 'Zone 1', ST_MakePoint(102.1500, 14.6000), 2.5, 28.5, 75, 3.2, 180, 1013.25);
EOF
    
    cd ../..
    
    echo -e "${GREEN}✅ Sensor Data Service configured${NC}"
    echo ""
}

# Step 5: Start Services
start_services() {
    echo "🚀 Step 5: Starting Services..."
    
    # Create startup script
    cat > start-services.sh << 'EOF'
#!/bin/bash

echo "Starting Munbon Services..."

# Function to start a service
start_service() {
    local service_name=$1
    local service_dir=$2
    local port=$3
    
    echo "Starting $service_name on port $port..."
    cd $service_dir
    npm run dev > $service_name.log 2>&1 &
    echo $! > $service_name.pid
    cd - > /dev/null
    
    # Wait for service to start
    sleep 5
    
    # Check if service is running
    if lsof -i:$port > /dev/null 2>&1; then
        echo "✅ $service_name started successfully"
    else
        echo "❌ Failed to start $service_name"
        cat $service_dir/$service_name.log
    fi
}

# Start services
start_service "sensor-data" "services/sensor-data" 3001
start_service "rid-ms" "services/rid-ms" 3002

echo ""
echo "Services are running:"
echo "- Sensor Data API: http://localhost:3001"
echo "- RID-MS API: http://localhost:3002"
echo ""
echo "To stop services, run: ./stop-services.sh"
EOF
    
    # Create stop script
    cat > stop-services.sh << 'EOF'
#!/bin/bash

echo "Stopping Munbon Services..."

# Stop services using PID files
for pidfile in services/*/*.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if ps -p $pid > /dev/null; then
            kill $pid
            echo "Stopped process $pid"
        fi
        rm "$pidfile"
    fi
done

echo "✅ All services stopped"
EOF
    
    chmod +x start-services.sh stop-services.sh
    
    # Start the services
    ./start-services.sh
    
    echo -e "${GREEN}✅ Services started${NC}"
    echo ""
}

# Step 6: Create Test Scripts
create_test_scripts() {
    echo "🧪 Step 6: Creating Test Scripts..."
    
    cat > test-local-apis.sh << 'EOF'
#!/bin/bash

echo "=== Testing Local APIs ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Test function
test_api() {
    local name=$1
    local method=$2
    local url=$3
    local headers=$4
    local data=$5
    
    echo "Testing: $name"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" $headers "$url")
    else
        response=$(curl -s -w "\n%{http_code}" -X $method $headers -d "$data" "$url")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
        echo -e "${GREEN}✅ Success (HTTP $http_code)${NC}"
        echo "$body" | jq . 2>/dev/null || echo "$body"
    else
        echo -e "${RED}❌ Failed (HTTP $http_code)${NC}"
        echo "$body"
    fi
    echo ""
}

# Test Sensor Data APIs
echo "=== Sensor Data APIs (Port 3001) ==="
test_api "Water Levels Latest" "GET" "http://localhost:3001/api/v1/public/water-levels/latest" "-H 'X-API-Key: test-key-123'"
test_api "Moisture Latest" "GET" "http://localhost:3001/api/v1/public/moisture/latest" "-H 'X-API-Key: test-key-123'"
test_api "AOS Weather Latest" "GET" "http://localhost:3001/api/v1/public/aos/latest" "-H 'X-API-Key: test-key-123'"

# Test RID-MS APIs
echo "=== RID-MS APIs (Port 3002) ==="
test_api "List Shapefiles" "GET" "http://localhost:3002/api/v1/rid-ms/shapefiles" "-H 'X-API-Key: test-key-123'"

# Test SHAPE file upload
echo "=== Testing SHAPE File Upload ==="
# Create a test ZIP file with dummy content
echo "test content" > test.txt
zip test.zip test.txt > /dev/null 2>&1
base64_content=$(base64 < test.zip)
rm test.txt test.zip

test_api "Upload SHAPE File" "POST" "http://localhost:3002/api/external/shapefile/push" \
    "-H 'Authorization: Bearer munbon-ridms-shape' -H 'Content-Type: application/json'" \
    "{\"filename\":\"test.zip\",\"content\":\"$base64_content\",\"metadata\":{\"zone\":\"Zone 1\"}}"

echo "✅ Testing complete"
EOF
    
    chmod +x test-local-apis.sh
    
    echo -e "${GREEN}✅ Test scripts created${NC}"
    echo ""
}

# Main execution
main() {
    echo "This script will:"
    echo "1. Start Docker infrastructure (databases)"
    echo "2. Initialize database schemas"
    echo "3. Configure RID-MS service"
    echo "4. Configure Sensor Data service"
    echo "5. Start all services"
    echo "6. Create test scripts"
    echo ""
    
    read -p "Continue? (y/n) " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
    
    echo ""
    
    # Run all steps
    setup_infrastructure
    initialize_databases
    setup_rid_ms
    setup_sensor_data
    start_services
    create_test_scripts
    
    # Create summary
    cat > local-setup-summary.txt << EOF
Munbon Local Environment Setup Complete
=======================================

🗄️ Databases Running:
- PostgreSQL (GIS): localhost:5432
- TimescaleDB (Sensors): localhost:5433
- Redis (Cache): localhost:6379

🚀 Services Running:
- Sensor Data API: http://localhost:3001
  - Water levels: /api/v1/public/water-levels/latest
  - Moisture: /api/v1/public/moisture/latest
  - Weather: /api/v1/public/aos/latest
  
- RID-MS API: http://localhost:3002
  - Upload: POST /api/external/shapefile/push
  - List: GET /api/v1/rid-ms/shapefiles
  - Parcels: GET /api/v1/rid-ms/zones/{zone}/parcels

🔑 Test API Keys:
- General: test-key-123
- RID-MS Upload: Bearer munbon-ridms-shape

🧪 Test Commands:
./test-local-apis.sh    # Run all API tests
./start-services.sh     # Start services
./stop-services.sh      # Stop services
make status            # Check Docker status
make logs             # View Docker logs

📚 Next Steps:
1. Run ./test-local-apis.sh to verify everything works
2. Use Postman/Insomnia to test APIs interactively
3. Check logs: tail -f services/*/**.log
4. Access pgAdmin: http://localhost:8093
5. Access Redis Commander: http://localhost:8091
EOF
    
    echo ""
    echo "========================================="
    echo -e "${GREEN}🎉 Local Setup Complete!${NC}"
    echo "========================================="
    echo ""
    cat local-setup-summary.txt
}

# Run main
main
#!/bin/bash

# Deploy AOS weather data table to EC2 database

echo "🌤️  Deploying AOS Weather Data Table"
echo "==================================="

# Configuration
EC2_HOST=${EC2_HOST:-43.208.201.191}
EC2_USER="ubuntu"
KEY_PATH="~/dev/th-lab01.pem"

echo "📍 Target: $EC2_USER@$EC2_HOST"
echo ""

# Step 1: Check if table exists
echo "🔍 Checking if AOS table already exists..."
TABLE_EXISTS=$(ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -t -c \
  "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'aos_weather_data');"
EOF
)

if [[ "$TABLE_EXISTS" =~ "t" ]]; then
    echo "✅ AOS table already exists"
    
    # Show table structure
    echo ""
    echo "📊 Current table structure:"
    ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \
  "\d aos_weather_data"
EOF
    
    # Check if it's a hypertable
    echo ""
    echo "🔍 Checking if it's a TimescaleDB hypertable..."
    ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \
  "SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'aos_weather_data';"
EOF
    
else
    echo "📊 Creating AOS weather table..."
    
    # Copy SQL file
    scp -i $KEY_PATH services/sensor-data/sql/create-aos-table.sql $EC2_USER@$EC2_HOST:/tmp/
    
    # Execute SQL
    ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -f /tmp/create-aos-table.sql
echo "✅ AOS weather table created"
EOF
fi

# Step 2: Check data
echo ""
echo "📈 Checking for existing AOS data..."
ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \
  "SELECT COUNT(*) as record_count FROM aos_weather_data;"
  
echo ""
echo "Recent AOS data (if any):"
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \
  "SELECT time, station_id, temperature_c, rainfall_mm, humidity_pct 
   FROM aos_weather_data 
   ORDER BY time DESC 
   LIMIT 5;"
EOF

# Step 3: Insert test data
echo ""
read -p "Do you want to insert test AOS data? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📝 Inserting test AOS weather data..."
    
    ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data << 'EOSQL'
-- Insert test data for 3 AOS stations
INSERT INTO aos_weather_data (
    time, station_id, location_lat, location_lng,
    rainfall_mm, temperature_c, humidity_pct,
    wind_speed_ms, wind_direction_deg, pressure_hpa,
    solar_radiation_wm2, evapotranspiration_mm, quality_score
) VALUES
    -- Station AOS-001
    (NOW() - INTERVAL '1 hour', 'AOS-001', 13.7563, 100.5018, 
     0, 28.5, 75, 3.2, 180, 1013.25, 650, 4.2, 1.0),
    (NOW() - INTERVAL '30 minutes', 'AOS-001', 13.7563, 100.5018, 
     2.5, 28.2, 78, 2.8, 175, 1013.20, 620, 4.0, 1.0),
    (NOW(), 'AOS-001', 13.7563, 100.5018, 
     0.5, 28.8, 72, 3.5, 185, 1013.30, 680, 4.5, 1.0),
    
    -- Station AOS-002
    (NOW() - INTERVAL '1 hour', 'AOS-002', 14.3754, 102.8756, 
     0, 29.2, 68, 2.5, 220, 1012.80, 700, 5.0, 1.0),
    (NOW() - INTERVAL '30 minutes', 'AOS-002', 14.3754, 102.8756, 
     0, 29.5, 65, 2.8, 225, 1012.75, 720, 5.2, 1.0),
    (NOW(), 'AOS-002', 14.3754, 102.8756, 
     0, 29.8, 62, 3.0, 230, 1012.70, 740, 5.5, 1.0),
    
    -- Station AOS-003
    (NOW() - INTERVAL '1 hour', 'AOS-003', 13.9455, 100.7340, 
     5.0, 27.5, 85, 4.0, 90, 1011.50, 500, 3.5, 1.0),
    (NOW() - INTERVAL '30 minutes', 'AOS-003', 13.9455, 100.7340, 
     3.0, 27.2, 88, 3.5, 95, 1011.60, 480, 3.2, 1.0),
    (NOW(), 'AOS-003', 13.9455, 100.7340, 
     1.0, 27.8, 82, 3.8, 85, 1011.70, 520, 3.8, 1.0);
EOSQL

echo "✅ Test data inserted"

echo ""
echo "Verifying inserted data:"
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \
  "SELECT time, station_id, temperature_c, rainfall_mm, humidity_pct 
   FROM aos_weather_data 
   ORDER BY time DESC 
   LIMIT 9;"
EOF
fi

echo ""
echo "✅ AOS table deployment complete!"
echo ""
echo "📊 Table Summary:"
ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \
  "SELECT 
     station_id, 
     COUNT(*) as readings,
     MIN(time) as first_reading,
     MAX(time) as last_reading
   FROM aos_weather_data 
   GROUP BY station_id;"
EOF
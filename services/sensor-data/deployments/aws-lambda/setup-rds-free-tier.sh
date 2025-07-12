#!/bin/bash

# Setup RDS PostgreSQL Free Tier for Munbon Data API

echo "=== Setting up RDS PostgreSQL Free Tier ==="
echo ""

# Configuration
DB_INSTANCE_ID="munbon-postgres-free"
DB_NAME="munbon_sensor_data"
DB_USERNAME="munbon_admin"
DB_PASSWORD=$(openssl rand -base64 12)  # Generate secure password
VPC_SECURITY_GROUP_NAME="munbon-rds-lambda-sg"

echo "Generated secure password: $DB_PASSWORD"
echo "Please save this password securely!"
echo ""

# Create security group for RDS
echo "1. Creating security group..."
SECURITY_GROUP_ID=$(aws ec2 create-security-group \
    --group-name $VPC_SECURITY_GROUP_NAME \
    --description "Security group for Munbon RDS instance" \
    --query 'GroupId' \
    --output text 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "✅ Created security group: $SECURITY_GROUP_ID"
    
    # Allow PostgreSQL port from Lambda
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 5432 \
        --cidr 0.0.0.0/0 \
        2>/dev/null
else
    echo "⚠️  Security group might already exist, continuing..."
    SECURITY_GROUP_ID=$(aws ec2 describe-security-groups \
        --group-names $VPC_SECURITY_GROUP_NAME \
        --query 'SecurityGroups[0].GroupId' \
        --output text)
fi

# Create RDS instance
echo ""
echo "2. Creating RDS PostgreSQL instance (this takes 5-10 minutes)..."
aws rds create-db-instance \
    --db-instance-identifier $DB_INSTANCE_ID \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 15.4 \
    --master-username $DB_USERNAME \
    --master-user-password $DB_PASSWORD \
    --allocated-storage 20 \
    --storage-type gp2 \
    --vpc-security-group-ids $SECURITY_GROUP_ID \
    --backup-retention-period 7 \
    --no-multi-az \
    --publicly-accessible \
    --db-name $DB_NAME \
    --tags "Key=Project,Value=Munbon" "Key=Environment,Value=Development" \
    2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ RDS instance creation started"
else
    echo "❌ Failed to create RDS instance (might already exist)"
fi

# Wait for RDS instance to be available
echo ""
echo "3. Waiting for RDS instance to be available..."
echo "This usually takes 5-10 minutes. You can check status with:"
echo "aws rds describe-db-instances --db-instance-identifier $DB_INSTANCE_ID"

# Create .env file with connection details
cat > rds-connection.env << EOF
# RDS PostgreSQL Free Tier Connection Details
# Generated on: $(date)

RDS_INSTANCE_ID=$DB_INSTANCE_ID
RDS_HOSTNAME=\${RDS_ENDPOINT}  # Will be available after creation
RDS_PORT=5432
RDS_DATABASE=$DB_NAME
RDS_USERNAME=$DB_USERNAME
RDS_PASSWORD=$DB_PASSWORD

# Connection string format:
# postgresql://\${RDS_USERNAME}:\${RDS_PASSWORD}@\${RDS_HOSTNAME}:5432/\${RDS_DATABASE}

# For Lambda environment variables:
DB_HOST=\${RDS_ENDPOINT}
DB_PORT=5432
DB_NAME=$DB_NAME
DB_USER=$DB_USERNAME
DB_PASSWORD=$DB_PASSWORD
EOF

# Create database initialization script
cat > init-rds-database.sql << 'EOF'
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "timescaledb";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS sensor_data;

-- Create sensor registry table
CREATE TABLE IF NOT EXISTS sensor_data.sensors (
    sensor_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    location JSONB,
    zone VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create sensor readings table (will be converted to hypertable)
CREATE TABLE IF NOT EXISTS sensor_data.sensor_readings (
    time TIMESTAMPTZ NOT NULL,
    sensor_id VARCHAR(50) NOT NULL,
    data JSONB NOT NULL,
    quality INTEGER DEFAULT 100,
    FOREIGN KEY (sensor_id) REFERENCES sensor_data.sensors(sensor_id)
);

-- Create hypertable for time-series data
SELECT create_hypertable('sensor_data.sensor_readings', 'time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_time 
    ON sensor_data.sensor_readings (sensor_id, time DESC);

-- Insert sample sensors
INSERT INTO sensor_data.sensors (sensor_id, name, type, location, zone) VALUES
    ('wl001', 'Water Level Sensor 1', 'water_level', '{"lat": 14.1234, "lon": 102.5678}', 'Zone 1'),
    ('wl002', 'Water Level Sensor 2', 'water_level', '{"lat": 14.2234, "lon": 102.6678}', 'Zone 2'),
    ('m001', 'Moisture Sensor 1', 'moisture', '{"lat": 14.1534, "lon": 102.5978}', 'Zone 1'),
    ('m002', 'Moisture Sensor 2', 'moisture', '{"lat": 14.2534, "lon": 102.6978}', 'Zone 2'),
    ('aos001', 'Weather Station 1', 'weather', '{"lat": 14.1834, "lon": 102.6278}', 'Zone 1')
ON CONFLICT (sensor_id) DO NOTHING;

-- Insert sample data for testing
INSERT INTO sensor_data.sensor_readings (time, sensor_id, data) VALUES
    (NOW() - INTERVAL '1 hour', 'wl001', '{"water_level_m": 12.5, "flow_rate_m3s": 1.2}'),
    (NOW() - INTERVAL '30 minutes', 'wl001', '{"water_level_m": 12.6, "flow_rate_m3s": 1.3}'),
    (NOW(), 'wl001', '{"water_level_m": 12.7, "flow_rate_m3s": 1.4}');

EOF

echo ""
echo "=== Setup Instructions ==="
echo ""
echo "1. Wait for RDS instance to be available (5-10 minutes):"
echo "   aws rds describe-db-instances --db-instance-identifier $DB_INSTANCE_ID --query 'DBInstances[0].DBInstanceStatus'"
echo ""
echo "2. Get the RDS endpoint:"
echo "   aws rds describe-db-instances --db-instance-identifier $DB_INSTANCE_ID --query 'DBInstances[0].Endpoint.Address' --output text"
echo ""
echo "3. Initialize the database:"
echo "   psql -h <RDS_ENDPOINT> -U $DB_USERNAME -d $DB_NAME -f init-rds-database.sql"
echo ""
echo "4. Update Lambda environment variables with values from rds-connection.env"
echo ""
echo "Files created:"
echo "- rds-connection.env: Database connection details"
echo "- init-rds-database.sql: Database initialization script"
echo ""
echo "⚠️  IMPORTANT: This uses AWS Free Tier (750 hours/month for 12 months)"
echo "After 12 months, costs will be approximately $15-20/month for db.t3.micro"
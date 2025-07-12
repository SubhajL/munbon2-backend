#!/bin/bash

echo "Setting up ROS Service Database..."

# Database configuration
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5434}
DB_NAME=${DB_NAME:-munbon_ros}
DB_USER=${DB_USER:-postgres}
DB_PASSWORD=${DB_PASSWORD:-postgres123}

# Export password to avoid prompt
export PGPASSWORD=$DB_PASSWORD

# Check if database exists
if psql -h $DB_HOST -p $DB_PORT -U $DB_USER -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo "Database $DB_NAME already exists. Dropping and recreating..."
    psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "DROP DATABASE IF EXISTS $DB_NAME;"
fi

# Create database and run initialization script
echo "Creating database and tables..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "CREATE DATABASE $DB_NAME;"

# Run the SQL script
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f ./init-db.sql

if [ $? -eq 0 ]; then
    echo "Database setup completed successfully!"
    echo "Database: $DB_NAME"
    echo "Host: $DB_HOST:$DB_PORT"
    echo "User: $DB_USER"
else
    echo "Database setup failed!"
    exit 1
fi

# Unset password
unset PGPASSWORD
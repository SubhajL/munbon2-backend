#!/bin/bash

# Test database connection to new EC2
echo "Testing database connection to new EC2 instance..."

# Connection parameters
DB_HOST="${EC2_HOST:-43.208.201.191}"
DB_PORT="5432"
DB_NAME="postgres"
DB_USER="postgres"
DB_PASSWORD="P@ssw0rd123!"

# Test with psql
echo "Method 1: Using PGPASSWORD environment variable"
PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1 as connected;" 2>&1

# Test with connection string
echo -e "\nMethod 2: Using connection string"
psql "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=disable" -c "SELECT 1 as connected;" 2>&1

# Test with Python
echo -e "\nMethod 3: Using Python psycopg2"
python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='${DB_HOST}',
        port='${DB_PORT}',
        database='${DB_NAME}',
        user='${DB_USER}',
        password='${DB_PASSWORD}'
    )
    cursor = conn.cursor()
    cursor.execute('SELECT 1 as connected')
    print('✅ Connected successfully:', cursor.fetchone())
    conn.close()
except Exception as e:
    print('❌ Connection failed:', e)
" 2>&1
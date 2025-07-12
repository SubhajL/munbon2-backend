#!/bin/bash

# Setup PostgreSQL and TimescaleDB on Moonup Server
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================"
echo "Setup PostgreSQL + TimescaleDB on Moonup"
echo "======================================"
echo -e "${NC}"

# Create installation script for moonup server
cat > install-on-moonup.sh << 'EOF'
#!/bin/bash
# Run this script on the moonup server

# Install PostgreSQL 14 and TimescaleDB
echo "Installing PostgreSQL 14..."
sudo apt-get update
sudo apt-get install -y postgresql-14 postgresql-client-14 postgresql-contrib-14

# Add TimescaleDB repository
sudo sh -c "echo 'deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -
sudo apt-get update

# Install TimescaleDB
echo "Installing TimescaleDB..."
sudo apt-get install -y timescaledb-2-postgresql-14

# Configure PostgreSQL
echo "Configuring PostgreSQL..."
sudo timescaledb-tune --quiet --yes

# Configure PostgreSQL for remote access
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/14/main/postgresql.conf

# Add remote access rules
echo "host    all             all             0.0.0.0/0               md5" | sudo tee -a /etc/postgresql/14/main/pg_hba.conf

# Open firewall port
sudo ufw allow 5432/tcp
sudo ufw allow 5433/tcp  # For TimescaleDB on different port

# Restart PostgreSQL
sudo systemctl restart postgresql

# Create databases
sudo -u postgres psql << SQL
-- Create user for Munbon
CREATE USER munbon WITH PASSWORD 'munbon2024';

-- Create sensor_data database
CREATE DATABASE sensor_data OWNER munbon;

-- Connect to sensor_data and enable TimescaleDB
\c sensor_data
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE sensor_data TO munbon;
GRANT CREATE ON SCHEMA public TO munbon;
SQL

echo "PostgreSQL and TimescaleDB installed successfully!"
echo "Connection details:"
echo "  Host: moonup.hopto.org"
echo "  Port: 5432"
echo "  Database: sensor_data"
echo "  User: munbon"
echo "  Password: munbon2024"
EOF

# Create migration script
cat > migrate-to-moonup.sh << 'EOF'
#!/bin/bash
# Migrate existing data from local to moonup

echo "Migrating TimescaleDB data to moonup..."

# Export from local TimescaleDB
pg_dump -h localhost -p 5433 -U postgres -d sensor_data -f sensor_data_backup.sql

# Import to moonup
psql -h moonup.hopto.org -p 5432 -U munbon -d sensor_data -f sensor_data_backup.sql

echo "Migration complete!"
EOF

# Create unified API config for moonup
cat > src/unified-api-moonup.js << 'EOF'
// Unified API configured for all databases on moonup server
const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(cors());

// All databases now on moonup.hopto.org!
console.log('Unified API - All databases on moonup.hopto.org');

// TimescaleDB on moonup
const timescaleDB = new Pool({
  host: 'moonup.hopto.org',
  port: 5432,  // or 5433 if you run it on different port
  database: 'sensor_data',
  user: 'munbon',
  password: 'munbon2024',
  ssl: false
});

// MSSQL on moonup (already there)
const mssqlConfig = {
  server: 'moonup.hopto.org',
  database: 'db_scada',
  user: 'sa',
  password: 'bangkok1234',
  options: {
    encrypt: false,
    trustServerCertificate: true,
    port: 1433
  }
};

// Copy the rest of your API code here...
EOF

# Append the API endpoints
tail -n +45 src/unified-api-v2.js >> src/unified-api-moonup.js

# Create test script
cat > test-moonup-connection.js << 'EOF'
const { Pool } = require('pg');
const sql = require('mssql');

async function testConnections() {
    console.log('Testing connections to moonup.hopto.org...\n');
    
    // Test PostgreSQL/TimescaleDB
    const pgPool = new Pool({
        host: 'moonup.hopto.org',
        port: 5432,
        database: 'sensor_data',
        user: 'munbon',
        password: 'munbon2024'
    });
    
    try {
        const result = await pgPool.query('SELECT version()');
        console.log('✅ PostgreSQL connected:', result.rows[0].version);
        
        const tsResult = await pgPool.query("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'");
        if (tsResult.rows.length > 0) {
            console.log('✅ TimescaleDB version:', tsResult.rows[0].extversion);
        }
    } catch (err) {
        console.log('❌ PostgreSQL error:', err.message);
    } finally {
        await pgPool.end();
    }
    
    // Test MSSQL
    try {
        await sql.connect({
            server: 'moonup.hopto.org',
            database: 'db_scada',
            user: 'sa',
            password: 'bangkok1234',
            options: {
                encrypt: false,
                trustServerCertificate: true
            }
        });
        console.log('✅ MSSQL connected');
        await sql.close();
    } catch (err) {
        console.log('❌ MSSQL error:', err.message);
    }
}

testConnections();
EOF

# Create Render deployment config
cat > render-moonup.yaml << 'EOF'
services:
  - type: web
    name: munbon-unified-api
    runtime: node
    buildCommand: npm install --production
    startCommand: node src/unified-api-moonup.js
    healthCheckPath: /health
    envVars:
      - key: NODE_ENV
        value: production
      - key: PORT
        value: 3000
      - key: INTERNAL_API_KEY
        value: munbon-internal-f3b89263126548
      # All databases on moonup - no complex configs!
      - key: DB_HOST
        value: moonup.hopto.org
EOF

echo -e "\n${GREEN}======================================"
echo "Setup Scripts Created!"
echo "======================================"
echo -e "${NC}"
echo "Steps to set up on moonup:"
echo ""
echo "1. ${YELLOW}Copy install-on-moonup.sh to moonup server:${NC}"
echo "   scp install-on-moonup.sh user@moonup.hopto.org:~/"
echo ""
echo "2. ${YELLOW}SSH to moonup and run:${NC}"
echo "   ssh user@moonup.hopto.org"
echo "   chmod +x install-on-moonup.sh"
echo "   ./install-on-moonup.sh"
echo ""
echo "3. ${YELLOW}Migrate existing data:${NC}"
echo "   ./migrate-to-moonup.sh"
echo ""
echo "4. ${YELLOW}Test connections:${NC}"
echo "   node test-moonup-connection.js"
echo ""
echo "5. ${YELLOW}Deploy to Render with simple config!${NC}"
echo "   - No tunnels needed"
echo "   - All DBs in one place"
echo "   - Better reliability"
echo -e "${GREEN}======================================${NC}"
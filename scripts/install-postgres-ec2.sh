#!/bin/bash

# Install PostgreSQL 15 with PostGIS on Ubuntu EC2
# This installs PostgreSQL natively for better production performance

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== Installing PostgreSQL 15 with PostGIS on EC2 ===${NC}"

# Update system
echo -e "${BLUE}Updating system packages...${NC}"
sudo apt-get update
sudo apt-get upgrade -y

# Install PostgreSQL 15
echo -e "${BLUE}Installing PostgreSQL 15...${NC}"
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update
sudo apt-get install -y postgresql-15 postgresql-contrib-15

# Install PostGIS
echo -e "${BLUE}Installing PostGIS...${NC}"
sudo apt-get install -y postgresql-15-postgis-3 postgis

# Install TimescaleDB (optional - may not be needed if not using time-series features)
echo -e "${BLUE}Installing TimescaleDB...${NC}"
sudo add-apt-repository -y ppa:timescale/timescaledb-ppa
sudo apt-get update
sudo apt-get install -y timescaledb-2-postgresql-15 || echo -e "${YELLOW}TimescaleDB installation failed - continuing without it${NC}"

# Configure PostgreSQL
echo -e "${BLUE}Configuring PostgreSQL...${NC}"

# Backup original config
sudo cp /etc/postgresql/15/main/postgresql.conf /etc/postgresql/15/main/postgresql.conf.backup
sudo cp /etc/postgresql/15/main/pg_hba.conf /etc/postgresql/15/main/pg_hba.conf.backup

# Update PostgreSQL configuration for production
sudo tee -a /etc/postgresql/15/main/postgresql.conf > /dev/null << EOF

# Production settings
listen_addresses = 'localhost,172.17.0.1'  # Allow Docker containers to connect
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 2MB
min_wal_size = 1GB
max_wal_size = 4GB
EOF

# Allow connections from Docker containers
echo -e "${BLUE}Configuring authentication...${NC}"
sudo tee -a /etc/postgresql/15/main/pg_hba.conf > /dev/null << EOF

# Allow Docker containers
host    all             all             172.17.0.0/16           md5
host    all             all             172.18.0.0/16           md5
EOF

# Restart PostgreSQL
echo -e "${BLUE}Restarting PostgreSQL...${NC}"
sudo systemctl restart postgresql
sudo systemctl enable postgresql

# Set postgres user password
echo -e "${BLUE}Setting postgres user password...${NC}"
sudo -u postgres psql << EOF
ALTER USER postgres PASSWORD 'postgres123';
EOF

# Create databases
echo -e "${BLUE}Creating application databases...${NC}"
sudo -u postgres psql << EOF
-- Create databases
CREATE DATABASE sensor_data;
CREATE DATABASE auth_db;
CREATE DATABASE gis_db;
CREATE DATABASE ros_db;
CREATE DATABASE rid_db;
CREATE DATABASE weather_db;
CREATE DATABASE awd_db;
CREATE DATABASE munbon;

-- Enable extensions
\c gis_db
CREATE EXTENSION IF NOT EXISTS postgis;

\c sensor_data
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE sensor_data TO postgres;
GRANT ALL PRIVILEGES ON DATABASE auth_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE gis_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE ros_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE rid_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE weather_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE awd_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE munbon TO postgres;
EOF

# Setup backup directory
echo -e "${BLUE}Setting up backup directory...${NC}"
sudo mkdir -p /var/backups/postgresql
sudo chown postgres:postgres /var/backups/postgresql

# Create backup script
echo -e "${BLUE}Creating backup script...${NC}"
sudo tee /usr/local/bin/backup-postgres.sh > /dev/null << 'EOF'
#!/bin/bash
# PostgreSQL backup script
BACKUP_DIR="/var/backups/postgresql"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATABASES="sensor_data auth_db gis_db ros_db rid_db weather_db awd_db munbon"

for db in $DATABASES; do
    sudo -u postgres pg_dump $db | gzip > "$BACKUP_DIR/${db}_${TIMESTAMP}.sql.gz"
done

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
EOF

sudo chmod +x /usr/local/bin/backup-postgres.sh

# Setup daily backup cron
echo -e "${BLUE}Setting up daily backups...${NC}"
echo "0 2 * * * /usr/local/bin/backup-postgres.sh" | sudo crontab -u postgres -

# Display connection info
echo -e "\n${GREEN}=== PostgreSQL Installation Complete ===${NC}"
echo -e "${BLUE}Connection Information:${NC}"
echo "Host: localhost (from host machine)"
echo "Host: 172.17.0.1 (from Docker containers)"
echo "Port: 5432"
echo "Username: postgres"
echo "Password: postgres123"
echo ""
echo -e "${BLUE}Databases created:${NC}"
echo "- sensor_data (with TimescaleDB)"
echo "- auth_db"
echo "- gis_db (with PostGIS)"
echo "- ros_db"
echo "- rid_db"
echo "- weather_db"
echo "- awd_db"
echo "- munbon"
echo ""
echo -e "${BLUE}Backup location:${NC} /var/backups/postgresql"
echo -e "${BLUE}Backup schedule:${NC} Daily at 2:00 AM"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Update .env.ec2 with POSTGRES_HOST=172.17.0.1"
echo "2. Run: docker-compose -f docker-compose.ec2-native-db.yml up -d"
echo ""
echo -e "${GREEN}PostgreSQL is now running natively for better performance!${NC}"
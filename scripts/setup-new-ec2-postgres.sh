#!/bin/bash

# Script to set up PostgreSQL password on new EC2 instance
# Run this AFTER you have SSH access

set -e

EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"
NEW_POSTGRES_PASSWORD="postgres123"

echo "=== Setting up PostgreSQL on new EC2 instance ==="
echo "This script will:"
echo "1. Connect to EC2 via SSH"
echo "2. Set PostgreSQL password"
echo "3. Update pg_hba.conf if needed"
echo "4. Restart PostgreSQL"
echo ""

# First, test SSH connection
echo "Testing SSH connection..."
if ssh -o ConnectTimeout=5 -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "echo 'SSH connection successful'"; then
    echo "✅ SSH connection works!"
else
    echo "❌ SSH connection failed!"
    echo ""
    echo "Please ensure:"
    echo "1. Security Group allows SSH (port 22) from your IP"
    echo "2. The instance was created with the th-lab01 key pair"
    echo "3. The instance is running"
    exit 1
fi

# Set up PostgreSQL
echo ""
echo "Setting up PostgreSQL..."
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'REMOTE_COMMANDS'
# Check if PostgreSQL is running
if ! systemctl is-active --quiet postgresql; then
    echo "PostgreSQL is not running. Starting it..."
    sudo systemctl start postgresql
fi

# Set postgres user password
echo "Setting PostgreSQL password..."
sudo -u postgres psql << EOF
ALTER USER postgres PASSWORD 'postgres123';
\q
EOF

# Ensure PostgreSQL accepts password authentication
echo "Checking pg_hba.conf..."
PG_VERSION=$(sudo -u postgres psql -t -c "SELECT version();" | grep -oP '\d+\.\d+' | head -1)
PG_CONFIG="/etc/postgresql/$PG_VERSION/main/pg_hba.conf"

if [ -f "$PG_CONFIG" ]; then
    # Backup original
    sudo cp "$PG_CONFIG" "$PG_CONFIG.backup"
    
    # Ensure password authentication for all connections
    sudo sed -i 's/local   all             postgres                                peer/local   all             postgres                                md5/' "$PG_CONFIG"
    sudo sed -i 's/local   all             all                                     peer/local   all             all                                     md5/' "$PG_CONFIG"
    
    # Ensure remote connections are allowed
    if ! grep -q "host    all             all             0.0.0.0/0" "$PG_CONFIG"; then
        echo "host    all             all             0.0.0.0/0               md5" | sudo tee -a "$PG_CONFIG"
    fi
    
    # Update postgresql.conf to listen on all interfaces
    PG_CONF="/etc/postgresql/$PG_VERSION/main/postgresql.conf"
    sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" "$PG_CONF"
    
    # Restart PostgreSQL
    echo "Restarting PostgreSQL..."
    sudo systemctl restart postgresql
    
    echo "✅ PostgreSQL configured successfully!"
else
    echo "⚠️  Could not find pg_hba.conf. PostgreSQL might be in a Docker container."
fi

# Test the connection
echo ""
echo "Testing PostgreSQL connection..."
PGPASSWORD='postgres123' psql -h localhost -U postgres -c "SELECT 1;" && echo "✅ Local connection works!"

REMOTE_COMMANDS

echo ""
echo "=== Setup Complete ==="
echo "PostgreSQL password has been set to: postgres123"
echo ""
echo "Test from your local machine:"
echo "PGPASSWORD=postgres123 psql -h $EC2_HOST -p 5432 -U postgres -l"
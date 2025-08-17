#!/bin/bash
# Source this file in your scripts to get EC2 configuration
# Usage: source ./load-ec2-config.sh

# Load from .env file if it exists
if [ -f .env ]; then
    export $(grep -E '^EC2_HOST=|^POSTGRES_|^TIMESCALE_|^DATABASE_URL=|^TIMESCALE_URL=' .env | xargs)
fi

# Set defaults if not already set
export EC2_HOST="${EC2_HOST:-43.208.201.191}"
export EC2_SSH_USER="${EC2_SSH_USER:-ubuntu}"
export EC2_SSH_KEY_PATH="${EC2_SSH_KEY_PATH:-./th-lab01.pem}"

# Database configurations
export POSTGRES_HOST="${POSTGRES_HOST:-$EC2_HOST}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_DB="${POSTGRES_DB:-munbon_dev}"

export TIMESCALE_HOST="${TIMESCALE_HOST:-$EC2_HOST}"
export TIMESCALE_PORT="${TIMESCALE_PORT:-5432}"
export TIMESCALE_USER="${TIMESCALE_USER:-postgres}"
export TIMESCALE_DB="${TIMESCALE_DB:-sensor_data}"

# URLs
export DATABASE_URL="${DATABASE_URL:-postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB}"
export TIMESCALE_URL="${TIMESCALE_URL:-postgresql://$TIMESCALE_USER:$TIMESCALE_PASSWORD@$TIMESCALE_HOST:$TIMESCALE_PORT/$TIMESCALE_DB}"

echo "EC2 Configuration Loaded:"
echo "  EC2_HOST: $EC2_HOST"
echo "  POSTGRES_HOST: $POSTGRES_HOST"
echo "  TIMESCALE_HOST: $TIMESCALE_HOST"

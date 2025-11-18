#!/bin/bash
# Run migration 005 to relax constraints and update SF-U3, SF-U6

set -e

# Load environment variables
if [ -f "../../../../.env" ]; then
  export $(grep -v '^#' ../../../../.env | xargs)
elif [ -f "../../../.env" ]; then
  export $(grep -v '^#' ../../../.env | xargs)
fi

# Check if TIMESCALE_URL is set
if [ -z "$TIMESCALE_URL" ]; then
  echo "Error: TIMESCALE_URL environment variable is not set"
  echo "Please set it or run: source load-credentials.sh"
  exit 1
fi

echo "Running migration 005 on AWS munbon_dev database..."
echo "Database: $TIMESCALE_URL (host masked)"

# Run the migration
psql "$TIMESCALE_URL" -f 005_relax_constraints_and_update_plots.sql

echo ""
echo "✓ Migration completed successfully"
echo ""
echo "Verifying current state of SF-U3 and SF-U6..."
psql "$TIMESCALE_URL" -c "SELECT plot_id, crop_type, control_mode, updated_at, updated_by FROM water_control_smartfarm.plot_configurations WHERE plot_id IN ('SF-U3', 'SF-U6') ORDER BY plot_id;"

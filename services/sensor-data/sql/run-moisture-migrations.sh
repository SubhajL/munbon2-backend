#!/bin/bash
set -euo pipefail

# Run moisture migrations and checks on TimescaleDB
# Usage: ./run-moisture-migrations.sh [check|convert]

cd "$(dirname "$0")"

DB_HOST="${TIMESCALE_HOST:-43.208.201.191}"
DB_PORT="${TIMESCALE_PORT:-5432}"
DB_NAME="${TIMESCALE_DB:-sensor_data}"
DB_USER="${TIMESCALE_USER:-postgres}"
DB_PASSWORD="${TIMESCALE_PASSWORD:-P@ssw0rd123!}"

run_query() {
  local q=$1
  PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -X -t -c "$q"
}

run_file() {
  local f=$1
  PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -X -f "$f"
}

cmd=${1:-check}

case "$cmd" in
  check)
    echo "=== Checking timezone and moisture table column types ==="
    echo -n "Server time zone: "; run_query "SHOW TIME ZONE;"
    echo "Columns:" 
    run_query "SELECT table_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('moisture_readings','smoothed_moisture_readings','water_level_readings','smoothed_water_level_readings') AND column_name='time' ORDER BY table_name;"
    echo "\nRecent moisture_readings rows (UTC vs Bangkok):"
    run_query "SELECT sensor_id, time, time AT TIME ZONE 'UTC' AS as_utc, time AT TIME ZONE 'Asia/Bangkok' AS as_bkk FROM moisture_readings ORDER BY time DESC LIMIT 5;"
    echo "\nRecent smoothed_moisture_readings rows (UTC vs Bangkok):"
    run_query "SELECT sensor_id, time, time AT TIME ZONE 'UTC' AS as_utc, time AT TIME ZONE 'Asia/Bangkok' AS as_bkk FROM smoothed_moisture_readings ORDER BY time DESC LIMIT 5;"
    ;;
  convert)
    echo "=== Converting moisture time columns to TIMESTAMPTZ (interpreting as UTC) ==="
    run_file "moisture/10_convert_time_columns_to_timestamptz.sql"
    echo "=== Verifying column types after conversion ==="
    run_query "SELECT table_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('moisture_readings','smoothed_moisture_readings') AND column_name='time' ORDER BY table_name;"
    ;;
  *)
    echo "Usage: $0 [check|convert]"
    exit 1
    ;;
esac

echo "Done."


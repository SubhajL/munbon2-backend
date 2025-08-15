#!/bin/bash

echo "=== Water Level Dual-Write Monitor ==="
echo "Starting at: $(date)"
echo "Monitoring for new water level sensor data..."
echo ""

# Get initial counts
LOCAL_COUNT_BEFORE=$(docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -t -c "SELECT COUNT(*) FROM water_level_readings")
EC2_COUNT_BEFORE=$(ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 "docker exec timescaledb psql -U postgres -d sensor_data -t -c 'SELECT COUNT(*) FROM water_level_readings'" 2>/dev/null)

echo "Initial counts:"
echo "  Local DB: $LOCAL_COUNT_BEFORE records"
echo "  EC2 DB:   $EC2_COUNT_BEFORE records"
echo ""
echo "Monitoring for new data (press Ctrl+C to stop)..."
echo ""

# Monitor in real-time
while true; do
    # Check for new water level data in local DB
    LATEST_LOCAL=$(docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -t -c "
        SELECT time || ' | ' || sensor_id || ' | ' || level_cm || 'cm'
        FROM water_level_readings 
        WHERE time > NOW() - INTERVAL '1 minute'
        ORDER BY time DESC 
        LIMIT 1")
    
    if [ ! -z "$LATEST_LOCAL" ] && [ "$LATEST_LOCAL" != "$LAST_LOCAL" ]; then
        echo "[$(date +%H:%M:%S)] NEW DATA in LOCAL DB:"
        echo "  $LATEST_LOCAL"
        
        # Check if same data appears in EC2
        sleep 2  # Give dual-write time to complete
        
        LATEST_EC2=$(ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 "docker exec timescaledb psql -U postgres -d sensor_data -t -c \"
            SELECT time || ' | ' || sensor_id || ' | ' || level_cm || 'cm'
            FROM water_level_readings 
            WHERE time > NOW() - INTERVAL '1 minute'
            ORDER BY time DESC 
            LIMIT 1\"" 2>/dev/null)
        
        if [ ! -z "$LATEST_EC2" ]; then
            echo "  ✅ DUAL-WRITE SUCCESS - Data also in EC2 DB:"
            echo "     $LATEST_EC2"
        else
            echo "  ❌ DUAL-WRITE FAILED - Data NOT in EC2 DB"
            
            # Check consumer logs for errors
            echo "  Checking logs for errors..."
            pm2 logs sensor-consumer --lines 5 --nostream | grep -i "error\|EC2" | tail -3
        fi
        
        LAST_LOCAL="$LATEST_LOCAL"
        echo ""
    fi
    
    sleep 5
done
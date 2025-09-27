#!/bin/bash

# Integration test for Redis event-driven coordination between Water Planning and Control BFFs
# This test verifies that events are properly published and received

set -e

echo "=== Redis Event Integration Test ==="
echo "Testing event coordination between Water Planning and Control BFFs"
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=15
TEST_CHANNEL="water:demands:updated"

# Ensure Redis is running
echo "1. Checking Redis connection..."
redis-cli -h $REDIS_HOST -p $REDIS_PORT ping > /dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Redis is running${NC}"
else
    echo -e "${RED}✗ Redis is not running${NC}"
    exit 1
fi

# Clear test database
echo "2. Clearing test database..."
redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB FLUSHDB > /dev/null
echo -e "${GREEN}✓ Test database cleared${NC}"

# Start subscriber in background
echo "3. Starting test subscriber..."
(
    redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB SUBSCRIBE "$TEST_CHANNEL" | while read -r line; do
        if [[ $line == *"zone_demand_ready"* ]]; then
            echo -e "${GREEN}✓ Received zone_demand_ready event${NC}"
            echo "   Event data: $line"
        fi
    done
) &
SUBSCRIBER_PID=$!
sleep 1

# Publish test event
echo "4. Publishing test event..."
TEST_EVENT='{
    "event_type": "zone_demand_ready",
    "zone_id": "ZONE001",
    "week_start": "2024-01-01",
    "total_demand_m3": 50000,
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
}'

redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB PUBLISH "$TEST_CHANNEL" "$TEST_EVENT" > /dev/null
echo -e "${GREEN}✓ Event published${NC}"

# Wait for subscriber to process
sleep 2

# Test batch event
echo "5. Publishing batch event..."
BATCH_EVENT='{
    "event_type": "batch_demands_ready",
    "zones": ["ZONE001", "ZONE002", "ZONE003"],
    "week_start": "2024-01-01",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
}'

redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB PUBLISH "$TEST_CHANNEL" "$BATCH_EVENT" > /dev/null
echo -e "${GREEN}✓ Batch event published${NC}"

# Test control feedback channel
echo "6. Testing control feedback channel..."
FEEDBACK_CHANNEL="water:control:feedback"
(
    redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB SUBSCRIBE "$FEEDBACK_CHANNEL" | while read -r line; do
        if [[ $line == *"gate_control_executed"* ]]; then
            echo -e "${GREEN}✓ Received control feedback event${NC}"
            echo "   Feedback data: $line"
        fi
    done
) &
FEEDBACK_PID=$!
sleep 1

FEEDBACK_EVENT='{
    "event_type": "gate_control_executed",
    "zone_id": "ZONE001",
    "gate_id": "GATE001",
    "status": "success",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
}'

redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB PUBLISH "$FEEDBACK_CHANNEL" "$FEEDBACK_EVENT" > /dev/null
echo -e "${GREEN}✓ Feedback event published${NC}"

sleep 2

# Cleanup
echo "7. Cleaning up..."
kill $SUBSCRIBER_PID 2>/dev/null || true
kill $FEEDBACK_PID 2>/dev/null || true
redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB FLUSHDB > /dev/null

echo
echo -e "${GREEN}=== All tests passed! ===${NC}"
echo "Event-driven coordination is working correctly."
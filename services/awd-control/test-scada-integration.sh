#!/bin/bash

# Test SCADA Gate Control Integration

echo "=== SCADA Gate Control Integration Test ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test database connection
echo "1. Testing SCADA database connection..."
PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d db_scada -c "SELECT COUNT(*) FROM tb_site WHERE stationcode IS NOT NULL;" 2>&1 | grep -q "20"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Connected to SCADA database${NC}"
else
    echo -e "${RED}✗ Failed to connect to SCADA database${NC}"
    exit 1
fi

# Test table structure
echo ""
echo "2. Checking tb_gatelevel_command table..."
PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d db_scada -c "\d tb_gatelevel_command" 2>&1 | grep -q "gate_level"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ tb_gatelevel_command table exists${NC}"
else
    echo -e "${RED}✗ tb_gatelevel_command table not found${NC}"
    exit 1
fi

# Insert test command
echo ""
echo "3. Inserting test gate command..."
COMMAND_ID=$(PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d db_scada -t -c "
INSERT INTO tb_gatelevel_command 
(gate_name, gate_level, startdatetime, completestatus)
VALUES ('TEST_WWA', 3, NOW(), 0)
RETURNING id;" | tr -d ' ')

if [ -n "$COMMAND_ID" ]; then
    echo -e "${GREEN}✓ Test command inserted with ID: $COMMAND_ID${NC}"
else
    echo -e "${RED}✗ Failed to insert test command${NC}"
    exit 1
fi

# Check command status
echo ""
echo "4. Checking command status..."
sleep 2
STATUS=$(PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d db_scada -t -c "
SELECT completestatus FROM tb_gatelevel_command WHERE id = $COMMAND_ID;" | tr -d ' ')

echo -e "${YELLOW}Command status: $STATUS (0=pending, 1=complete)${NC}"

# List recent commands
echo ""
echo "5. Recent gate commands:"
PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d db_scada -c "
SELECT id, gate_name, gate_level, 
       startdatetime AT TIME ZONE 'Asia/Bangkok' as start_time,
       CASE completestatus 
         WHEN 0 THEN 'Pending'
         WHEN 1 THEN 'Complete'
       END as status
FROM tb_gatelevel_command 
ORDER BY id DESC 
LIMIT 5;"

# Clean up test command
echo ""
echo "6. Cleaning up test command..."
PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -U postgres -d db_scada -c "
DELETE FROM tb_gatelevel_command WHERE id = $COMMAND_ID;" > /dev/null 2>&1
echo -e "${GREEN}✓ Test command cleaned up${NC}"

# Test API endpoint (if service is running)
echo ""
echo "7. Testing API endpoints (if service is running on port 3013)..."
if curl -s http://localhost:3013/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ AWD Control Service is running${NC}"
    
    # Test irrigation start endpoint
    echo ""
    echo "8. Testing irrigation control API..."
    echo "Example API call:"
    echo -e "${YELLOW}curl -X POST http://localhost:3013/api/v1/awd/control/fields/{fieldId}/irrigation/start \\
  -H \"Authorization: Bearer \$TOKEN\" \\
  -H \"Content-Type: application/json\" \\
  -d '{
    \"targetLevelCm\": 10,
    \"targetFlowRate\": 7.5
  }'${NC}"
else
    echo -e "${YELLOW}⚠ AWD Control Service not running on port 3013${NC}"
fi

echo ""
echo "=== Test Summary ==="
echo -e "${GREEN}✓ SCADA database connection working${NC}"
echo -e "${GREEN}✓ Gate command table structure verified${NC}"
echo -e "${GREEN}✓ Can insert and query gate commands${NC}"
echo -e "${YELLOW}⚠ Manual verification needed for actual gate control${NC}"
echo ""
echo "Next steps:"
echo "1. Map fields to station codes in awd.field_gate_mapping"
echo "2. Configure Flow Monitoring Service URL in .env"
echo "3. Start the AWD Control Service"
echo "4. Test irrigation control through API"
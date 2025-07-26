#!/bin/bash

echo "=== Diagnosing Consumer Service ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if consumer container exists
echo "1. Checking if consumer container is running..."
if docker ps | grep -q "sensor-data-consumer"; then
    echo -e "${GREEN}✅ Consumer container is running${NC}"
    CONTAINER_ID=$(docker ps | grep "sensor-data-consumer" | awk '{print $1}')
    echo "   Container ID: $CONTAINER_ID"
else
    echo -e "${RED}❌ Consumer container is NOT running${NC}"
    echo "   Checking if container exists but stopped..."
    if docker ps -a | grep -q "sensor-data-consumer"; then
        echo -e "${YELLOW}⚠️  Container exists but is stopped${NC}"
    else
        echo -e "${RED}❌ Container doesn't exist${NC}"
    fi
fi

echo ""
echo "2. Checking AWS credentials in container..."
if [ ! -z "$CONTAINER_ID" ]; then
    AWS_KEY=$(docker exec $CONTAINER_ID env | grep AWS_ACCESS_KEY_ID)
    if [ ! -z "$AWS_KEY" ]; then
        echo -e "${GREEN}✅ AWS credentials are set${NC}"
        docker exec $CONTAINER_ID env | grep -E 'AWS_|SQS_' | sed 's/^/   /'
    else
        echo -e "${RED}❌ AWS credentials are NOT set${NC}"
    fi
fi

echo ""
echo "3. Checking recent consumer logs..."
if [ ! -z "$CONTAINER_ID" ]; then
    echo "Last 20 lines of consumer logs:"
    docker logs --tail 20 $CONTAINER_ID 2>&1 | sed 's/^/   /'
fi

echo ""
echo "4. Checking database connection..."
if [ ! -z "$CONTAINER_ID" ]; then
    if docker exec $CONTAINER_ID sh -c 'PGPASSWORD=$TIMESCALE_PASSWORD psql -h $TIMESCALE_HOST -U $TIMESCALE_USER -d $TIMESCALE_DB -c "SELECT NOW()" 2>/dev/null' > /dev/null; then
        echo -e "${GREEN}✅ Database connection successful${NC}"
    else
        echo -e "${RED}❌ Database connection failed${NC}"
    fi
fi

echo ""
echo "5. Checking environment file..."
if [ -f ".env" ]; then
    echo -e "${GREEN}✅ .env file exists${NC}"
    if grep -q "AWS_ACCESS_KEY_ID" .env; then
        echo -e "${GREEN}✅ AWS credentials in .env${NC}"
    else
        echo -e "${RED}❌ AWS credentials missing in .env${NC}"
    fi
else
    echo -e "${RED}❌ .env file not found${NC}"
    if [ -f ".env.ec2" ]; then
        echo -e "${YELLOW}⚠️  .env.ec2 exists but .env is missing${NC}"
        echo "   Run: cp .env.ec2 .env"
    fi
fi

echo ""
echo "=== Recommended Actions ==="

if ! docker ps | grep -q "sensor-data-consumer"; then
    echo "1. Start the consumer service:"
    echo "   docker-compose -f docker-compose.ec2-consolidated.yml up -d sensor-data-consumer"
fi

if [ ! -f ".env" ] && [ -f ".env.ec2" ]; then
    echo "2. Copy environment file:"
    echo "   cp .env.ec2 .env"
fi

echo ""
echo "3. To restart consumer with fresh state:"
echo "   docker-compose -f docker-compose.ec2-consolidated.yml restart sensor-data-consumer"
echo ""
echo "4. To see live logs:"
echo "   docker-compose -f docker-compose.ec2-consolidated.yml logs -f sensor-data-consumer"
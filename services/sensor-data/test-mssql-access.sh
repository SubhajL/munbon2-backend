#!/bin/bash

# Test MSSQL Access and Troubleshooting Script
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================"
echo "MSSQL Connection Test & Troubleshooting"
echo "======================================"
echo -e "${NC}"

MSSQL_HOST="moonup.hopto.org"
MSSQL_PORT="1433"

# Test 1: DNS Resolution
echo -e "${YELLOW}1. Testing DNS resolution...${NC}"
if nslookup $MSSQL_HOST > /dev/null 2>&1; then
    IP=$(nslookup $MSSQL_HOST | grep -A1 "Name:" | grep "Address:" | tail -1 | awk '{print $2}')
    echo -e "${GREEN}✓ DNS resolved to: $IP${NC}"
else
    echo -e "${RED}✗ DNS resolution failed${NC}"
    exit 1
fi

# Test 2: Ping Test
echo -e "\n${YELLOW}2. Testing basic connectivity...${NC}"
if ping -c 2 $MSSQL_HOST > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Host is reachable${NC}"
else
    echo -e "${RED}✗ Host is not pingable (might be firewall)${NC}"
fi

# Test 3: Port Scan
echo -e "\n${YELLOW}3. Testing MSSQL port $MSSQL_PORT...${NC}"
if nc -zv -w 5 $MSSQL_HOST $MSSQL_PORT 2>&1 | grep -q "succeeded\|connected"; then
    echo -e "${GREEN}✓ Port $MSSQL_PORT is open${NC}"
else
    echo -e "${RED}✗ Port $MSSQL_PORT is closed or filtered${NC}"
    
    # Try alternative ports
    echo -e "${YELLOW}   Trying alternative SQL Server ports...${NC}"
    for port in 1434 1435 2433 3433 14330; do
        if nc -zv -w 2 $MSSQL_HOST $port 2>&1 | grep -q "succeeded\|connected"; then
            echo -e "${GREEN}   ✓ Port $port is open - SQL Server might be on this port${NC}"
        fi
    done
fi

# Test 4: Telnet Test
echo -e "\n${YELLOW}4. Testing with telnet...${NC}"
echo "quit" | telnet $MSSQL_HOST $MSSQL_PORT 2>&1 | head -10

# Test 5: Common Issues
echo -e "\n${BLUE}======================================"
echo "Common Solutions:"
echo "======================================${NC}"

echo -e "${YELLOW}If connection is blocked:${NC}"
echo "1. Check if you're behind a corporate firewall"
echo "2. Try using a VPN"
echo "3. Use SSH tunnel through a server that has access"
echo "4. Contact the MSSQL administrator to whitelist your IP"

echo -e "\n${YELLOW}Your current public IP:${NC}"
curl -s ifconfig.me && echo

echo -e "\n${YELLOW}To create SSH tunnel:${NC}"
echo "ssh -L 1433:$MSSQL_HOST:1433 user@intermediate-server"
echo "Then connect to localhost:1433"

# Test 6: Node.js Connection Test
echo -e "\n${YELLOW}5. Testing with Node.js mssql module...${NC}"
cat > test-mssql-direct.js << 'EOF'
const sql = require('mssql');

const config = {
    server: 'moonup.hopto.org',
    port: 1433,
    database: 'db_scada',
    user: 'sa',
    password: 'bangkok1234',
    options: {
        encrypt: false,
        trustServerCertificate: true,
        connectTimeout: 30000,
        requestTimeout: 30000
    }
};

console.log('Attempting to connect to MSSQL...');
console.log('Config:', { ...config, password: '***' });

sql.connect(config)
    .then(pool => {
        console.log('✓ Connected successfully!');
        return pool.request().query('SELECT @@VERSION as version');
    })
    .then(result => {
        console.log('✓ Query successful!');
        console.log('SQL Server Version:', result.recordset[0].version);
        sql.close();
    })
    .catch(err => {
        console.error('✗ Connection failed:', err.message);
        if (err.code === 'ECONNREFUSED') {
            console.log('\nPossible solutions:');
            console.log('1. Port 1433 is blocked by firewall');
            console.log('2. SQL Server is not configured for remote access');
            console.log('3. Try using a VPN or SSH tunnel');
        }
        if (err.code === 'ETIMEOUT') {
            console.log('\nConnection timed out. The server might be:');
            console.log('1. Behind a firewall that drops packets');
            console.log('2. Not accessible from your network');
            console.log('3. Using a different port');
        }
    });

setTimeout(() => {
    console.log('\nTest complete');
    process.exit(0);
}, 35000);
EOF

if command -v node > /dev/null 2>&1; then
    echo "Running Node.js connection test..."
    node test-mssql-direct.js
else
    echo -e "${YELLOW}Node.js not found, skipping Node.js test${NC}"
fi

echo -e "\n${BLUE}======================================"
echo "Test Complete"
echo "======================================${NC}"
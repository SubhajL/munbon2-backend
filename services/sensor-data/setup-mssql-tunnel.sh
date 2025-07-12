#!/bin/bash

# Setup MSSQL Access Solutions
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================"
echo "MSSQL Access Solutions"
echo "======================================"
echo -e "${NC}"

# Solution 1: SSH Tunnel
echo -e "${GREEN}Solution 1: SSH Tunnel${NC}"
cat > ssh-tunnel-mssql.sh << 'EOF'
#!/bin/bash
# If you have SSH access to a server that can reach moonup.hopto.org

SSH_HOST="your-server.com"
SSH_USER="your-username"
LOCAL_PORT=1433
REMOTE_HOST="moonup.hopto.org"
REMOTE_PORT=1433

echo "Creating SSH tunnel..."
ssh -N -L $LOCAL_PORT:$REMOTE_HOST:$REMOTE_PORT $SSH_USER@$SSH_HOST

# Now connect to localhost:1433 instead of moonup.hopto.org:1433
EOF
chmod +x ssh-tunnel-mssql.sh

# Solution 2: VPN Setup
echo -e "\n${GREEN}Solution 2: VPN Options${NC}"
cat > vpn-options.md << 'EOF'
# VPN Solutions for MSSQL Access

## Free VPN Options:
1. **ProtonVPN** (free tier available)
   - Download: https://protonvpn.com
   - Connect to any server
   - Try accessing moonup.hopto.org:1433

2. **Windscribe** (10GB/month free)
   - Download: https://windscribe.com
   - Good for testing

3. **TunnelBear** (500MB/month free)
   - Download: https://tunnelbear.com
   - Limited but works for testing

## After VPN Connection:
Test with: `nc -zv moonup.hopto.org 1433`
EOF

# Solution 3: Cloudflare Tunnel for MSSQL
echo -e "\n${GREEN}Solution 3: Cloudflare Tunnel${NC}"
cat > cloudflare-mssql-tunnel.sh << 'EOF'
#!/bin/bash
# Create a Cloudflare tunnel to access MSSQL

# Install cloudflared
brew install cloudflared

# Login to Cloudflare
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create mssql-tunnel

# Create config file
cat > ~/.cloudflared/config.yml << EOCONFIG
tunnel: mssql-tunnel
credentials-file: ~/.cloudflared/[TUNNEL_ID].json

ingress:
  - hostname: mssql.yourdomain.com
    service: tcp://moonup.hopto.org:1433
  - service: http_status:404
EOCONFIG

# Run tunnel
cloudflared tunnel run mssql-tunnel
EOF
chmod +x cloudflare-mssql-tunnel.sh

# Solution 4: Port Forwarding Service
echo -e "\n${GREEN}Solution 4: ngrok TCP Tunnel${NC}"
cat > ngrok-mssql.sh << 'EOF'
#!/bin/bash
# Use ngrok to create a public tunnel to MSSQL

# First, you need a server that can access moonup.hopto.org
# SSH to that server and run:

# Install ngrok on the intermediate server
wget https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-amd64.zip
unzip ngrok-stable-linux-amd64.zip

# Create tunnel from intermediate server to MSSQL
./ngrok tcp moonup.hopto.org:1433

# You'll get a URL like: tcp://0.tcp.ngrok.io:12345
# Use this URL in your local connection
EOF
chmod +x ngrok-mssql.sh

# Solution 5: Local Testing Alternative
echo -e "\n${GREEN}Solution 5: Local SQL Server for Testing${NC}"
cat > docker-mssql-local.sh << 'EOF'
#!/bin/bash
# Run MSSQL locally in Docker for testing

docker run -e "ACCEPT_EULA=Y" -e "SA_PASSWORD=YourStrong@Passw0rd" \
   -p 1433:1433 --name sql_server_local \
   -d mcr.microsoft.com/mssql/server:2019-latest

echo "Local MSSQL running on localhost:1433"
echo "Username: sa"
echo "Password: YourStrong@Passw0rd"

# Import test data
echo "You can now import your schema and test data"
EOF
chmod +x docker-mssql-local.sh

# Create connection test with different methods
cat > test-all-connections.js << 'EOF'
const sql = require('mssql');

const configs = [
    {
        name: 'Direct Connection',
        server: 'moonup.hopto.org',
        port: 1433
    },
    {
        name: 'Via SSH Tunnel (localhost)',
        server: 'localhost',
        port: 1433
    },
    {
        name: 'Alternative Port 1',
        server: 'moonup.hopto.org',
        port: 14330
    },
    {
        name: 'Alternative Port 2',
        server: 'moonup.hopto.org',
        port: 2433
    }
];

async function testConnection(config) {
    const fullConfig = {
        ...config,
        database: 'db_scada',
        user: 'sa',
        password: 'bangkok1234',
        options: {
            encrypt: false,
            trustServerCertificate: true,
            connectTimeout: 10000
        }
    };

    console.log(`\nTesting: ${config.name}`);
    console.log(`Server: ${config.server}:${config.port}`);
    
    try {
        const pool = await sql.connect(fullConfig);
        console.log('✅ Connected successfully!');
        await pool.close();
    } catch (err) {
        console.log('❌ Failed:', err.message);
    }
}

async function testAll() {
    for (const config of configs) {
        await testConnection(config);
    }
}

testAll().then(() => {
    console.log('\nAll tests complete');
    process.exit(0);
});
EOF

# Create quick fix script
cat > quick-fix-mssql.sh << 'EOF'
#!/bin/bash

echo "Quick MSSQL Access Fixes:"
echo ""
echo "1. Check your IP is whitelisted:"
echo "   Your IP: $(curl -s ifconfig.me)"
echo ""
echo "2. Try with telnet:"
echo "   telnet moonup.hopto.org 1433"
echo ""
echo "3. Try with VPN:"
echo "   - Connect to any VPN"
echo "   - Test again"
echo ""
echo "4. Use Azure Data Studio:"
echo "   - Download: https://docs.microsoft.com/en-us/sql/azure-data-studio/"
echo "   - Sometimes works when others fail"
echo ""
echo "5. Contact admin to whitelist:"
echo "   - Your IP: $(curl -s ifconfig.me)"
echo "   - Ask them to allow port 1433"
EOF
chmod +x quick-fix-mssql.sh

echo -e "\n${BLUE}======================================"
echo "Solutions Created!"
echo "======================================"
echo -e "${NC}"
echo "Try these in order:"
echo "1. ${YELLOW}./test-mssql-access.sh${NC} - Diagnose the issue"
echo "2. ${YELLOW}./quick-fix-mssql.sh${NC} - Quick solutions"
echo "3. Use a VPN service (see vpn-options.md)"
echo "4. Set up SSH tunnel if you have a server with access"
echo "5. Run MSSQL locally with Docker for testing"
echo ""
echo "Most likely solution: ${GREEN}Use a VPN${NC} to bypass network restrictions"
echo -e "${BLUE}======================================${NC}"
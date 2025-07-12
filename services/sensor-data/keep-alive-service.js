#!/usr/bin/env node

// Simple Keep-Alive Service for Render.com
// Can run on your local machine, another server, or as a scheduled task

const https = require('https');
const http = require('http');

// Configuration
const config = {
    services: [
        {
            name: 'Munbon Unified API',
            url: process.env.RENDER_URL || 'https://munbon-unified-api.onrender.com',
            endpoints: ['/health', '/wake-up'],
            interval: 5 * 60 * 1000  // 5 minutes
        }
    ],
    port: process.env.PORT || 3001
};

// Colors for console
const colors = {
    reset: '\x1b[0m',
    bright: '\x1b[1m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    red: '\x1b[31m',
    blue: '\x1b[34m'
};

// Ping function
async function pingEndpoint(service, endpoint) {
    const url = `${service.url}${endpoint}`;
    const startTime = Date.now();
    
    return new Promise((resolve) => {
        const protocol = url.startsWith('https') ? https : http;
        
        protocol.get(url, (res) => {
            const responseTime = Date.now() - startTime;
            let data = '';
            
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                resolve({
                    success: res.statusCode === 200,
                    statusCode: res.statusCode,
                    responseTime,
                    wasSleeping: responseTime > 1000,
                    data: data.slice(0, 100)
                });
            });
        }).on('error', (err) => {
            resolve({
                success: false,
                error: err.message,
                responseTime: Date.now() - startTime
            });
        });
    });
}

// Ping all services
async function pingAllServices() {
    console.log(`\n${colors.blue}[${new Date().toISOString()}] Starting ping cycle...${colors.reset}`);
    
    for (const service of config.services) {
        console.log(`\n${colors.bright}Service: ${service.name}${colors.reset}`);
        
        for (const endpoint of service.endpoints) {
            const result = await pingEndpoint(service, endpoint);
            
            if (result.success) {
                const status = result.wasSleeping ? 
                    `${colors.yellow}WOKE UP${colors.reset}` : 
                    `${colors.green}ACTIVE${colors.reset}`;
                console.log(`  ${endpoint}: ${status} (${result.responseTime}ms)`);
            } else {
                console.log(`  ${endpoint}: ${colors.red}FAILED${colors.reset} - ${result.error || `Status ${result.statusCode}`}`);
            }
        }
    }
}

// Schedule pings
function schedulePings() {
    // Initial ping
    pingAllServices();
    
    // Schedule regular pings
    config.services.forEach(service => {
        setInterval(() => {
            service.endpoints.forEach(endpoint => {
                pingEndpoint(service, endpoint).then(result => {
                    const timestamp = new Date().toISOString();
                    if (result.wasSleeping) {
                        console.log(`${colors.yellow}[${timestamp}] Woke up ${service.name}${endpoint} (${result.responseTime}ms)${colors.reset}`);
                    }
                });
            });
        }, service.interval);
    });
}

// Create a simple web interface
function createWebInterface() {
    const server = http.createServer(async (req, res) => {
        if (req.url === '/') {
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(`
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Keep-Alive Service</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 40px; }
                        .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
                        .active { background-color: #d4edda; color: #155724; }
                        .sleeping { background-color: #fff3cd; color: #856404; }
                        .error { background-color: #f8d7da; color: #721c24; }
                    </style>
                </head>
                <body>
                    <h1>Keep-Alive Service Status</h1>
                    <div id="status"></div>
                    <script>
                        async function checkStatus() {
                            const response = await fetch('/status');
                            const data = await response.json();
                            document.getElementById('status').innerHTML = data.services.map(s => 
                                '<div class="status ' + s.status + '">' + 
                                '<h3>' + s.name + '</h3>' +
                                '<p>Status: ' + s.status + '</p>' +
                                '<p>Response Time: ' + s.responseTime + 'ms</p>' +
                                '<p>Last Check: ' + s.lastCheck + '</p>' +
                                '</div>'
                            ).join('');
                        }
                        checkStatus();
                        setInterval(checkStatus, 5000);
                    </script>
                </body>
                </html>
            `);
        } else if (req.url === '/status') {
            const statuses = await Promise.all(
                config.services.map(async service => {
                    const result = await pingEndpoint(service, '/health');
                    return {
                        name: service.name,
                        status: result.success ? (result.wasSleeping ? 'sleeping' : 'active') : 'error',
                        responseTime: result.responseTime,
                        lastCheck: new Date().toISOString()
                    };
                })
            );
            
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ services: statuses }));
        } else {
            res.writeHead(404);
            res.end('Not found');
        }
    });
    
    server.listen(config.port, () => {
        console.log(`\n${colors.green}Keep-Alive Service web interface running at http://localhost:${config.port}${colors.reset}`);
    });
}

// Main execution
console.log(`${colors.bright}${colors.blue}Keep-Alive Service for Render.com${colors.reset}`);
console.log('=====================================\n');

// Show configuration
console.log('Configuration:');
config.services.forEach(service => {
    console.log(`- ${service.name}: ${service.url}`);
    console.log(`  Endpoints: ${service.endpoints.join(', ')}`);
    console.log(`  Interval: ${service.interval / 1000}s`);
});

// Start services
schedulePings();
createWebInterface();

console.log(`\n${colors.green}Service started! Keeping your Render services awake 24/7.${colors.reset}`);
console.log(`${colors.yellow}Press Ctrl+C to stop.${colors.reset}\n`);

// Handle graceful shutdown
process.on('SIGINT', () => {
    console.log(`\n${colors.red}Shutting down keep-alive service...${colors.reset}`);
    process.exit(0);
});
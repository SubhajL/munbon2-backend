const express = require('express');
const HealthMonitor = require('./health-monitor');
const path = require('path');
const fs = require('fs').promises;

const app = express();
app.use(express.json());

// Initialize health monitor
const monitor = new HealthMonitor();

// Start monitoring
monitor.start();

// API Routes
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'health-monitor' });
});

app.get('/status', async (req, res) => {
  try {
    const status = await monitor.getStatus();
    
    // Determine overall health
    const allHealthy = status.services.tunnel.status === 'up' && 
                      status.services.api.status === 'up';
    
    res.status(allHealthy ? 200 : 503).json(status);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/logs', async (req, res) => {
  try {
    const logPath = monitor.config.logFile;
    const logs = await fs.readFile(logPath, 'utf8');
    const lines = logs.split('\n').filter(line => line.trim());
    
    // Get last N lines (default 100)
    const limit = parseInt(req.query.limit) || 100;
    const recentLogs = lines.slice(-limit);
    
    res.json({
      total: lines.length,
      returned: recentLogs.length,
      logs: recentLogs
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/check', async (req, res) => {
  try {
    // Trigger immediate health check
    const status = await monitor.getStatus();
    res.json(status);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/config', (req, res) => {
  // Return config with sensitive data masked
  const safeConfig = {
    ...monitor.config,
    email: monitor.config.email ? {
      ...monitor.config.email,
      smtp: {
        ...monitor.config.email.smtp,
        auth: { user: '***', pass: '***' }
      }
    } : undefined,
    webhook: monitor.config.webhook ? {
      ...monitor.config.webhook,
      url: monitor.config.webhook.url ? '***' : undefined
    } : undefined
  };
  
  res.json(safeConfig);
});

// Dashboard HTML
app.get('/', (req, res) => {
  res.send(`
<!DOCTYPE html>
<html>
<head>
    <title>Munbon Health Monitor</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .status-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .status-card h3 {
            margin-top: 0;
        }
        .status-up {
            color: #28a745;
            font-weight: bold;
        }
        .status-down {
            color: #dc3545;
            font-weight: bold;
        }
        .logs {
            background-color: #f4f4f4;
            padding: 10px;
            border-radius: 4px;
            max-height: 400px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 12px;
        }
        .log-entry {
            margin: 2px 0;
            padding: 2px;
        }
        .log-error {
            background-color: #ffe0e0;
        }
        .log-warn {
            background-color: #fff3cd;
        }
        .log-info {
            background-color: #d1ecf1;
        }
        button {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            margin: 5px;
        }
        button:hover {
            background-color: #0056b3;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Munbon Health Monitor Dashboard</h1>
        
        <div class="status-grid" id="statusGrid">
            <div class="status-card">
                <h3>Loading...</h3>
            </div>
        </div>
        
        <div>
            <button onclick="refreshStatus()">Refresh Status</button>
            <button onclick="triggerCheck()">Run Check Now</button>
            <button onclick="refreshLogs()">Refresh Logs</button>
        </div>
        
        <h2>Recent Logs</h2>
        <div class="logs" id="logsContainer">
            Loading logs...
        </div>
    </div>

    <script>
        async function refreshStatus() {
            try {
                const response = await fetch('/status');
                const data = await response.json();
                
                const statusGrid = document.getElementById('statusGrid');
                statusGrid.innerHTML = '';
                
                // Tunnel status
                const tunnelCard = createStatusCard('Cloudflare Tunnel', data.services.tunnel);
                statusGrid.appendChild(tunnelCard);
                
                // API status
                const apiCard = createStatusCard('Unified API', data.services.api);
                statusGrid.appendChild(apiCard);
                
                // Update timestamp
                const timestampCard = document.createElement('div');
                timestampCard.className = 'status-card';
                timestampCard.innerHTML = '<h3>Last Check</h3><p>' + new Date(data.timestamp).toLocaleString() + '</p>';
                statusGrid.appendChild(timestampCard);
            } catch (error) {
                console.error('Failed to fetch status:', error);
            }
        }
        
        function createStatusCard(title, service) {
            const card = document.createElement('div');
            card.className = 'status-card';
            
            const statusClass = service.status === 'up' ? 'status-up' : 'status-down';
            const statusText = service.status === 'up' ? '✓ UP' : '✗ DOWN';
            
            card.innerHTML = \`
                <h3>\${title}</h3>
                <p>Status: <span class="\${statusClass}">\${statusText}</span></p>
                <p>URL: \${service.url}</p>
                <p>Failure Count: \${service.failureCount}</p>
            \`;
            
            return card;
        }
        
        async function refreshLogs() {
            try {
                const response = await fetch('/logs?limit=50');
                const data = await response.json();
                
                const logsContainer = document.getElementById('logsContainer');
                logsContainer.innerHTML = '';
                
                data.logs.forEach(log => {
                    const entry = document.createElement('div');
                    entry.className = 'log-entry';
                    
                    if (log.includes('[ERROR]')) {
                        entry.className += ' log-error';
                    } else if (log.includes('[WARN]')) {
                        entry.className += ' log-warn';
                    } else if (log.includes('[INFO]')) {
                        entry.className += ' log-info';
                    }
                    
                    entry.textContent = log;
                    logsContainer.appendChild(entry);
                });
                
                // Scroll to bottom
                logsContainer.scrollTop = logsContainer.scrollHeight;
            } catch (error) {
                console.error('Failed to fetch logs:', error);
            }
        }
        
        async function triggerCheck() {
            try {
                const response = await fetch('/check', { method: 'POST' });
                const data = await response.json();
                console.log('Check triggered:', data);
                refreshStatus();
                refreshLogs();
            } catch (error) {
                console.error('Failed to trigger check:', error);
            }
        }
        
        // Initial load
        refreshStatus();
        refreshLogs();
        
        // Auto-refresh every 30 seconds
        setInterval(() => {
            refreshStatus();
            refreshLogs();
        }, 30000);
    </script>
</body>
</html>
  `);
});

const PORT = process.env.HEALTH_MONITOR_PORT || 3001;

app.listen(PORT, () => {
  console.log(`Health Monitor API running on port ${PORT}`);
  console.log(`Dashboard: http://localhost:${PORT}`);
  console.log(`Status API: http://localhost:${PORT}/status`);
});

// Handle shutdown
process.on('SIGINT', () => {
  console.log('\nShutting down health monitor...');
  monitor.stop();
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('\nShutting down health monitor...');
  monitor.stop();
  process.exit(0);
});
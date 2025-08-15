/**
 * Debug Dashboard - Central monitoring for all services
 * Access at http://localhost:9999
 */

const express = require('express');
const cors = require('cors');
const http = require('http');
const socketIo = require('socket.io');
const axios = require('axios');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 9999;
const SERVICES = process.env.SERVICES ? process.env.SERVICES.split(',').map(s => {
  const [name, port] = s.split(':');
  return { name, port, url: `http://${name}:${port}` };
}) : [];

// Service status tracking
const serviceStatus = {};
const requestLog = [];
const MAX_LOG_SIZE = 1000;

// Health check all services
async function checkServices() {
  for (const service of SERVICES) {
    try {
      const response = await axios.get(`${service.url}/health`, { timeout: 2000 });
      serviceStatus[service.name] = {
        status: 'healthy',
        lastCheck: new Date(),
        details: response.data,
        uptime: process.uptime()
      };
    } catch (error) {
      serviceStatus[service.name] = {
        status: 'unhealthy',
        lastCheck: new Date(),
        error: error.message,
        details: error.response?.data
      };
    }
  }
  io.emit('service-status', serviceStatus);
}

// Check services every 5 seconds
setInterval(checkServices, 5000);
checkServices();

// Dashboard HTML
app.get('/', (req, res) => {
  res.send(`
<!DOCTYPE html>
<html>
<head>
  <title>Debug Dashboard</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
      font-family: 'Monaco', 'Menlo', monospace; 
      background: #1e1e1e; 
      color: #d4d4d4;
      padding: 20px;
    }
    h1 { 
      color: #569cd6; 
      margin-bottom: 20px;
      font-size: 24px;
    }
    .container {
      max-width: 1400px;
      margin: 0 auto;
    }
    .services {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 15px;
      margin-bottom: 30px;
    }
    .service {
      background: #2d2d30;
      border: 1px solid #3e3e42;
      border-radius: 5px;
      padding: 15px;
    }
    .service.healthy {
      border-left: 4px solid #4ec9b0;
    }
    .service.unhealthy {
      border-left: 4px solid #f14c4c;
    }
    .service-name {
      font-weight: bold;
      font-size: 16px;
      margin-bottom: 10px;
    }
    .service-status {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }
    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }
    .status-dot.healthy {
      background: #4ec9b0;
      animation: pulse 2s infinite;
    }
    .status-dot.unhealthy {
      background: #f14c4c;
    }
    @keyframes pulse {
      0% { opacity: 1; }
      50% { opacity: 0.5; }
      100% { opacity: 1; }
    }
    .service-details {
      font-size: 12px;
      color: #808080;
    }
    .logs {
      background: #1e1e1e;
      border: 1px solid #3e3e42;
      border-radius: 5px;
      padding: 15px;
      height: 400px;
      overflow-y: auto;
    }
    .log-entry {
      margin-bottom: 10px;
      padding: 10px;
      background: #2d2d30;
      border-radius: 3px;
      font-size: 12px;
    }
    .log-entry.error {
      border-left: 3px solid #f14c4c;
    }
    .log-entry.success {
      border-left: 3px solid #4ec9b0;
    }
    .tabs {
      display: flex;
      gap: 10px;
      margin-bottom: 20px;
    }
    .tab {
      padding: 10px 20px;
      background: #2d2d30;
      border: 1px solid #3e3e42;
      border-radius: 5px;
      cursor: pointer;
      transition: all 0.3s;
    }
    .tab:hover {
      background: #3e3e42;
    }
    .tab.active {
      background: #569cd6;
      color: white;
    }
    .endpoint-tester {
      background: #2d2d30;
      border: 1px solid #3e3e42;
      border-radius: 5px;
      padding: 20px;
      margin-top: 20px;
    }
    input, select, button {
      padding: 8px;
      margin: 5px;
      background: #1e1e1e;
      border: 1px solid #3e3e42;
      color: #d4d4d4;
      border-radius: 3px;
    }
    button {
      background: #569cd6;
      color: white;
      cursor: pointer;
      padding: 8px 20px;
    }
    button:hover {
      background: #4a8cc7;
    }
    .response {
      margin-top: 15px;
      padding: 15px;
      background: #1e1e1e;
      border-radius: 5px;
      white-space: pre-wrap;
      font-size: 12px;
      max-height: 300px;
      overflow-y: auto;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 15px;
      margin-bottom: 20px;
    }
    .metric {
      background: #2d2d30;
      border: 1px solid #3e3e42;
      border-radius: 5px;
      padding: 15px;
      text-align: center;
    }
    .metric-value {
      font-size: 24px;
      font-weight: bold;
      color: #569cd6;
    }
    .metric-label {
      font-size: 12px;
      color: #808080;
      margin-top: 5px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🔧 Debug Dashboard</h1>
    
    <div class="metrics">
      <div class="metric">
        <div class="metric-value" id="total-services">0</div>
        <div class="metric-label">Total Services</div>
      </div>
      <div class="metric">
        <div class="metric-value" id="healthy-services">0</div>
        <div class="metric-label">Healthy</div>
      </div>
      <div class="metric">
        <div class="metric-value" id="request-count">0</div>
        <div class="metric-label">Requests</div>
      </div>
      <div class="metric">
        <div class="metric-value" id="error-count">0</div>
        <div class="metric-label">Errors</div>
      </div>
    </div>
    
    <div class="tabs">
      <div class="tab active" onclick="showTab('services')">Services</div>
      <div class="tab" onclick="showTab('tester')">API Tester</div>
      <div class="tab" onclick="showTab('logs')">Request Logs</div>
      <div class="tab" onclick="showTab('mock')">Mock Data</div>
    </div>
    
    <div id="services-tab">
      <h2 style="color: #4ec9b0; margin-bottom: 15px;">Service Health</h2>
      <div class="services" id="services"></div>
    </div>
    
    <div id="tester-tab" style="display: none;">
      <h2 style="color: #4ec9b0; margin-bottom: 15px;">API Endpoint Tester</h2>
      <div class="endpoint-tester">
        <select id="method">
          <option>GET</option>
          <option>POST</option>
          <option>PUT</option>
          <option>DELETE</option>
        </select>
        <select id="service">
          ${SERVICES.map(s => `<option value="${s.url}">${s.name}</option>`).join('')}
        </select>
        <input type="text" id="endpoint" placeholder="/api/endpoint" style="width: 300px;">
        <br>
        <textarea id="body" placeholder="Request body (JSON)" style="width: 100%; height: 100px; margin-top: 10px;"></textarea>
        <br>
        <input type="text" id="auth" placeholder="Authorization token (optional)" style="width: 100%; margin-top: 10px;">
        <br>
        <button onclick="testEndpoint()">Send Request</button>
        <div id="response" class="response"></div>
      </div>
    </div>
    
    <div id="logs-tab" style="display: none;">
      <h2 style="color: #4ec9b0; margin-bottom: 15px;">Request Logs</h2>
      <div class="logs" id="logs"></div>
    </div>
    
    <div id="mock-tab" style="display: none;">
      <h2 style="color: #4ec9b0; margin-bottom: 15px;">Mock Data Generator</h2>
      <div class="endpoint-tester">
        <select id="mock-type">
          <option value="sensor">Sensor Data</option>
          <option value="water-level">Water Level</option>
          <option value="moisture">Moisture</option>
          <option value="user">User</option>
          <option value="parcel">GIS Parcel</option>
        </select>
        <input type="number" id="mock-count" placeholder="Count" value="10" style="width: 100px;">
        <button onclick="generateMockData()">Generate</button>
        <div id="mock-response" class="response"></div>
      </div>
    </div>
  </div>
  
  <script src="/socket.io/socket.io.js"></script>
  <script>
    const socket = io();
    let requestCount = 0;
    let errorCount = 0;
    
    socket.on('service-status', (status) => {
      updateServices(status);
    });
    
    socket.on('request-log', (log) => {
      addLog(log);
      requestCount++;
      if (log.status >= 400) errorCount++;
      updateMetrics();
    });
    
    function updateServices(status) {
      const container = document.getElementById('services');
      container.innerHTML = '';
      
      let healthy = 0;
      let total = 0;
      
      for (const [name, data] of Object.entries(status)) {
        total++;
        if (data.status === 'healthy') healthy++;
        
        const serviceDiv = document.createElement('div');
        serviceDiv.className = 'service ' + data.status;
        serviceDiv.innerHTML = \`
          <div class="service-name">\${name}</div>
          <div class="service-status">
            <div class="status-dot \${data.status}"></div>
            <span>\${data.status.toUpperCase()}</span>
          </div>
          <div class="service-details">
            Last Check: \${new Date(data.lastCheck).toLocaleTimeString()}<br>
            \${data.error ? 'Error: ' + data.error : ''}
            \${data.details ? '<br>Details: ' + JSON.stringify(data.details) : ''}
          </div>
        \`;
        container.appendChild(serviceDiv);
      }
      
      document.getElementById('total-services').textContent = total;
      document.getElementById('healthy-services').textContent = healthy;
    }
    
    function updateMetrics() {
      document.getElementById('request-count').textContent = requestCount;
      document.getElementById('error-count').textContent = errorCount;
    }
    
    function addLog(log) {
      const logsDiv = document.getElementById('logs');
      const logEntry = document.createElement('div');
      logEntry.className = 'log-entry ' + (log.status >= 400 ? 'error' : 'success');
      logEntry.innerHTML = \`
        <strong>\${log.method} \${log.url}</strong> - Status: \${log.status}<br>
        Service: \${log.service} | Duration: \${log.duration}ms<br>
        \${log.error ? 'Error: ' + log.error : ''}
      \`;
      logsDiv.insertBefore(logEntry, logsDiv.firstChild);
      
      // Keep only last 50 logs
      while (logsDiv.children.length > 50) {
        logsDiv.removeChild(logsDiv.lastChild);
      }
    }
    
    function showTab(tab) {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      event.target.classList.add('active');
      
      document.getElementById('services-tab').style.display = tab === 'services' ? 'block' : 'none';
      document.getElementById('tester-tab').style.display = tab === 'tester' ? 'block' : 'none';
      document.getElementById('logs-tab').style.display = tab === 'logs' ? 'block' : 'none';
      document.getElementById('mock-tab').style.display = tab === 'mock' ? 'block' : 'none';
    }
    
    async function testEndpoint() {
      const method = document.getElementById('method').value;
      const service = document.getElementById('service').value;
      const endpoint = document.getElementById('endpoint').value;
      const body = document.getElementById('body').value;
      const auth = document.getElementById('auth').value;
      
      const responseDiv = document.getElementById('response');
      responseDiv.textContent = 'Sending request...';
      
      try {
        const options = {
          method: method,
          headers: {
            'Content-Type': 'application/json',
          }
        };
        
        if (auth) {
          options.headers['Authorization'] = auth.startsWith('Bearer ') ? auth : 'Bearer ' + auth;
        }
        
        if (body && method !== 'GET') {
          options.body = body;
        }
        
        const response = await fetch(service + endpoint, options);
        const data = await response.text();
        
        responseDiv.innerHTML = \`
          <strong>Status:</strong> \${response.status} \${response.statusText}<br>
          <strong>Headers:</strong><br>\${Array.from(response.headers.entries()).map(([k,v]) => k + ': ' + v).join('<br>')}<br>
          <strong>Body:</strong><br>\${data}
        \`;
      } catch (error) {
        responseDiv.innerHTML = '<strong style="color: #f14c4c;">Error:</strong> ' + error.message;
      }
    }
    
    async function generateMockData() {
      const type = document.getElementById('mock-type').value;
      const count = document.getElementById('mock-count').value;
      const responseDiv = document.getElementById('mock-response');
      
      const mockData = [];
      for (let i = 0; i < count; i++) {
        switch(type) {
          case 'sensor':
            mockData.push({
              sensorId: 'SENSOR-' + Math.random().toString(36).substr(2, 9),
              timestamp: new Date(),
              value: Math.random() * 100,
              type: ['temperature', 'humidity', 'pressure'][Math.floor(Math.random() * 3)]
            });
            break;
          case 'water-level':
            mockData.push({
              sensorId: 'WL-' + Math.random().toString(36).substr(2, 9),
              timestamp: new Date(),
              levelCm: Math.random() * 200,
              location: {
                lat: 13.7563 + Math.random() * 0.1,
                lng: 100.5018 + Math.random() * 0.1
              }
            });
            break;
          case 'moisture':
            mockData.push({
              sensorId: 'MS-' + Math.random().toString(36).substr(2, 9),
              timestamp: new Date(),
              moistureSurfacePct: Math.random() * 100,
              moistureDeepPct: Math.random() * 100,
              location: {
                lat: 13.7563 + Math.random() * 0.1,
                lng: 100.5018 + Math.random() * 0.1
              }
            });
            break;
          case 'user':
            mockData.push({
              id: 'USER-' + Math.random().toString(36).substr(2, 9),
              name: 'Test User ' + i,
              email: 'user' + i + '@test.com',
              role: ['admin', 'operator', 'viewer'][Math.floor(Math.random() * 3)]
            });
            break;
          case 'parcel':
            mockData.push({
              id: 'PARCEL-' + Math.random().toString(36).substr(2, 9),
              area: Math.random() * 1000,
              cropType: ['rice', 'corn', 'sugarcane'][Math.floor(Math.random() * 3)],
              geometry: {
                type: 'Polygon',
                coordinates: [[
                  [100.5018, 13.7563],
                  [100.5028, 13.7563],
                  [100.5028, 13.7573],
                  [100.5018, 13.7573],
                  [100.5018, 13.7563]
                ]]
              }
            });
            break;
        }
      }
      
      responseDiv.textContent = JSON.stringify(mockData, null, 2);
    }
  </script>
</body>
</html>
  `);
});

// API endpoints
app.get('/debug/health', (req, res) => {
  res.json({
    status: 'healthy',
    services: serviceStatus,
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    requestCount,
    errorCount
  });
});

app.post('/debug/log', (req, res) => {
  const log = req.body;
  requestLog.push(log);
  if (requestLog.length > MAX_LOG_SIZE) {
    requestLog.shift();
  }
  io.emit('request-log', log);
  res.json({ success: true });
});

server.listen(PORT, () => {
  console.log(`🚀 Debug Dashboard running at http://localhost:${PORT}`);
  console.log(`📊 Monitoring services:`, SERVICES.map(s => s.name).join(', '));
});
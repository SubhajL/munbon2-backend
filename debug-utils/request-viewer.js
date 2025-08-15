/**
 * Request Viewer - Real-time request/response log viewer
 * Access at http://localhost:9998
 */

const express = require('express');
const cors = require('cors');
const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 9998;
const LOG_DIR = process.env.LOG_DIR || './logs';

// Ensure log directory exists
if (!fs.existsSync(LOG_DIR)) {
  fs.mkdirSync(LOG_DIR, { recursive: true });
}

// WebSocket server for real-time updates
const wss = new WebSocket.Server({ port: 9997 });

// Broadcast to all connected clients
function broadcast(data) {
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify(data));
    }
  });
}

// Log storage
const logs = {
  requests: [],
  errors: [],
  sql: [],
  performance: []
};

// Main page
app.get('/', (req, res) => {
  res.send(`
<!DOCTYPE html>
<html>
<head>
  <title>Request Viewer</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
      font-family: 'Monaco', 'Menlo', monospace; 
      background: #000; 
      color: #0f0;
      padding: 10px;
      font-size: 12px;
    }
    .container {
      max-width: 100%;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }
    .header {
      background: #111;
      padding: 10px;
      border: 1px solid #0f0;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .title {
      font-size: 16px;
      color: #0f0;
      text-shadow: 0 0 10px #0f0;
    }
    .controls {
      display: flex;
      gap: 10px;
    }
    button {
      background: #000;
      color: #0f0;
      border: 1px solid #0f0;
      padding: 5px 10px;
      cursor: pointer;
      font-family: inherit;
    }
    button:hover {
      background: #0f0;
      color: #000;
    }
    .filters {
      display: flex;
      gap: 10px;
      margin-bottom: 10px;
    }
    input, select {
      background: #000;
      color: #0f0;
      border: 1px solid #0f0;
      padding: 5px;
      font-family: inherit;
    }
    .logs {
      flex: 1;
      overflow-y: auto;
      background: #000;
      border: 1px solid #0f0;
      padding: 10px;
    }
    .log-entry {
      margin-bottom: 10px;
      padding: 5px;
      border-left: 2px solid #0f0;
      padding-left: 10px;
    }
    .log-entry.error {
      border-left-color: #f00;
      color: #f00;
    }
    .log-entry.success {
      border-left-color: #0f0;
    }
    .log-entry.sql {
      border-left-color: #ff0;
      color: #ff0;
    }
    .log-entry.performance {
      border-left-color: #0ff;
      color: #0ff;
    }
    .timestamp {
      color: #666;
      font-size: 10px;
    }
    .method {
      font-weight: bold;
      display: inline-block;
      width: 60px;
    }
    .url {
      color: #0ff;
    }
    .status {
      display: inline-block;
      width: 40px;
      text-align: right;
    }
    .status.success { color: #0f0; }
    .status.error { color: #f00; }
    .duration {
      color: #ff0;
      float: right;
    }
    .body {
      margin-top: 5px;
      padding: 5px;
      background: #111;
      white-space: pre-wrap;
      font-size: 11px;
      max-height: 200px;
      overflow-y: auto;
    }
    .stats {
      position: fixed;
      top: 10px;
      right: 10px;
      background: #111;
      border: 1px solid #0f0;
      padding: 10px;
      font-size: 10px;
    }
    .stat {
      margin-bottom: 5px;
    }
    .stat-label {
      color: #666;
      display: inline-block;
      width: 100px;
    }
    .stat-value {
      color: #0f0;
      font-weight: bold;
    }
    @keyframes blink {
      0%, 50% { opacity: 1; }
      51%, 100% { opacity: 0; }
    }
    .live-indicator {
      display: inline-block;
      width: 8px;
      height: 8px;
      background: #0f0;
      border-radius: 50%;
      animation: blink 1s infinite;
      margin-left: 10px;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="title">
        REQUEST VIEWER 
        <span class="live-indicator"></span>
        <span style="font-size: 10px; color: #666; margin-left: 5px;">LIVE</span>
      </div>
      <div class="controls">
        <button onclick="clearLogs()">CLEAR</button>
        <button onclick="pauseLogs()">PAUSE</button>
        <button onclick="exportLogs()">EXPORT</button>
      </div>
    </div>
    
    <div class="filters">
      <input type="text" id="filter" placeholder="Filter..." onkeyup="filterLogs()">
      <select id="type-filter" onchange="filterLogs()">
        <option value="all">ALL</option>
        <option value="requests">REQUESTS</option>
        <option value="errors">ERRORS</option>
        <option value="sql">SQL</option>
        <option value="performance">PERFORMANCE</option>
      </select>
      <select id="service-filter" onchange="filterLogs()">
        <option value="all">ALL SERVICES</option>
        <option value="auth">AUTH</option>
        <option value="sensor-data">SENSOR-DATA</option>
        <option value="gis">GIS</option>
        <option value="ros">ROS</option>
      </select>
    </div>
    
    <div class="logs" id="logs"></div>
    
    <div class="stats">
      <div class="stat">
        <span class="stat-label">TOTAL REQUESTS:</span>
        <span class="stat-value" id="total-requests">0</span>
      </div>
      <div class="stat">
        <span class="stat-label">ERRORS:</span>
        <span class="stat-value" id="total-errors" style="color: #f00;">0</span>
      </div>
      <div class="stat">
        <span class="stat-label">AVG RESPONSE:</span>
        <span class="stat-value" id="avg-response">0ms</span>
      </div>
      <div class="stat">
        <span class="stat-label">ACTIVE CONNS:</span>
        <span class="stat-value" id="active-conns">0</span>
      </div>
    </div>
  </div>
  
  <script>
    const ws = new WebSocket('ws://localhost:9997');
    let logs = [];
    let paused = false;
    let stats = {
      total: 0,
      errors: 0,
      totalDuration: 0,
      connections: 0
    };
    
    ws.onopen = () => {
      console.log('Connected to log stream');
      stats.connections = 1;
      updateStats();
    };
    
    ws.onmessage = (event) => {
      if (paused) return;
      
      const log = JSON.parse(event.data);
      logs.unshift(log);
      if (logs.length > 500) logs.pop();
      
      addLogEntry(log);
      updateStats(log);
    };
    
    function addLogEntry(log) {
      const logsDiv = document.getElementById('logs');
      const entry = document.createElement('div');
      entry.className = 'log-entry ' + getLogClass(log);
      entry.dataset.service = log.service;
      entry.dataset.type = log.type;
      
      let content = '';
      const timestamp = new Date(log.timestamp).toLocaleTimeString();
      
      if (log.type === 'request') {
        const statusClass = log.status >= 400 ? 'error' : 'success';
        content = \`
          <span class="timestamp">\${timestamp}</span>
          <span class="method">\${log.method}</span>
          <span class="url">\${log.url}</span>
          <span class="status \${statusClass}">\${log.status}</span>
          <span class="duration">\${log.duration}ms</span>
          \${log.body ? '<div class="body">' + JSON.stringify(log.body, null, 2) + '</div>' : ''}
        \`;
      } else if (log.type === 'sql') {
        content = \`
          <span class="timestamp">\${timestamp}</span>
          SQL: \${log.query}
          <span class="duration">\${log.duration}ms</span>
        \`;
      } else if (log.type === 'error') {
        content = \`
          <span class="timestamp">\${timestamp}</span>
          ERROR: \${log.message}
          <div class="body">\${log.stack}</div>
        \`;
      } else {
        content = \`
          <span class="timestamp">\${timestamp}</span>
          \${log.message}
        \`;
      }
      
      entry.innerHTML = content;
      logsDiv.insertBefore(entry, logsDiv.firstChild);
      
      while (logsDiv.children.length > 100) {
        logsDiv.removeChild(logsDiv.lastChild);
      }
    }
    
    function getLogClass(log) {
      if (log.type === 'error' || log.status >= 400) return 'error';
      if (log.type === 'sql') return 'sql';
      if (log.type === 'performance') return 'performance';
      return 'success';
    }
    
    function updateStats(log) {
      if (log) {
        stats.total++;
        if (log.status >= 400 || log.type === 'error') stats.errors++;
        if (log.duration) stats.totalDuration += log.duration;
      }
      
      document.getElementById('total-requests').textContent = stats.total;
      document.getElementById('total-errors').textContent = stats.errors;
      document.getElementById('avg-response').textContent = 
        stats.total > 0 ? Math.round(stats.totalDuration / stats.total) + 'ms' : '0ms';
      document.getElementById('active-conns').textContent = stats.connections;
    }
    
    function clearLogs() {
      logs = [];
      document.getElementById('logs').innerHTML = '';
      stats = { total: 0, errors: 0, totalDuration: 0, connections: stats.connections };
      updateStats();
    }
    
    function pauseLogs() {
      paused = !paused;
      event.target.textContent = paused ? 'RESUME' : 'PAUSE';
    }
    
    function exportLogs() {
      const blob = new Blob([JSON.stringify(logs, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'logs-' + new Date().getTime() + '.json';
      a.click();
    }
    
    function filterLogs() {
      const filter = document.getElementById('filter').value.toLowerCase();
      const typeFilter = document.getElementById('type-filter').value;
      const serviceFilter = document.getElementById('service-filter').value;
      
      const entries = document.querySelectorAll('.log-entry');
      entries.forEach(entry => {
        const text = entry.textContent.toLowerCase();
        const type = entry.dataset.type;
        const service = entry.dataset.service;
        
        let show = true;
        if (filter && !text.includes(filter)) show = false;
        if (typeFilter !== 'all' && type !== typeFilter) show = false;
        if (serviceFilter !== 'all' && service !== serviceFilter) show = false;
        
        entry.style.display = show ? 'block' : 'none';
      });
    }
  </script>
</body>
</html>
  `);
});

// API endpoint to receive logs
app.post('/log', (req, res) => {
  const log = {
    ...req.body,
    timestamp: new Date(),
    service: req.headers['x-service-name'] || 'unknown'
  };
  
  // Store log
  if (log.type === 'error' || log.status >= 400) {
    logs.errors.push(log);
  } else if (log.type === 'sql') {
    logs.sql.push(log);
  } else {
    logs.requests.push(log);
  }
  
  // Broadcast to connected clients
  broadcast(log);
  
  // Write to file
  const filename = `${LOG_DIR}/${log.service}-${new Date().toISOString().split('T')[0]}.log`;
  fs.appendFileSync(filename, JSON.stringify(log) + '\\n');
  
  res.json({ success: true });
});

app.listen(PORT, () => {
  console.log(`📡 Request Viewer running at http://localhost:${PORT}`);
  console.log(`🔌 WebSocket server on port 9997`);
});
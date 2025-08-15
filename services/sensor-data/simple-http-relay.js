#!/usr/bin/env node

const express = require('express');
const app = express();
app.use(express.json());

// Simple relay that just logs and responds 200 OK
app.post('/api/v1/:token/telemetry', (req, res) => {
  console.log('=== MOISTURE SENSOR DATA RECEIVED ===');
  console.log('Time:', new Date().toISOString());
  console.log('Token:', req.params.token);
  console.log('Headers:', req.headers);
  console.log('Body:', JSON.stringify(req.body, null, 2));
  console.log('=====================================\n');
  
  // Always return success to test if manufacturer can connect
  res.json({
    status: 'success',
    message: 'Telemetry received',
    timestamp: new Date().toISOString()
  });
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'simple-http-relay' });
});

const PORT = 3003;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Simple HTTP relay running on port ${PORT}`);
  console.log(`Accepting requests at http://localhost:${PORT}/api/v1/{token}/telemetry`);
});
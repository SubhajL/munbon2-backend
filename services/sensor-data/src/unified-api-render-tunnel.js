// Unified API for Render.com with tunnel to local databases
const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(cors());

// Internal API key for Lambda authentication
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'munbon-internal-f3b89263126548';
console.log('Starting Unified API on Render...');
console.log('Internal API Key:', INTERNAL_API_KEY);

// IMPORTANT: These will connect through your tunnel to local databases
// You need to set up ngrok or cloudflared tunnel and update these URLs
const timescaleDB = new Pool({
  host: process.env.TIMESCALE_HOST || 'your-tunnel-url.ngrok-free.app', // Update with your tunnel URL
  port: process.env.TIMESCALE_PORT || 5433,
  database: process.env.TIMESCALE_DB || 'sensor_data',
  user: process.env.TIMESCALE_USER || 'postgres',
  password: process.env.TIMESCALE_PASSWORD || 'postgres',
  ssl: false // Tunnel handles security
});

// MSSQL connection (SCADA data) - This seems to be already accessible
const mssqlConfig = {
  server: process.env.MSSQL_HOST || 'moonup.hopto.org',
  database: process.env.MSSQL_DB || 'db_scada',
  user: process.env.MSSQL_USER || 'sa',
  password: process.env.MSSQL_PASSWORD || 'bangkok1234',
  options: {
    encrypt: false,
    trustServerCertificate: true,
    port: parseInt(process.env.MSSQL_PORT || '1433')
  }
};

// Middleware for internal API key validation
app.use((req, res, next) => {
  // Skip auth for health check
  if (req.path === '/health') return next();
  
  const apiKey = req.headers['x-internal-key'];
  if (apiKey !== INTERNAL_API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    service: 'unified-api-render',
    environment: 'render',
    timestamp: new Date().toISOString()
  });
});

// Database connection status endpoint
app.get('/status', async (req, res) => {
  const apiKey = req.headers['x-internal-key'];
  if (apiKey !== INTERNAL_API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  
  let timescaleStatus = 'disconnected';
  let mssqlStatus = 'disconnected';
  
  try {
    await timescaleDB.query('SELECT 1');
    timescaleStatus = 'connected';
  } catch (err) {
    console.error('TimescaleDB connection error:', err.message);
  }
  
  try {
    const pool = await sql.connect(mssqlConfig);
    await pool.request().query('SELECT 1');
    mssqlStatus = 'connected';
    pool.close();
  } catch (err) {
    console.error('MSSQL connection error:', err.message);
  }
  
  res.json({
    service: 'unified-api',
    databases: {
      timescale: timescaleStatus,
      mssql: mssqlStatus
    },
    tunnelUrl: process.env.TIMESCALE_HOST,
    timestamp: new Date().toISOString()
  });
});

// Copy all the API endpoints from unified-api-v2.js below this line...
// (Buddhist calendar conversion, water level endpoints, moisture endpoints, etc.)
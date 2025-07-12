// Vercel Serverless Function
// Place in: api/unified.js

const { Pool } = require('pg');
const sql = require('mssql');

// Database connections
const timescaleDB = new Pool({
  host: process.env.TIMESCALE_HOST,
  port: process.env.TIMESCALE_PORT,
  database: process.env.TIMESCALE_DB,
  user: process.env.TIMESCALE_USER,
  password: process.env.TIMESCALE_PASSWORD
});

const mssqlConfig = {
  server: process.env.MSSQL_HOST,
  database: process.env.MSSQL_DB,
  user: process.env.MSSQL_USER,
  password: process.env.MSSQL_PASSWORD,
  options: {
    encrypt: false,
    trustServerCertificate: true,
    port: parseInt(process.env.MSSQL_PORT)
  }
};

module.exports = async (req, res) => {
  // Enable CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'X-Internal-Key');

  // Check API key
  const apiKey = req.headers['x-internal-key'];
  if (apiKey !== process.env.INTERNAL_API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  // Route handling
  const { pathname } = new URL(req.url, `http://${req.headers.host}`);
  
  if (pathname === '/health') {
    return res.json({ status: 'ok', service: 'unified-api-vercel' });
  }

  // Add your other routes here...
  
  res.status(404).json({ error: 'Not found' });
};
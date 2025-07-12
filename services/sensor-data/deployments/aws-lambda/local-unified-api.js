// Unified API that Lambda will call
// This runs locally and has access to both TimescaleDB and MSSQL

const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');

const app = express();

// TimescaleDB connection
const timescaleDB = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'sensor_data',
  user: 'postgres',
  password: 'postgres'
});

// MSSQL connection (for SCADA data)
const mssqlConfig = {
  server: 'localhost',
  database: 'SCADA_DB',
  user: 'sa',
  password: 'your_password',
  options: {
    encrypt: false,
    trustServerCertificate: true
  }
};

// Middleware for internal API key
app.use((req, res, next) => {
  const apiKey = req.headers['x-internal-key'];
  if (apiKey !== process.env.INTERNAL_API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
});

// Endpoint that combines data from both databases
app.get('/api/v1/sensors/combined/latest', async (req, res) => {
  try {
    // Get sensor data from TimescaleDB
    const sensorData = await timescaleDB.query(`
      SELECT sensor_id, data, timestamp 
      FROM sensor_readings 
      WHERE timestamp > NOW() - INTERVAL '1 hour'
      ORDER BY timestamp DESC
    `);

    // Get SCADA data from MSSQL
    await sql.connect(mssqlConfig);
    const scadaData = await sql.query`
      SELECT TagName, Value, Timestamp 
      FROM ScadaData 
      WHERE Timestamp > DATEADD(hour, -1, GETDATE())
    `;

    // Combine and return
    res.json({
      sensors: sensorData.rows,
      scada: scadaData.recordset,
      timestamp: new Date()
    });
  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

app.listen(3000, () => {
  console.log('Unified API running on port 3000');
});

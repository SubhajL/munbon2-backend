#!/usr/bin/env node

const { Pool } = require('pg');
const sql = require('mssql');
require('dotenv').config();

// Configuration
const config = require('../src/config');

console.log('Database Setup Verification');
console.log('===========================\n');

// Test TimescaleDB Connection
async function testTimescaleDB() {
  console.log('1. Testing TimescaleDB Connection...');

  const pool = new Pool({
    host: config.timescale.host,
    port: config.timescale.port,
    database: config.timescale.database,
    user: config.timescale.user,
    password: config.timescale.password,
  });

  try {
    const client = await pool.connect();
    console.log('✅ TimescaleDB connected successfully');

    // Check if TimescaleDB extension is installed
    const extResult = await client.query(
      "SELECT * FROM pg_extension WHERE extname = 'timescaledb'"
    );

    if (extResult.rows.length > 0) {
      console.log('✅ TimescaleDB extension is installed');
    } else {
      console.log('⚠️  TimescaleDB extension not found. You may need to run: CREATE EXTENSION IF NOT EXISTS timescaledb;');
    }

    // Check schemas
    console.log('\nChecking schemas:');
    for (const [name, schema] of Object.entries(config.timescale.schemas)) {
      const schemaResult = await client.query(
        'SELECT schema_name FROM information_schema.schemata WHERE schema_name = $1',
        [schema]
      );

      if (schemaResult.rows.length > 0) {
        console.log(`  ✓ Schema "${schema}" exists`);

        // List tables in schema
        const tableResult = await client.query(
          `SELECT table_name FROM information_schema.tables
           WHERE table_schema = $1 AND table_type = 'BASE TABLE'`,
          [schema]
        );

        if (tableResult.rows.length > 0) {
          console.log(`    Tables: ${tableResult.rows.map(r => r.table_name).join(', ')}`);
        } else {
          console.log(`    No tables found in schema`);
        }
      } else {
        console.log(`  ✗ Schema "${schema}" does not exist`);
      }
    }

    client.release();
  } catch (error) {
    console.error('❌ TimescaleDB connection failed:', error.message);
    console.error('   Check your TIMESCALE_* environment variables');
  } finally {
    await pool.end();
  }
}

// Test MSSQL Connection
async function testMSSQL() {
  console.log('\n2. Testing MSSQL Connection...');

  const mssqlConfig = {
    server: config.mssql.host,
    port: config.mssql.port,
    database: config.mssql.database,
    user: config.mssql.user,
    password: config.mssql.password,
    options: {
      encrypt: false,
      trustServerCertificate: true,
    },
  };

  try {
    await sql.connect(mssqlConfig);
    console.log('✅ MSSQL connected successfully');

    // Check if valve command table exists
    const result = await sql.query`
      SELECT * FROM INFORMATION_SCHEMA.TABLES
      WHERE TABLE_NAME = ${config.mssql.tableName}
    `;

    if (result.recordset.length > 0) {
      console.log(`✅ Table "${config.mssql.tableName}" exists`);

      // Check table structure
      const columns = await sql.query`
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ${config.mssql.tableName}
      `;

      console.log('   Columns:', columns.recordset.map(c =>
        `${c.COLUMN_NAME} (${c.DATA_TYPE})`
      ).join(', '));
    } else {
      console.log(`⚠️  Table "${config.mssql.tableName}" not found`);
      console.log('   You may need to create it with:');
      console.log(`   CREATE TABLE ${config.mssql.tableName} (`);
      console.log('     valve_name VARCHAR(50),');
      console.log('     valve_level INT,');
      console.log('     startdatetime DATETIME');
      console.log('   )');
    }

    await sql.close();
  } catch (error) {
    console.error('❌ MSSQL connection failed:', error.message);
    console.error('   Check your MSSQL_* environment variables');
  }
}

// Test External Services
async function testExternalServices() {
  console.log('\n3. Testing External Service Connections...');

  const axios = require('axios');

  // Test Sensor Data Service
  if (config.sensorData.serviceUrl) {
    try {
      const response = await axios.get(
        `${config.sensorData.serviceUrl}/health`,
        { timeout: 5000 }
      );
      console.log('✅ Sensor Data Service is reachable');
    } catch (error) {
      console.log('⚠️  Sensor Data Service not reachable at', config.sensorData.serviceUrl);
      console.log('   Make sure the external-api service is running');
    }
  }

  // Test Water Planning Service
  if (config.waterPlanning && config.waterPlanning.serviceUrl) {
    try {
      await axios.get(
        `${config.waterPlanning.serviceUrl}/health`,
        { timeout: 5000 }
      );
      console.log('✅ Water Planning Service is reachable');
    } catch (error) {
      console.log('⚠️  Water Planning Service not reachable at', config.waterPlanning.serviceUrl);
      console.log('   Ensure the planning API is running');
    }
  }
}

// Summary
function printSummary() {
  console.log('\n4. Configuration Summary');
  console.log('========================');
  console.log('\nEnvironment Variables Required:');

  const requiredEnvVars = [
    'TIMESCALE_HOST',
    'TIMESCALE_PASSWORD',
    'MSSQL_HOST',
    'MSSQL_USER',
    'MSSQL_PASSWORD',
'WATER_PLANNING_API_KEY',
    'SENSOR_DATA_API_KEY'
  ];

  requiredEnvVars.forEach(envVar => {
    const value = process.env[envVar];
    if (value) {
      console.log(`  ✓ ${envVar}: ${envVar.includes('PASSWORD') || envVar.includes('KEY') ? '***' : value}`);
    } else {
      console.log(`  ✗ ${envVar}: NOT SET`);
    }
  });

  console.log('\nNext Steps:');
  console.log('1. Set any missing environment variables in your .env file');
  console.log('2. Ensure all dependent services are running:');
  console.log('   - External API service (port 3015)');
  console.log('   - ROS service (port 3001)');
  console.log('3. Run database initialization if schemas are missing:');
  console.log('   npm run db:init');
  console.log('4. Start the Smart Farm service:');
  console.log('   npm start');
}

// Run all tests
async function main() {
  await testTimescaleDB();
  await testMSSQL();
  await testExternalServices();
  printSummary();
}

main().catch(console.error);
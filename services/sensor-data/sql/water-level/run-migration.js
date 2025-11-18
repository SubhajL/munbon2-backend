#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { Client } = require('pg');
require('dotenv').config({ path: path.join(__dirname, '../../.env') });

// Database configuration from environment variables
const config = {
  host: process.env.TIMESCALE_HOST || '43.208.201.191',
  port: process.env.TIMESCALE_PORT || 5432,
  database: process.env.TIMESCALE_DB || 'sensor_data',
  user: process.env.TIMESCALE_USER || 'postgres',
  password: process.env.TIMESCALE_PASSWORD || '__ROTATED_DB_PASSWORD__',
  ssl: false
};

async function runMigration(sqlFile) {
  const client = new Client(config);

  try {
    await client.connect();
    console.log('✅ Connected to database');

    const sqlPath = path.join(__dirname, sqlFile);
    const sql = fs.readFileSync(sqlPath, 'utf8');

    console.log(`Running: ${sqlFile}\n`);

    // Check if this is a SELECT query or profile script
    if (sql.toLowerCase().includes('select') && !sql.toLowerCase().includes('create')) {
      // Split SQL by semicolons to handle multiple queries
      const queries = sql.split(/;\s*(?=WITH|SELECT|--)/);

      for (const query of queries) {
        if (query.trim()) {
          const result = await client.query(query);

          if (result.rows.length > 0) {
            // Format output as table
            console.table(result.rows);
            console.log(`\n(${result.rows.length} rows)\n`);
          }
        }
      }
      console.log('✅ Profile completed');
    } else {
      // Execute DDL/DML statement
      await client.query(sql);
      console.log(`✅ Successfully executed ${sqlFile}`);

      // Verify table creation
      if (sqlFile.includes('create_smoothed_table')) {
        const result = await client.query(`
          SELECT column_name, data_type
          FROM information_schema.columns
          WHERE table_name = 'smoothed_water_level_readings'
          ORDER BY ordinal_position;
        `);
        console.log('\nTable structure:');
        result.rows.forEach(row => {
          console.log(`  ${row.column_name}: ${row.data_type}`);
        });
      }
    }

  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  } finally {
    await client.end();
  }
}

// Get SQL file from command line argument
const sqlFile = process.argv[2];
if (!sqlFile) {
  console.error('Usage: node run-migration.js <sql-file>');
  process.exit(1);
}

runMigration(sqlFile).catch(console.error);
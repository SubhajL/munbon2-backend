import { Client } from 'pg';
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load EC2 specific env vars
dotenv.config({ path: path.join(__dirname, '..', '.env.ec2') });

async function checkEC2Hypertables() {
  const client = new Client({
    host: process.env.EC2_DB_HOST || process.env.EC2_HOST || '43.208.201.191',
    port: parseInt(process.env.EC2_DB_PORT || '5432'),
    database: process.env.EC2_DB_NAME || 'sensor_data',
    user: process.env.EC2_DB_USER || 'postgres',
    password: process.env.EC2_DB_PASSWORD || 'postgres'
  });

  try {
    await client.connect();
    console.log('🔗 Connected to EC2 database');

    // Check if TimescaleDB is installed
    const extensionResult = await client.query(`
      SELECT * FROM pg_extension WHERE extname = 'timescaledb';
    `);
    console.log('\n📦 TimescaleDB Extension:', extensionResult.rows.length > 0 ? 'Installed' : 'Not installed');

    // Check hypertables
    console.log('\n📊 Checking hypertables...');
    try {
      const hypertables = await client.query(`
        SELECT 
          h.schema_name,
          h.table_name,
          h.num_dimensions,
          h.num_chunks,
          h.compression_enabled,
          h.is_distributed,
          h.tablespace
        FROM timescaledb_information.hypertables h
        WHERE h.schema_name = 'public';
      `);
      
      if (hypertables.rows.length > 0) {
        console.log('\nHypertables found:');
        hypertables.rows.forEach(ht => {
          console.log(`  - ${ht.schema_name}.${ht.table_name}: ${ht.num_chunks} chunks, compression: ${ht.compression_enabled}`);
        });
      } else {
        console.log('No hypertables found');
      }
    } catch (err) {
      // Try alternative query for older TimescaleDB versions
      try {
        const hypertables = await client.query(`
          SELECT * FROM _timescaledb_catalog.hypertable 
          WHERE schema_name = 'public';
        `);
        console.log('\nHypertables (from catalog):', hypertables.rows.length);
      } catch (err2) {
        console.log('Could not query hypertable catalog');
      }
    }

    // Check regular tables
    console.log('\n📋 Regular tables:');
    const tables = await client.query(`
      SELECT tablename, hasindexes, hasrules, hastriggers 
      FROM pg_tables 
      WHERE schemaname = 'public' 
      AND tablename IN ('sensor_readings', 'water_level_readings', 'moisture_readings', 'sensor_registry')
      ORDER BY tablename;
    `);
    
    tables.rows.forEach(table => {
      console.log(`  - ${table.tablename}: triggers=${table.hastriggers}`);
    });

    // Check for blocking triggers
    console.log('\n🚫 Checking for blocking triggers...');
    const triggers = await client.query(`
      SELECT 
        t.tgname as trigger_name,
        c.relname as table_name,
        p.proname as function_name
      FROM pg_trigger t
      JOIN pg_class c ON t.tgrelid = c.oid
      JOIN pg_proc p ON t.tgfoid = p.oid
      WHERE c.relnamespace = 'public'::regnamespace
      AND c.relname IN ('sensor_readings', 'water_level_readings', 'moisture_readings')
      AND t.tgname LIKE '%blocker%';
    `);

    if (triggers.rows.length > 0) {
      console.log('\n⚠️  Insert blocker triggers found:');
      triggers.rows.forEach(trigger => {
        console.log(`  - ${trigger.table_name}: ${trigger.trigger_name} -> ${trigger.function_name}`);
      });
    } else {
      console.log('No insert blocker triggers found');
    }

  } catch (error) {
    console.error('❌ Error:', error);
  } finally {
    await client.end();
  }
}

// Run the check
checkEC2Hypertables().catch(console.error);
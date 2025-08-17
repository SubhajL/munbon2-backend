import { Client } from 'pg';
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load EC2 specific env vars
dotenv.config({ path: path.join(__dirname, '..', '.env.ec2') });

async function setupHypertables() {
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

    // Enable TimescaleDB extension
    console.log('📦 Enabling TimescaleDB extension...');
    await client.query('CREATE EXTENSION IF NOT EXISTS timescaledb;');

    // Convert tables to hypertables
    const tables = [
      { name: 'water_level_readings', interval: '1 day' },
      { name: 'moisture_readings', interval: '1 day' },
      { name: 'sensor_location_history', interval: '7 days' }
    ];

    for (const table of tables) {
      try {
        console.log(`\n🔄 Converting ${table.name} to hypertable...`);
        
        // Check if table exists
        const tableExists = await client.query(`
          SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = $1
          );
        `, [table.name]);

        if (!tableExists.rows[0].exists) {
          console.log(`⚠️  Table ${table.name} does not exist, skipping...`);
          continue;
        }

        // Check if already a hypertable
        const isHypertable = await client.query(`
          SELECT EXISTS (
            SELECT 1 FROM _timescaledb_catalog.hypertable h
            JOIN pg_class c ON h.table_name = c.relname
            WHERE h.schema_name = 'public' AND h.table_name = $1
          );
        `, [table.name]);

        if (isHypertable.rows[0].exists) {
          console.log(`✅ ${table.name} is already a hypertable`);
        } else {
          await client.query(`
            SELECT create_hypertable('${table.name}', 'time', 
              if_not_exists => TRUE,
              chunk_time_interval => INTERVAL '${table.interval}',
              migrate_data => TRUE
            );
          `);
          console.log(`✅ ${table.name} converted to hypertable with ${table.interval} chunks`);
        }

        // Verify hypertable configuration
        const hypertableInfo = await client.query(`
          SELECT 
            h.table_name,
            d.column_name,
            d.interval_length::text as chunk_interval
          FROM _timescaledb_catalog.hypertable h
          JOIN _timescaledb_catalog.dimension d ON h.id = d.hypertable_id
          WHERE h.schema_name = 'public' AND h.table_name = $1;
        `, [table.name]);

        if (hypertableInfo.rows.length > 0) {
          const info = hypertableInfo.rows[0];
          console.log(`   ℹ️  Hypertable info: time column='${info.column_name}', chunk interval='${info.chunk_interval}'`);
        }

      } catch (error) {
        console.error(`❌ Error processing ${table.name}:`, error);
      }
    }

    // Create missing indexes if needed
    console.log('\n📊 Creating indexes...');
    const indexes = [
      'CREATE INDEX IF NOT EXISTS idx_water_level_sensor_time ON water_level_readings (sensor_id, time DESC);',
      'CREATE INDEX IF NOT EXISTS idx_moisture_sensor_time ON moisture_readings (sensor_id, time DESC);'
    ];

    for (const indexSql of indexes) {
      try {
        await client.query(indexSql);
        console.log(`✅ Index created/verified`);
      } catch (error) {
        console.error(`⚠️  Index creation warning:`, error);
      }
    }

    console.log('\n✅ EC2 database hypertable setup completed!');

  } catch (error) {
    console.error('❌ Error setting up hypertables:', error);
    process.exit(1);
  } finally {
    await client.end();
  }
}

// Run the setup
setupHypertables().catch(console.error);
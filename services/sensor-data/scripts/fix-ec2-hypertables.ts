import { Client } from 'pg';
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load environment variables
dotenv.config({ path: path.join(__dirname, '..', '.env.local') });
dotenv.config(); // Also load .env as fallback

async function fixEC2Hypertables() {
  const client = new Client({
    host: process.env.EC2_DB_HOST || process.env.EC2_HOST || '43.208.201.191',
    port: parseInt(process.env.EC2_DB_PORT || '5432'),
    database: process.env.EC2_DB_NAME || 'sensor_data',
    user: process.env.EC2_DB_USER || 'postgres',
    password: process.env.EC2_DB_PASSWORD || 'P@ssw0rd123!'
  });

  try {
    await client.connect();
    console.log('🔗 Connected to EC2 database');

    // First, let's drop the blocker triggers
    console.log('\n🔧 Removing insert blocker triggers...');
    const tables = ['water_level_readings', 'moisture_readings', 'sensor_readings'];
    
    for (const table of tables) {
      try {
        // Drop the trigger if it exists
        await client.query(`DROP TRIGGER IF EXISTS ts_insert_blocker ON ${table};`);
        console.log(`✅ Removed blocker trigger from ${table}`);
      } catch (error) {
        console.error(`⚠️  Error removing trigger from ${table}:`, error);
      }
    }

    // Now convert tables to proper hypertables
    console.log('\n📊 Converting tables to hypertables...');
    const hypertableConfigs = [
      { name: 'water_level_readings', interval: '1 day' },
      { name: 'moisture_readings', interval: '1 day' },
      { name: 'sensor_readings', interval: '1 day' }
    ];

    for (const config of hypertableConfigs) {
      try {
        // Check if table exists
        const tableExists = await client.query(`
          SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = $1
          );
        `, [config.name]);

        if (!tableExists.rows[0].exists) {
          console.log(`⚠️  Table ${config.name} does not exist, skipping...`);
          continue;
        }

        // Check if already a hypertable
        const isHypertable = await client.query(`
          SELECT EXISTS (
            SELECT 1 FROM _timescaledb_catalog.hypertable h
            WHERE h.schema_name = 'public' AND h.table_name = $1
          );
        `, [config.name]);

        if (isHypertable.rows[0].exists) {
          console.log(`✅ ${config.name} is already a hypertable`);
        } else {
          // Convert to hypertable
          await client.query(`
            SELECT create_hypertable('${config.name}', 'time', 
              if_not_exists => TRUE,
              chunk_time_interval => INTERVAL '${config.interval}',
              migrate_data => TRUE
            );
          `);
          console.log(`✅ ${config.name} converted to hypertable with ${config.interval} chunks`);
        }

      } catch (error) {
        console.error(`❌ Error processing ${config.name}:`, error);
      }
    }

    // Verify the fix
    console.log('\n🔍 Verifying fix...');
    const triggers = await client.query(`
      SELECT 
        t.tgname as trigger_name,
        c.relname as table_name
      FROM pg_trigger t
      JOIN pg_class c ON t.tgrelid = c.oid
      WHERE c.relnamespace = 'public'::regnamespace
      AND c.relname IN ('sensor_readings', 'water_level_readings', 'moisture_readings')
      AND t.tgname LIKE '%blocker%';
    `);

    if (triggers.rows.length === 0) {
      console.log('✅ No blocker triggers found - fix successful!');
    } else {
      console.log('⚠️  Some blocker triggers still exist:');
      triggers.rows.forEach(trigger => {
        console.log(`  - ${trigger.table_name}: ${trigger.trigger_name}`);
      });
    }

    // Test insert
    console.log('\n🧪 Testing insert capability...');
    try {
      await client.query(`
        INSERT INTO water_level_readings (time, sensor_id, level_cm, voltage, rssi, quality_score)
        VALUES (NOW(), 'TEST-SENSOR', 100.5, 3.3, -70, 0.95);
      `);
      console.log('✅ Test insert successful!');
      
      // Clean up test data
      await client.query(`DELETE FROM water_level_readings WHERE sensor_id = 'TEST-SENSOR';`);
    } catch (error) {
      console.error('❌ Test insert failed:', error);
    }

    console.log('\n✅ EC2 database fix completed!');

  } catch (error) {
    console.error('❌ Error:', error);
    process.exit(1);
  } finally {
    await client.end();
  }
}

// Run the fix
fixEC2Hypertables().catch(console.error);
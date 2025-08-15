import { Client } from 'pg';
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load environment variables
dotenv.config({ path: path.join(__dirname, '..', '.env.local') });
dotenv.config();

async function checkEC2Constraints() {
  const client = new Client({
    host: process.env.EC2_DB_HOST || '43.209.22.250',
    port: parseInt(process.env.EC2_DB_PORT || '5432'),
    database: process.env.EC2_DB_NAME || 'sensor_data',
    user: process.env.EC2_DB_USER || 'postgres',
    password: process.env.EC2_DB_PASSWORD || 'P@ssw0rd123!'
  });

  try {
    await client.connect();
    console.log('🔗 Connected to EC2 database');

    // Check foreign key constraints
    console.log('\n🔑 Checking foreign key constraints...');
    const constraints = await client.query(`
      SELECT 
        tc.table_name,
        tc.constraint_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
      FROM information_schema.table_constraints AS tc
      JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
      JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
      WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND tc.table_name IN ('water_level_readings', 'moisture_readings', 'sensor_readings');
    `);

    if (constraints.rows.length > 0) {
      console.log('\nForeign key constraints found:');
      constraints.rows.forEach(c => {
        console.log(`  - ${c.table_name}.${c.column_name} → ${c.foreign_table_name}.${c.foreign_column_name}`);
      });
    } else {
      console.log('No foreign key constraints found');
    }

    // Check sensor_registry table
    console.log('\n📊 Checking sensor_registry table...');
    const registryCount = await client.query('SELECT COUNT(*) FROM sensor_registry;');
    console.log(`  Total sensors in registry: ${registryCount.rows[0].count}`);

    // Check some sample sensor IDs
    console.log('\n🔍 Sample sensor IDs in registry:');
    const sampleSensors = await client.query('SELECT sensor_id, sensor_type FROM sensor_registry LIMIT 10;');
    sampleSensors.rows.forEach(s => {
      console.log(`  - ${s.sensor_id} (${s.sensor_type})`);
    });

    // Check if our common sensor IDs exist
    console.log('\n🔍 Checking for common sensor IDs...');
    const commonIds = ['AWD-5003', 'test-001-test-001', '222410831183230', 'AWD-B7E6'];
    for (const id of commonIds) {
      const exists = await client.query('SELECT EXISTS(SELECT 1 FROM sensor_registry WHERE sensor_id = $1);', [id]);
      console.log(`  - ${id}: ${exists.rows[0].exists ? '✅ exists' : '❌ missing'}`);
    }

  } catch (error) {
    console.error('❌ Error:', error);
  } finally {
    await client.end();
  }
}

// Run the check
checkEC2Constraints().catch(console.error);
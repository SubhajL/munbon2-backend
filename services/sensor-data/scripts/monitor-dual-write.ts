import { Client } from 'pg';
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load environment variables
dotenv.config({ path: path.join(__dirname, '..', '.env.local') });
dotenv.config();

async function monitorDualWrite() {
  const localClient = new Client({
    host: process.env.TIMESCALE_HOST || 'localhost',
    port: parseInt(process.env.TIMESCALE_PORT || '5433'),
    database: process.env.TIMESCALE_DB || 'munbon_timescale',
    user: process.env.TIMESCALE_USER || 'postgres',
    password: process.env.TIMESCALE_PASSWORD || 'postgres'
  });

  const ec2Client = new Client({
    host: process.env.EC2_DB_HOST || '43.209.22.250',
    port: parseInt(process.env.EC2_DB_PORT || '5432'),
    database: process.env.EC2_DB_NAME || 'sensor_data',
    user: process.env.EC2_DB_USER || 'postgres',
    password: process.env.EC2_DB_PASSWORD || 'P@ssw0rd123!'
  });

  try {
    // Connect to both databases
    await localClient.connect();
    await ec2Client.connect();
    
    console.log('📊 Dual-Write Monitoring Dashboard');
    console.log('===================================');
    console.log(`Dual-write enabled: ${process.env.ENABLE_DUAL_WRITE === 'true' ? '✅' : '❌'}`);
    console.log('');

    // Get counts
    const localWaterLevel = await localClient.query('SELECT COUNT(*) FROM water_level_readings');
    const ec2WaterLevel = await ec2Client.query('SELECT COUNT(*) FROM water_level_readings');
    
    const localMoisture = await localClient.query('SELECT COUNT(*) FROM moisture_readings');
    const ec2Moisture = await ec2Client.query('SELECT COUNT(*) FROM moisture_readings');
    
    const localSensors = await localClient.query('SELECT COUNT(*) FROM sensor_registry');
    const ec2Sensors = await ec2Client.query('SELECT COUNT(*) FROM sensor_registry');

    console.log('📊 Record Counts:');
    console.log('┌─────────────────────┬──────────┬──────────┬──────────┐');
    console.log('│ Table               │ Local    │ EC2      │ Diff     │');
    console.log('├─────────────────────┼──────────┼──────────┼──────────┤');
    console.log(`│ Water Level         │ ${localWaterLevel.rows[0].count.toString().padEnd(8)} │ ${ec2WaterLevel.rows[0].count.toString().padEnd(8)} │ ${(localWaterLevel.rows[0].count - ec2WaterLevel.rows[0].count).toString().padEnd(8)} │`);
    console.log(`│ Moisture            │ ${localMoisture.rows[0].count.toString().padEnd(8)} │ ${ec2Moisture.rows[0].count.toString().padEnd(8)} │ ${(localMoisture.rows[0].count - ec2Moisture.rows[0].count).toString().padEnd(8)} │`);
    console.log(`│ Sensors             │ ${localSensors.rows[0].count.toString().padEnd(8)} │ ${ec2Sensors.rows[0].count.toString().padEnd(8)} │ ${(localSensors.rows[0].count - ec2Sensors.rows[0].count).toString().padEnd(8)} │`);
    console.log('└─────────────────────┴──────────┴──────────┴──────────┘');
    console.log('');

    // Get recent data timestamps
    const localRecentWL = await localClient.query(
      'SELECT MAX(time) as latest FROM water_level_readings'
    );
    const ec2RecentWL = await ec2Client.query(
      'SELECT MAX(time) as latest FROM water_level_readings'
    );
    
    const localRecentM = await localClient.query(
      'SELECT MAX(time) as latest FROM moisture_readings'
    );
    const ec2RecentM = await ec2Client.query(
      'SELECT MAX(time) as latest FROM moisture_readings'
    );

    console.log('🕐 Latest Data Timestamps:');
    console.log('┌─────────────────────┬──────────────────────────┬──────────────────────────┐');
    console.log('│ Data Type           │ Local                    │ EC2                      │');
    console.log('├─────────────────────┼──────────────────────────┼──────────────────────────┤');
    console.log(`│ Water Level         │ ${formatTimestamp(localRecentWL.rows[0].latest)} │ ${formatTimestamp(ec2RecentWL.rows[0].latest)} │`);
    console.log(`│ Moisture            │ ${formatTimestamp(localRecentM.rows[0].latest)} │ ${formatTimestamp(ec2RecentM.rows[0].latest)} │`);
    console.log('└─────────────────────┴──────────────────────────┴──────────────────────────┘');
    console.log('');

    // Get sync status
    const timeDiffWL = localRecentWL.rows[0].latest && ec2RecentWL.rows[0].latest 
      ? Math.abs(new Date(localRecentWL.rows[0].latest).getTime() - new Date(ec2RecentWL.rows[0].latest).getTime()) / 1000 / 60
      : null;
    
    const timeDiffM = localRecentM.rows[0].latest && ec2RecentM.rows[0].latest
      ? Math.abs(new Date(localRecentM.rows[0].latest).getTime() - new Date(ec2RecentM.rows[0].latest).getTime()) / 1000 / 60
      : null;

    console.log('🔄 Sync Status:');
    if (timeDiffWL !== null) {
      const wlStatus = timeDiffWL < 5 ? '✅ In Sync' : timeDiffWL < 60 ? '⚠️  Behind' : '❌ Out of Sync';
      console.log(`  Water Level: ${wlStatus} (${timeDiffWL.toFixed(1)} minutes difference)`);
    }
    if (timeDiffM !== null) {
      const mStatus = timeDiffM < 5 ? '✅ In Sync' : timeDiffM < 60 ? '⚠️  Behind' : '❌ Out of Sync';
      console.log(`  Moisture: ${mStatus} (${timeDiffM.toFixed(1)} minutes difference)`);
    }

    // Check EC2 hypertable status
    console.log('\n📊 EC2 Hypertable Status:');
    try {
      const hypertables = await ec2Client.query(`
        SELECT 
          h.schema_name,
          h.table_name,
          h.num_chunks
        FROM timescaledb_information.hypertables h
        WHERE h.schema_name = 'public';
      `);
      
      if (hypertables.rows.length > 0) {
        hypertables.rows.forEach(ht => {
          console.log(`  ✅ ${ht.table_name}: ${ht.num_chunks} chunks`);
        });
      } else {
        console.log('  ⚠️  No hypertables found');
      }
    } catch (err) {
      console.log('  ℹ️  Using alternative hypertable check...');
      const altCheck = await ec2Client.query(`
        SELECT COUNT(*) FROM _timescaledb_catalog.hypertable WHERE schema_name = 'public';
      `);
      console.log(`  Found ${altCheck.rows[0].count} hypertables`);
    }

  } catch (error) {
    console.error('❌ Error:', error);
  } finally {
    await localClient.end();
    await ec2Client.end();
  }
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return 'No data'.padEnd(24);
  const date = new Date(ts);
  return date.toISOString().substring(0, 19).replace('T', ' ').padEnd(24);
}

// Run the monitor
monitorDualWrite().catch(console.error);
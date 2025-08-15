import { Client } from 'pg';
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load environment variables
dotenv.config();
dotenv.config({ path: path.join(__dirname, '..', '.env.ec2') });
dotenv.config({ path: path.join(__dirname, '..', '.env.dual-write') });

interface DatabaseCounts {
  waterLevelCount: number;
  moistureCount: number;
  sensorRegistryCount: number;
  timestamp: Date;
}

async function getDatabaseCounts(client: Client, dbName: string): Promise<DatabaseCounts> {
  try {
    // Get water level count
    const waterLevelResult = await client.query('SELECT COUNT(*) FROM water_level_readings');
    const waterLevelCount = parseInt(waterLevelResult.rows[0].count);

    // Get moisture count
    const moistureResult = await client.query('SELECT COUNT(*) FROM moisture_readings');
    const moistureCount = parseInt(moistureResult.rows[0].count);

    // Get sensor registry count
    const sensorRegistryResult = await client.query('SELECT COUNT(*) FROM sensor_registry');
    const sensorRegistryCount = parseInt(sensorRegistryResult.rows[0].count);

    console.log(`\n📊 ${dbName} Database Counts:`);
    console.log(`   Water Level Readings: ${waterLevelCount}`);
    console.log(`   Moisture Readings: ${moistureCount}`);
    console.log(`   Registered Sensors: ${sensorRegistryCount}`);

    return {
      waterLevelCount,
      moistureCount,
      sensorRegistryCount,
      timestamp: new Date()
    };
  } catch (error) {
    console.error(`❌ Error getting counts from ${dbName}:`, error);
    throw error;
  }
}

async function getLatestReadings(client: Client, dbName: string, limit: number = 5) {
  try {
    console.log(`\n🕐 Latest readings from ${dbName}:`);
    
    // Latest water level readings
    const waterLevelResult = await client.query(`
      SELECT time, sensor_id, level_cm 
      FROM water_level_readings 
      ORDER BY time DESC 
      LIMIT $1
    `, [limit]);
    
    console.log('\n  Water Level:');
    waterLevelResult.rows.forEach(row => {
      console.log(`    ${row.time.toISOString()} - ${row.sensor_id}: ${row.level_cm} cm`);
    });

    // Latest moisture readings
    const moistureResult = await client.query(`
      SELECT time, sensor_id, moisture_surface_pct, moisture_deep_pct 
      FROM moisture_readings 
      ORDER BY time DESC 
      LIMIT $1
    `, [limit]);
    
    console.log('\n  Moisture:');
    moistureResult.rows.forEach(row => {
      console.log(`    ${row.time.toISOString()} - ${row.sensor_id}: Surface=${row.moisture_surface_pct}%, Deep=${row.moisture_deep_pct}%`);
    });
  } catch (error) {
    console.error(`❌ Error getting latest readings from ${dbName}:`, error);
  }
}

async function compareDatabases() {
  console.log('🔍 Comparing Local and EC2 Databases...\n');
  console.log('Dual-write enabled:', process.env.ENABLE_DUAL_WRITE === 'true');
  
  // Local database connection
  const localClient = new Client({
    host: process.env.TIMESCALE_HOST || 'localhost',
    port: parseInt(process.env.TIMESCALE_PORT || '5433'),
    database: process.env.TIMESCALE_DB || 'munbon_timescale',
    user: process.env.TIMESCALE_USER || 'postgres',
    password: process.env.TIMESCALE_PASSWORD || 'postgres'
  });

  // EC2 database connection
  const ec2Client = new Client({
    host: process.env.EC2_DB_HOST || '43.209.22.250',
    port: parseInt(process.env.EC2_DB_PORT || '5432'),
    database: process.env.EC2_DB_NAME || 'sensor_data',
    user: process.env.EC2_DB_USER || 'postgres',
    password: process.env.EC2_DB_PASSWORD || 'postgres'
  });

  try {
    // Connect to both databases
    await localClient.connect();
    console.log('✅ Connected to local database');
    
    await ec2Client.connect();
    console.log('✅ Connected to EC2 database');

    // Get initial counts
    console.log('\n=== INITIAL STATE ===');
    const localInitial = await getDatabaseCounts(localClient, 'Local');
    const ec2Initial = await getDatabaseCounts(ec2Client, 'EC2');

    // Compare counts
    console.log('\n📊 Count Differences:');
    console.log(`   Water Level: Local=${localInitial.waterLevelCount}, EC2=${ec2Initial.waterLevelCount}, Diff=${localInitial.waterLevelCount - ec2Initial.waterLevelCount}`);
    console.log(`   Moisture: Local=${localInitial.moistureCount}, EC2=${ec2Initial.moistureCount}, Diff=${localInitial.moistureCount - ec2Initial.moistureCount}`);
    console.log(`   Sensors: Local=${localInitial.sensorRegistryCount}, EC2=${ec2Initial.sensorRegistryCount}, Diff=${localInitial.sensorRegistryCount - ec2Initial.sensorRegistryCount}`);

    // Get latest readings
    await getLatestReadings(localClient, 'Local', 3);
    await getLatestReadings(ec2Client, 'EC2', 3);

    // Monitor for changes if requested
    if (process.argv.includes('--monitor')) {
      console.log('\n\n🔄 Monitoring for changes (press Ctrl+C to stop)...');
      
      setInterval(async () => {
        console.log('\n' + '='.repeat(50));
        console.log(`⏰ Check at ${new Date().toISOString()}`);
        
        const localCurrent = await getDatabaseCounts(localClient, 'Local');
        const ec2Current = await getDatabaseCounts(ec2Client, 'EC2');
        
        // Show changes since initial
        console.log('\n📈 Changes since start:');
        console.log(`   Local Water Level: +${localCurrent.waterLevelCount - localInitial.waterLevelCount}`);
        console.log(`   EC2 Water Level: +${ec2Current.waterLevelCount - ec2Initial.waterLevelCount}`);
        console.log(`   Local Moisture: +${localCurrent.moistureCount - localInitial.moistureCount}`);
        console.log(`   EC2 Moisture: +${ec2Current.moistureCount - ec2Initial.moistureCount}`);
        
      }, 30000); // Check every 30 seconds
    }

  } catch (error) {
    console.error('❌ Error:', error);
  } finally {
    if (!process.argv.includes('--monitor')) {
      await localClient.end();
      await ec2Client.end();
      console.log('\n✅ Test completed');
    }
  }
}

// Run the comparison
compareDatabases().catch(console.error);
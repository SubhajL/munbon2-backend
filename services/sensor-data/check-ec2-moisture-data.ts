import { Pool } from 'pg';
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load EC2 specific env vars
dotenv.config({ path: path.join(__dirname, '.env.ec2') });
dotenv.config(); // Load default env vars as fallback

// EC2 database configuration
const ec2Pool = new Pool({
  host: process.env.EC2_DB_HOST || '43.208.201.191',
  port: parseInt(process.env.EC2_DB_PORT || '5432'),
  database: process.env.EC2_DB_NAME || 'sensor_data',
  user: process.env.EC2_DB_USER || 'postgres',
  password: process.env.EC2_DB_PASSWORD || '__ROTATED_DB_PASSWORD__',
  connectionTimeoutMillis: 5000,
});

async function checkEC2MoistureData() {
  try {
    console.log('🔍 Checking moisture data on EC2 database...');
    console.log(`Host: ${process.env.EC2_DB_HOST || '43.208.201.191'}`);
    console.log(`Database: ${process.env.EC2_DB_NAME || 'sensor_data'}`);
    
    // Test connection
    await ec2Pool.query('SELECT NOW()');
    console.log('✅ Connected to EC2 database successfully\n');

    // Check if moisture_readings table exists
    const tableCheck = await ec2Pool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'moisture_readings'
      );
    `);
    
    if (!tableCheck.rows[0].exists) {
      console.log('❌ moisture_readings table does not exist on EC2');
      return;
    }

    // Check recent moisture readings (last 24 hours)
    console.log('=== Recent Moisture Data (Last 24 Hours) ===');
    const recentResult = await ec2Pool.query(`
      SELECT 
        time AT TIME ZONE 'UTC' as utc_time,
        sensor_id,
        moisture_surface_pct,
        moisture_deep_pct,
        temp_surface_c,
        temp_deep_c,
        ambient_humidity_pct,
        ambient_temp_c,
        flood_status,
        voltage,
        quality_score
      FROM moisture_readings 
      WHERE time > NOW() - INTERVAL '24 hours'
      ORDER BY time DESC
      LIMIT 20
    `);
    
    console.log(`Found ${recentResult.rows.length} moisture readings in the last 24 hours`);
    if (recentResult.rows.length > 0) {
      console.table(recentResult.rows);
    }

    // Check total count and date range
    console.log('\n=== Moisture Data Summary ===');
    const summaryResult = await ec2Pool.query(`
      SELECT 
        COUNT(*) as total_records,
        MIN(time) as earliest_record,
        MAX(time) as latest_record,
        COUNT(DISTINCT sensor_id) as unique_sensors
      FROM moisture_readings
    `);
    
    console.table(summaryResult.rows);

    // Check data by sensor
    console.log('\n=== Data Count by Sensor ===');
    const sensorResult = await ec2Pool.query(`
      SELECT 
        sensor_id,
        COUNT(*) as record_count,
        MIN(time) as first_reading,
        MAX(time) as last_reading,
        AVG(moisture_surface_pct) as avg_surface_moisture,
        AVG(moisture_deep_pct) as avg_deep_moisture
      FROM moisture_readings
      WHERE time > NOW() - INTERVAL '7 days'
      GROUP BY sensor_id
      ORDER BY last_reading DESC
    `);
    
    if (sensorResult.rows.length > 0) {
      console.table(sensorResult.rows);
    } else {
      console.log('No moisture data found in the last 7 days');
    }

    // Check today's data specifically
    console.log('\n=== Today\'s Moisture Data ===');
    const todayResult = await ec2Pool.query(`
      SELECT 
        COUNT(*) as readings_today,
        COUNT(DISTINCT sensor_id) as sensors_today
      FROM moisture_readings
      WHERE time >= CURRENT_DATE
    `);
    
    console.table(todayResult.rows);

    // Check if dual-write is working by comparing with sensor_readings
    console.log('\n=== Checking sensor_readings table for moisture data ===');
    const sensorReadingsResult = await ec2Pool.query(`
      SELECT 
        COUNT(*) as moisture_count_in_sensor_readings
      FROM sensor_readings
      WHERE sensor_type = 'moisture'
        AND time > NOW() - INTERVAL '24 hours'
    `);
    
    console.table(sensorReadingsResult.rows);

  } catch (error) {
    console.error('❌ Error connecting to EC2 database:', error);
    if (error instanceof Error) {
      console.error('Error details:', error.message);
    }
  } finally {
    await ec2Pool.end();
  }
}

// Run the check
checkEC2MoistureData();
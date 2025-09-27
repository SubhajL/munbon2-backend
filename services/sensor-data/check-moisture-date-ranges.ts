import { Pool } from 'pg';

const ec2Pool = new Pool({
  host: '43.208.201.191',
  port: 5432,
  database: 'sensor_data',
  user: 'postgres',
  password: '__ROTATED_DB_PASSWORD__',
  connectionTimeoutMillis: 5000,
});

async function checkMoistureDateRanges() {
  try {
    // Overall date range and statistics
    console.log('🔍 MOISTURE DATA DATE RANGE ANALYSIS\n');
    
    const overallStats = await ec2Pool.query(`
      SELECT 
        COUNT(*) as total_records,
        COUNT(DISTINCT sensor_id) as unique_sensors,
        MIN(time) as earliest_date,
        MAX(time) as latest_date,
        MIN(time)::date as first_day,
        MAX(time)::date as last_day,
        (MAX(time)::date - MIN(time)::date) as days_span
      FROM moisture_readings
    `);
    
    console.log('=== Overall Statistics ===');
    console.table(overallStats.rows);

    // Monthly breakdown
    const monthlyBreakdown = await ec2Pool.query(`
      SELECT 
        DATE_TRUNC('month', time) as month,
        COUNT(*) as records,
        COUNT(DISTINCT sensor_id) as sensors,
        COUNT(DISTINCT DATE(time)) as active_days
      FROM moisture_readings
      GROUP BY DATE_TRUNC('month', time)
      ORDER BY month
    `);
    
    console.log('\n=== Monthly Breakdown ===');
    console.table(monthlyBreakdown.rows);

    // Daily data for the last 30 days
    const dailyRecent = await ec2Pool.query(`
      SELECT 
        DATE(time) as date,
        COUNT(*) as records,
        COUNT(DISTINCT sensor_id) as sensors,
        MIN(time)::time as first_reading,
        MAX(time)::time as last_reading
      FROM moisture_readings
      WHERE time > CURRENT_DATE - INTERVAL '30 days'
      GROUP BY DATE(time)
      ORDER BY date DESC
    `);
    
    console.log('\n=== Last 30 Days Daily Activity ===');
    console.table(dailyRecent.rows);

    // Check for data gaps
    const dataGaps = await ec2Pool.query(`
      WITH daily_data AS (
        SELECT DATE(time) as date, COUNT(*) as count
        FROM moisture_readings
        GROUP BY DATE(time)
      ),
      date_series AS (
        SELECT generate_series(
          (SELECT MIN(date) FROM daily_data),
          (SELECT MAX(date) FROM daily_data),
          '1 day'::interval
        )::date as date
      )
      SELECT 
        ds.date,
        COALESCE(dd.count, 0) as record_count,
        CASE WHEN dd.count IS NULL THEN 'NO DATA' ELSE 'OK' END as status
      FROM date_series ds
      LEFT JOIN daily_data dd ON ds.date = dd.date
      WHERE dd.count IS NULL OR dd.count = 0
      ORDER BY ds.date DESC
      LIMIT 20
    `);
    
    console.log('\n=== Recent Data Gaps (Days with No Data) ===');
    if (dataGaps.rows.length > 0) {
      console.table(dataGaps.rows);
    } else {
      console.log('No gaps found in the date range');
    }

    // Check NULL values distribution
    const nullValuesCheck = await ec2Pool.query(`
      SELECT 
        COUNT(*) as total_records,
        COUNT(moisture_surface_pct) as has_surface_moisture,
        COUNT(moisture_deep_pct) as has_deep_moisture,
        COUNT(temp_surface_c) as has_surface_temp,
        COUNT(temp_deep_c) as has_deep_temp,
        COUNT(voltage) as has_voltage,
        COUNT(ambient_humidity_pct) as has_ambient_humidity,
        COUNT(ambient_temp_c) as has_ambient_temp
      FROM moisture_readings
    `);
    
    console.log('\n=== Data Completeness (Non-NULL Values) ===');
    console.table(nullValuesCheck.rows);

    // Sample of records with actual values
    const sampleWithValues = await ec2Pool.query(`
      SELECT 
        time,
        sensor_id,
        moisture_surface_pct,
        moisture_deep_pct,
        temp_surface_c,
        temp_deep_c,
        voltage
      FROM moisture_readings
      WHERE moisture_surface_pct IS NOT NULL
         OR moisture_deep_pct IS NOT NULL
         OR temp_surface_c IS NOT NULL
      ORDER BY time DESC
      LIMIT 10
    `);
    
    console.log('\n=== Sample Records with Actual Values ===');
    if (sampleWithValues.rows.length > 0) {
      console.table(sampleWithValues.rows);
    } else {
      console.log('No records found with non-NULL sensor values');
    }

  } finally {
    await ec2Pool.end();
  }
}

checkMoistureDateRanges();
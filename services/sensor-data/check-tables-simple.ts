import { Pool } from 'pg';
import * as dotenv from 'dotenv';

dotenv.config();

async function checkTables() {
  const pool = new Pool({
    host: process.env.TIMESCALE_HOST || 'localhost',
    port: parseInt(process.env.TIMESCALE_PORT || '5433'),
    database: process.env.TIMESCALE_DB || 'munbon_timescale',
    user: process.env.TIMESCALE_USER || 'postgres',
    password: process.env.TIMESCALE_PASSWORD || 'postgres'
  });

  try {
    // Check tables
    console.log('=== Tables in database ===');
    const tablesResult = await pool.query(`
      SELECT tablename 
      FROM pg_tables 
      WHERE schemaname = 'public'
      ORDER BY tablename;
    `);
    console.log('Tables found:');
    tablesResult.rows.forEach(row => console.log('  -', row.tablename));
    
    // Test water level insert (which we know works)
    console.log('\n=== Testing water_level_readings insert ===');
    try {
      await pool.query(`
        INSERT INTO water_level_readings 
        (time, sensor_id, location_lat, location_lng, level_cm, voltage, rssi, quality_score)
        VALUES (NOW(), 'TEST-WL', 14.4972, 102.1505, 123.45, 3.72, -65, 0.95);
      `);
      console.log('✓ water_level_readings INSERT: Success');
      
      const verify = await pool.query(`SELECT * FROM water_level_readings WHERE sensor_id = 'TEST-WL'`);
      console.log('  Verified:', verify.rows.length, 'record(s) found');
      
      await pool.query(`DELETE FROM water_level_readings WHERE sensor_id = 'TEST-WL'`);
    } catch (err: any) {
      console.log('✗ water_level_readings INSERT: Failed -', err.code, err.message);
    }
    
    // Test moisture insert
    console.log('\n=== Testing moisture_readings insert ===');
    try {
      await pool.query(`
        INSERT INTO moisture_readings 
        (time, sensor_id, location_lat, location_lng, moisture_surface_pct, moisture_deep_pct,
         temp_surface_c, temp_deep_c, ambient_humidity_pct, ambient_temp_c,
         flood_status, voltage, quality_score)
        VALUES (NOW(), 'TEST-M', 14.4972, 102.1505, 38.2, 48.7, 26.2, 25.9, 55.5, 27.8, false, 4.05, 0.95);
      `);
      console.log('✓ moisture_readings INSERT: Success');
      
      const verify = await pool.query(`SELECT * FROM moisture_readings WHERE sensor_id = 'TEST-M'`);
      console.log('  Verified:', verify.rows.length, 'record(s) found');
      
      await pool.query(`DELETE FROM moisture_readings WHERE sensor_id = 'TEST-M'`);
    } catch (err: any) {
      console.log('✗ moisture_readings INSERT: Failed -', err.code, err.message);
    }
    
    // Let's check if the tables are set up differently
    console.log('\n=== Checking table inheritance ===');
    const inheritanceQuery = `
      SELECT 
        c.relname AS child_table,
        p.relname AS parent_table
      FROM pg_inherits i
      JOIN pg_class c ON c.oid = i.inhrelid
      JOIN pg_class p ON p.oid = i.inhparent
      WHERE c.relname IN ('water_level_readings', 'moisture_readings');
    `;
    
    const inheritanceResult = await pool.query(inheritanceQuery);
    if (inheritanceResult.rows.length > 0) {
      console.log('Table inheritance found:');
      console.table(inheritanceResult.rows);
    } else {
      console.log('No table inheritance found');
    }
    
    // Check for any triggers or rules
    console.log('\n=== Checking triggers ===');
    const triggersQuery = `
      SELECT 
        tablename,
        triggername,
        enabled
      FROM pg_trigger t
      JOIN pg_class c ON t.tgrelid = c.oid
      JOIN pg_tables tb ON c.relname = tb.tablename
      WHERE tb.schemaname = 'public'
        AND tb.tablename IN ('water_level_readings', 'moisture_readings')
        AND t.tgisinternal = false;
    `;
    
    const triggersResult = await pool.query(triggersQuery);
    if (triggersResult.rows.length > 0) {
      console.log('Triggers found:');
      console.table(triggersResult.rows);
    } else {
      console.log('No custom triggers found');
    }
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await pool.end();
  }
}

checkTables();
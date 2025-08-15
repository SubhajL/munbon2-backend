#!/usr/bin/env node

/**
 * Copy data from agricultural_plots to ros.plots table
 * with zone/section assignment based on sub_member field
 */

const { Pool } = require('pg');

// Database connection
const pool = new Pool({
  host: 'localhost',
  port: 5434,
  database: 'munbon_dev',
  user: 'postgres',
  password: 'postgres'
});

async function checkRosSchema() {
  console.log('Checking ros schema and tables...');
  
  try {
    // Check if ros schema exists
    const schemaResult = await pool.query(`
      SELECT schema_name 
      FROM information_schema.schemata 
      WHERE schema_name = 'ros'
    `);
    
    if (schemaResult.rows.length === 0) {
      console.log('Creating ros schema...');
      await pool.query('CREATE SCHEMA ros');
    }
    
    // Check if plots table exists
    const tableResult = await pool.query(`
      SELECT table_name 
      FROM information_schema.tables 
      WHERE table_schema = 'ros' AND table_name = 'plots'
    `);
    
    if (tableResult.rows.length === 0) {
      console.log('Creating ros.plots table...');
      await pool.query(`
        -- Create plot information table
        CREATE TABLE IF NOT EXISTS ros.plots (
            id SERIAL PRIMARY KEY,
            plot_id VARCHAR(50) UNIQUE NOT NULL,
            plot_code VARCHAR(50),
            area_rai DECIMAL(10,2) NOT NULL,
            geometry GEOMETRY(Polygon, 32648),
            parent_section_id VARCHAR(50),
            parent_zone_id VARCHAR(50),
            aos_station VARCHAR(100) DEFAULT 'นครราชสีมา',
            province VARCHAR(100) DEFAULT 'นครราชสีมา',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_plots_geometry ON ros.plots USING GIST(geometry);
        CREATE INDEX IF NOT EXISTS idx_plots_parent_section ON ros.plots(parent_section_id);
        CREATE INDEX IF NOT EXISTS idx_plots_parent_zone ON ros.plots(parent_zone_id);
      `);
    }
    
    console.log('Schema and tables ready.');
  } catch (error) {
    console.error('Error setting up schema:', error);
    throw error;
  }
}

async function copyToRosPlots() {
  console.log('\nCopying data from agricultural_plots to ros.plots...');
  
  try {
    // First check what data we have
    const sourceCount = await pool.query(`
      SELECT COUNT(*) as count,
             COUNT(DISTINCT (properties->>'ridAttributes')::jsonb->>'subMember') as unique_sub_members
      FROM gis.agricultural_plots
    `);
    console.log(`Found ${sourceCount.rows[0].count} parcels with ${sourceCount.rows[0].unique_sub_members} unique sub_members`);
    
    // Show sample data
    const sampleData = await pool.query(`
      SELECT plot_code,
             area_rai,
             (properties->>'ridAttributes')::jsonb->>'subMember' as sub_member,
             ST_GeometryType(boundary) as geom_type
      FROM gis.agricultural_plots
      LIMIT 5
    `);
    console.log('\nSample data:');
    sampleData.rows.forEach(row => {
      console.log(`  ${row.plot_code}: ${row.area_rai} rai, sub_member=${row.sub_member}, geom=${row.geom_type}`);
    });
    
    // Clear existing data in ros.plots
    await pool.query('TRUNCATE TABLE ros.plots RESTART IDENTITY CASCADE');
    
    // Copy data from agricultural_plots to ros.plots
    const result = await pool.query(`
      INSERT INTO ros.plots (
        plot_id,
        plot_code,
        area_rai,
        geometry,
        parent_section_id,
        parent_zone_id,
        aos_station,
        province
      )
      SELECT 
        plot_code as plot_id,
        plot_code,
        area_rai,
        ST_Transform(boundary, 32648) as geometry,  -- Transform from 4326 to 32648
        CASE 
          WHEN (properties->>'ridAttributes')::jsonb->>'subMember' IS NOT NULL 
          THEN 'section_' || (((properties->>'ridAttributes')::jsonb->>'subMember')::int - 1) / 10 + 1
          ELSE 'section_1'
        END as parent_section_id,
        CASE 
          WHEN (properties->>'ridAttributes')::jsonb->>'subMember' IS NOT NULL 
          THEN 'zone_' || (((properties->>'ridAttributes')::jsonb->>'subMember')::int - 1) / 3 + 1
          ELSE 'zone_1'
        END as parent_zone_id,
        'นครราชสีมา' as aos_station,
        'นครราชสีมา' as province
      FROM gis.agricultural_plots
      WHERE plot_code IS NOT NULL
        AND boundary IS NOT NULL
        AND area_rai IS NOT NULL
      ON CONFLICT (plot_id) DO UPDATE SET
        plot_code = EXCLUDED.plot_code,
        area_rai = EXCLUDED.area_rai,
        geometry = EXCLUDED.geometry,
        parent_section_id = EXCLUDED.parent_section_id,
        parent_zone_id = EXCLUDED.parent_zone_id,
        updated_at = NOW()
    `);
    
    console.log(`\nCopied ${result.rowCount} parcels to ros.plots`);
    
    // Verify the import
    const countResult = await pool.query('SELECT COUNT(*) FROM ros.plots');
    const zoneResult = await pool.query(`
      SELECT parent_zone_id, COUNT(*) as count 
      FROM ros.plots 
      GROUP BY parent_zone_id 
      ORDER BY parent_zone_id
    `);
    
    console.log(`\nTotal parcels in ros.plots: ${countResult.rows[0].count}`);
    console.log('\nParcels by zone:');
    zoneResult.rows.forEach(row => {
      console.log(`  ${row.parent_zone_id}: ${row.count} parcels`);
    });
    
    // Show section distribution
    const sectionResult = await pool.query(`
      SELECT parent_section_id, COUNT(*) as count 
      FROM ros.plots 
      GROUP BY parent_section_id 
      ORDER BY parent_section_id
    `);
    
    console.log('\nParcels by section:');
    sectionResult.rows.forEach(row => {
      console.log(`  ${row.parent_section_id}: ${row.count} parcels`);
    });
    
    // Show area summary
    const areaResult = await pool.query(`
      SELECT 
        SUM(area_rai) as total_rai,
        AVG(area_rai) as avg_rai,
        MIN(area_rai) as min_rai,
        MAX(area_rai) as max_rai
      FROM ros.plots
    `);
    
    console.log('\nArea summary:');
    console.log(`  Total: ${parseFloat(areaResult.rows[0].total_rai).toFixed(2)} rai`);
    console.log(`  Average: ${parseFloat(areaResult.rows[0].avg_rai).toFixed(2)} rai`);
    console.log(`  Min: ${parseFloat(areaResult.rows[0].min_rai).toFixed(2)} rai`);
    console.log(`  Max: ${parseFloat(areaResult.rows[0].max_rai).toFixed(2)} rai`);
    
  } catch (error) {
    console.error('Error copying data:', error);
    throw error;
  }
}

async function main() {
  try {
    // Step 1: Setup schema
    await checkRosSchema();
    
    // Step 2: Copy to ros.plots
    await copyToRosPlots();
    
    console.log('\nImport completed successfully!');
    
  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

// Run the script
main();
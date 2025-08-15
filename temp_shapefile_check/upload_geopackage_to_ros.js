#!/usr/bin/env node

/**
 * Upload GeoPackage to GIS service and import into ros.plots table
 * 
 * This script:
 * 1. Uploads the merge3Amp GeoPackage to the GIS service
 * 2. The GIS service will process it and store in agricultural_plots
 * 3. Then we'll copy the data from agricultural_plots to ros.plots
 */

const fs = require('fs');
const path = require('path');
const FormData = require('form-data');
const axios = require('axios');
const { Pool } = require('pg');

// Configuration
const GIS_SERVICE_URL = process.env.GIS_SERVICE_URL || 'http://localhost:3007';
const GEOPACKAGE_PATH = path.join(__dirname, 'merge3Amp_32648_edit20230721.gpkg');

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

async function uploadGeoPackage() {
  console.log('Uploading GeoPackage to GIS service...');
  
  const form = new FormData();
  const fileStream = fs.createReadStream(GEOPACKAGE_PATH);
  form.append('file', fileStream, 'merge3Amp_32648_edit20230721.gpkg');
  form.append('description', 'RID agricultural plots for ROS import');
  
  try {
    const response = await axios.post(
      `${GIS_SERVICE_URL}/api/shapefile/upload`,
      form,
      {
        headers: {
          ...form.getHeaders(),
          'Authorization': 'Bearer dummy-token' // Add if auth is required
        },
        maxContentLength: Infinity,
        maxBodyLength: Infinity
      }
    );
    
    console.log('Upload successful:', response.data);
    return response.data;
  } catch (error) {
    if (error.response) {
      console.error('Upload failed:', error.response.data);
    } else {
      console.error('Upload error:', error.message);
    }
    throw error;
  }
}

async function copyToRosPlots() {
  console.log('Copying data from agricultural_plots to ros.plots...');
  
  try {
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
      ON CONFLICT (plot_id) DO UPDATE SET
        plot_code = EXCLUDED.plot_code,
        area_rai = EXCLUDED.area_rai,
        geometry = EXCLUDED.geometry,
        parent_section_id = EXCLUDED.parent_section_id,
        parent_zone_id = EXCLUDED.parent_zone_id,
        updated_at = NOW()
    `);
    
    console.log(`Copied ${result.rowCount} parcels to ros.plots`);
    
    // Verify the import
    const countResult = await pool.query('SELECT COUNT(*) FROM ros.plots');
    const zoneResult = await pool.query(`
      SELECT parent_zone_id, COUNT(*) as count 
      FROM ros.plots 
      GROUP BY parent_zone_id 
      ORDER BY parent_zone_id
    `);
    
    console.log(`\nTotal parcels in ros.plots: ${countResult.rows[0].count}`);
    console.log('Parcels by zone:');
    zoneResult.rows.forEach(row => {
      console.log(`  ${row.parent_zone_id}: ${row.count} parcels`);
    });
    
  } catch (error) {
    console.error('Error copying data:', error);
    throw error;
  }
}

async function main() {
  try {
    // Check if GeoPackage exists
    if (!fs.existsSync(GEOPACKAGE_PATH)) {
      console.error(`GeoPackage not found: ${GEOPACKAGE_PATH}`);
      process.exit(1);
    }
    
    // Step 1: Setup schema
    await checkRosSchema();
    
    // Step 2: Check if data already exists in agricultural_plots
    const existingData = await pool.query(`
      SELECT COUNT(*) as count 
      FROM gis.agricultural_plots 
      WHERE plot_code LIKE 'MBN-%'
    `);
    
    if (existingData.rows[0].count > 0) {
      console.log(`Found ${existingData.rows[0].count} existing parcels in agricultural_plots`);
      console.log('Skipping upload, copying existing data to ros.plots...');
    } else {
      // Upload the GeoPackage
      await uploadGeoPackage();
      
      // Wait a bit for processing
      console.log('Waiting for processing to complete...');
      await new Promise(resolve => setTimeout(resolve, 5000));
    }
    
    // Step 3: Copy to ros.plots
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
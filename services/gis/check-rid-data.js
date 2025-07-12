require('dotenv').config();
const { Client } = require('pg');

async function checkRIDData() {
  const client = new Client({
    connectionString: process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/munbon_dev'
  });

  try {
    await client.connect();
    console.log('Connected to database');
    
    // Check agricultural_plots table
    const parcelResult = await client.query(`
      SELECT 
        plot_code,
        area_hectares,
        current_crop_type,
        planting_date,
        zone_id
      FROM gis.agricultural_plots 
      LIMIT 5
    `);
    
    console.log('\nAgricultural Plots Data:');
    console.log('========================');
    console.log(`Total parcels found: ${parcelResult.rowCount}`);
    parcelResult.rows.forEach(row => {
      console.log(`\nPlot Code: ${row.plot_code}`);
      console.log(`  Area (hectares): ${row.area_hectares}`);
      console.log(`  Crop Type: ${row.current_crop_type || 'N/A'}`);
      console.log(`  Planting Date: ${row.planting_date || 'N/A'}`);
      console.log(`  Zone ID: ${row.zone_id}`);
    });
    
    // Count total parcels
    const countResult = await client.query(`
      SELECT COUNT(*) as total FROM gis.agricultural_plots
    `);
    console.log(`\nTotal parcels in database: ${countResult.rows[0].total}`);
    
    // Check if properties column exists
    const columnResult = await client.query(`
      SELECT column_name, data_type 
      FROM information_schema.columns 
      WHERE table_schema = 'gis' 
      AND table_name = 'agricultural_plots' 
      AND column_name = 'properties'
    `);
    
    if (columnResult.rows.length > 0) {
      console.log('\nProperties column exists!');
      
      // Check properties data
      const propsResult = await client.query(`
        SELECT 
          plot_code,
          properties
        FROM gis.agricultural_plots 
        WHERE properties IS NOT NULL
        LIMIT 3
      `);
      
      if (propsResult.rows.length > 0) {
        console.log('\nProperties data found:');
        propsResult.rows.forEach(row => {
          console.log(`\nPlot: ${row.plot_code}`);
          console.log('Properties:', JSON.stringify(row.properties, null, 2));
        });
      } else {
        console.log('\nNo properties data found yet (need to re-upload shapefile)');
      }
    } else {
      console.log('\nProperties column does not exist yet. Run: psql -f add-properties-column.sql');
    }
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await client.end();
  }
}

checkRIDData();
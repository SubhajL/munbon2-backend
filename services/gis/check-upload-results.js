require('dotenv').config();
const { Client } = require('pg');

async function checkUploadResults() {
  const client = new Client({
    connectionString: process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5434/munbon_dev'
  });

  try {
    await client.connect();
    console.log('Connected to database');
    
    // Check total parcels
    const countResult = await client.query('SELECT COUNT(*) as total FROM gis.agricultural_plots');
    console.log(`\nTotal parcels in database: ${countResult.rows[0].total}`);
    
    // Check parcels with properties
    const propsCountResult = await client.query('SELECT COUNT(*) as total FROM gis.agricultural_plots WHERE properties IS NOT NULL');
    console.log(`Parcels with properties: ${propsCountResult.rows[0].total}`);
    
    // Check sample data
    const sampleResult = await client.query(`
      SELECT 
        plot_code,
        zone_id,
        properties->'ridAttributes'->>'seasonIrrM3PerRai' as water_demand,
        properties->'ridAttributes'->>'age' as plant_age,
        properties->'ridAttributes'->>'plantId' as plant_id,
        properties->'uploadId' as upload_id
      FROM gis.agricultural_plots 
      WHERE properties IS NOT NULL
      LIMIT 5
    `);
    
    console.log('\nSample parcels with RID attributes:');
    console.log('====================================');
    sampleResult.rows.forEach(row => {
      console.log(`Plot: ${row.plot_code}`);
      console.log(`  Zone: ${row.zone_id}`);
      console.log(`  Water Demand: ${row.water_demand} m³/rai`);
      console.log(`  Plant Age: ${row.plant_age} days`);
      console.log(`  Plant ID: ${row.plant_id}`);
      console.log(`  Upload ID: ${row.upload_id}`);
      console.log('---');
    });
    
    // Check upload record
    const uploadResult = await client.query(`
      SELECT * FROM gis.shape_file_uploads 
      WHERE upload_id = 'f127b01c-4f5c-46b6-a675-1a873e54c894'
    `);
    
    if (uploadResult.rows.length > 0) {
      console.log('\nUpload Record:');
      console.log('==============');
      const upload = uploadResult.rows[0];
      console.log(`Status: ${upload.status}`);
      console.log(`File: ${upload.file_name}`);
      console.log(`Parcels: ${upload.metadata?.parcelCount || 'N/A'}`);
      console.log(`Completed: ${upload.completed_at}`);
    }
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await client.end();
  }
}

checkUploadResults();
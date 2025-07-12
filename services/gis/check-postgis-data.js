require('dotenv').config();
const { Client } = require('pg');

async function checkPostGISData() {
  const client = new Client({
    connectionString: process.env.DATABASE_URL
  });

  try {
    await client.connect();
    
    // Check parcels table with PostGIS functions
    const result = await client.query(`
      SELECT 
        parcel_code,
        ST_GeometryType(geometry) as geom_type,
        ST_Area(geometry::geography) as area_m2,
        ST_AsText(ST_Centroid(geometry)) as centroid_wkt
      FROM gis.parcels 
      LIMIT 5
    `);
    
    console.log('PostGIS Parcels Data:');
    console.log('====================');
    result.rows.forEach(row => {
      console.log(`\nParcel: ${row.parcel_code}`);
      console.log(`  Geometry Type: ${row.geom_type}`);
      console.log(`  Area (m²): ${row.area_m2?.toFixed(2) || 'N/A'}`);
      console.log(`  Centroid: ${row.centroid_wkt || 'N/A'}`);
    });
    
    // Check spatial indexes
    const indexResult = await client.query(`
      SELECT indexname, indexdef 
      FROM pg_indexes 
      WHERE schemaname = 'gis' 
      AND tablename = 'parcels' 
      AND indexdef LIKE '%gist%'
    `);
    
    console.log('\nSpatial Indexes:');
    console.log('================');
    indexResult.rows.forEach(row => {
      console.log(`- ${row.indexname}`);
    });
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await client.end();
  }
}

checkPostGISData();
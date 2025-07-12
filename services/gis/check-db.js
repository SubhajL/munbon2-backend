require('dotenv').config();
const { Client } = require('pg');

async function checkDB() {
  const client = new Client({
    connectionString: process.env.DATABASE_URL
  });

  try {
    await client.connect();
    console.log('Connected to database');
    
    // Check uploads
    const uploadsResult = await client.query('SELECT * FROM gis.shape_file_uploads');
    console.log('\nShape file uploads:', uploadsResult.rows.length);
    if (uploadsResult.rows.length > 0) {
      console.log(uploadsResult.rows);
    }
    
    // Check parcels
    const parcelsResult = await client.query('SELECT COUNT(*) FROM gis.parcels_simple');
    console.log('\nParcels count:', parcelsResult.rows[0].count);
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await client.end();
  }
}

checkDB();
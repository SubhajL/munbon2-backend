const { Pool } = require('pg');

async function testConnection() {
  const pool = new Pool({
    host: '43.209.22.250',
    port: 5432,
    database: 'postgres',
    user: 'postgres',
    password: 'P@ssw0rd123!',
    ssl: false
  });

  try {
    console.log('Testing connection to EC2 PostgreSQL...');
    const result = await pool.query('SELECT NOW(), current_database(), version()');
    console.log('✅ Connection successful!');
    console.log('Database:', result.rows[0].current_database);
    console.log('Time:', result.rows[0].now);
    console.log('Version:', result.rows[0].version.split('\n')[0]);
    
    // Check for schemas
    const schemas = await pool.query(`
      SELECT schema_name 
      FROM information_schema.schemata 
      WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
      ORDER BY schema_name
    `);
    console.log('\nAvailable schemas:');
    schemas.rows.forEach(row => console.log('  -', row.schema_name));
    
    // Check for sensor tables
    const tables = await pool.query(`
      SELECT table_schema, table_name 
      FROM information_schema.tables 
      WHERE table_name LIKE '%sensor%' OR table_name LIKE '%water%' OR table_name LIKE '%moisture%'
      ORDER BY table_schema, table_name
    `);
    console.log('\nSensor-related tables:');
    tables.rows.forEach(row => console.log('  -', `${row.table_schema}.${row.table_name}`));
    
  } catch (error) {
    console.error('❌ Connection failed:', error.message);
  } finally {
    await pool.end();
  }
}

testConnection();
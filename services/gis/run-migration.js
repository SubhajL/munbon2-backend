require('dotenv').config();
const { Client } = require('pg');
const fs = require('fs');

async function runMigration() {
  const client = new Client({
    connectionString: process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/munbon_dev'
  });

  try {
    await client.connect();
    console.log('Connected to database');
    
    // Read SQL file
    const sql = fs.readFileSync('add-properties-column.sql', 'utf8');
    
    // Run migration
    await client.query(sql);
    console.log('✓ Migration completed successfully');
    console.log('✓ Properties column added to agricultural_plots table');
    
  } catch (error) {
    console.error('Error running migration:', error.message);
  } finally {
    await client.end();
  }
}

runMigration();
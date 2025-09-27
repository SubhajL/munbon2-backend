#!/usr/bin/env node

const { Client } = require('pg');

async function testConnection() {
  console.log('Testing database connection methods...\n');
  
  // Test 1: With empty string password
  console.log('Test 1: Empty string password');
  try {
    const client1 = new Client({
      host: '127.0.0.1',
      port: 5432,
      database: 'munbon_dev',
      user: 'postgres',
      password: ''
    });
    await client1.connect();
    const result = await client1.query('SELECT NOW()');
    console.log('✓ Success with empty password:', result.rows[0].now);
    await client1.end();
  } catch (error) {
    console.log('✗ Failed:', error.message);
  }

  // Test 2: With no password field
  console.log('\nTest 2: No password field');
  try {
    const client2 = new Client({
      host: '127.0.0.1',
      port: 5432,
      database: 'munbon_dev',
      user: 'postgres'
    });
    await client2.connect();
    const result = await client2.query('SELECT NOW()');
    console.log('✓ Success without password:', result.rows[0].now);
    await client2.end();
  } catch (error) {
    console.log('✗ Failed:', error.message);
  }

  // Test 3: Connection string without password
  console.log('\nTest 3: Connection string without password');
  try {
    const client3 = new Client({
      connectionString: 'postgresql://postgres@127.0.0.1:5432/munbon_dev'
    });
    await client3.connect();
    const result = await client3.query('SELECT NOW()');
    console.log('✓ Success with connection string:', result.rows[0].now);
    await client3.end();
  } catch (error) {
    console.log('✗ Failed:', error.message);
  }

  // Test 4: Using PGPASSWORD environment variable
  console.log('\nTest 4: Using PGPASSWORD environment');
  try {
    process.env.PGPASSWORD = '';
    const client4 = new Client({
      host: '127.0.0.1',
      port: 5432,
      database: 'munbon_dev',
      user: 'postgres'
    });
    await client4.connect();
    const result = await client4.query('SELECT NOW()');
    console.log('✓ Success with PGPASSWORD:', result.rows[0].now);
    await client4.end();
  } catch (error) {
    console.log('✗ Failed:', error.message);
  }
}

testConnection().then(() => {
  console.log('\nConnection tests completed.');
  process.exit(0);
}).catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
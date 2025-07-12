const sql = require('mssql');

// MSSQL connection configuration
const config = {
  server: 'RID-SCADA01\\SCADA', // or use IP address if this doesn't work
  database: 'Scada2024',
  user: 'sa',
  password: 'bangkok1234',
  options: {
    encrypt: false, // For local SQL Server
    trustServerCertificate: true,
    enableArithAbort: true
  }
};

async function testConnection() {
  try {
    console.log('Connecting to MSSQL Server...');
    await sql.connect(config);
    console.log('✅ Connected to MSSQL!');

    // Test query to understand the data structure
    console.log('\n1. Checking MoonBonLive table structure:');
    const columns = await sql.query`
      SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_NAME = 'MoonBonLive'
      ORDER BY ORDINAL_POSITION
    `;
    console.table(columns.recordset);

    // Get sample data
    console.log('\n2. Sample data from MoonBonLive:');
    const sampleData = await sql.query`
      SELECT TOP 10 DateTime, TagIndex, Val
      FROM MoonBonLive
      ORDER BY DateTime DESC
    `;
    console.table(sampleData.recordset);

    // Get unique TagIndex values to understand what each represents
    console.log('\n3. Unique TagIndex values (sensor types):');
    const tagIndexes = await sql.query`
      SELECT DISTINCT TagIndex, COUNT(*) as RecordCount
      FROM MoonBonLive
      GROUP BY TagIndex
      ORDER BY TagIndex
    `;
    console.table(tagIndexes.recordset);

    // Get latest reading for each TagIndex
    console.log('\n4. Latest reading for each TagIndex:');
    const latestReadings = await sql.query`
      SELECT m1.TagIndex, m1.DateTime, m1.Val
      FROM MoonBonLive m1
      INNER JOIN (
        SELECT TagIndex, MAX(DateTime) as MaxDateTime
        FROM MoonBonLive
        GROUP BY TagIndex
      ) m2 ON m1.TagIndex = m2.TagIndex AND m1.DateTime = m2.MaxDateTime
      ORDER BY m1.TagIndex
    `;
    console.table(latestReadings.recordset);

    // Check if there's a tag mapping table
    console.log('\n5. Looking for tag mapping tables:');
    const tables = await sql.query`
      SELECT TABLE_NAME
      FROM INFORMATION_SCHEMA.TABLES
      WHERE TABLE_TYPE = 'BASE TABLE'
      AND TABLE_NAME LIKE '%Tag%' OR TABLE_NAME LIKE '%Sensor%' OR TABLE_NAME LIKE '%AOS%'
      ORDER BY TABLE_NAME
    `;
    console.log('Related tables:', tables.recordset.map(t => t.TABLE_NAME));

    await sql.close();
    console.log('\n✅ Connection closed successfully');
  } catch (err) {
    console.error('Error:', err);
  }
}

testConnection();
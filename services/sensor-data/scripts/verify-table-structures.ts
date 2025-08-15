import { Client } from 'pg';
import * as dotenv from 'dotenv';
import * as path from 'path';

// Load default .env
dotenv.config();

// Load EC2 specific env vars
dotenv.config({ path: path.join(__dirname, '..', '.env.ec2') });

interface ColumnInfo {
  column_name: string;
  data_type: string;
  is_nullable: string;
  column_default: string | null;
  numeric_precision: number | null;
  numeric_scale: number | null;
  character_maximum_length: number | null;
}

interface TableComparison {
  tableName: string;
  localColumns: ColumnInfo[];
  ec2Columns: ColumnInfo[];
  differences: string[];
}

async function getTableStructure(client: Client, tableName: string): Promise<ColumnInfo[]> {
  const query = `
    SELECT 
      column_name,
      data_type,
      is_nullable,
      column_default,
      numeric_precision,
      numeric_scale,
      character_maximum_length
    FROM information_schema.columns
    WHERE table_schema = 'public' 
      AND table_name = $1
    ORDER BY ordinal_position;
  `;
  
  const result = await client.query(query, [tableName]);
  return result.rows;
}

async function compareTableStructures(table: string): Promise<TableComparison> {
  // Local database connection
  const localClient = new Client({
    host: 'localhost',
    port: 5433,
    database: 'munbon_timescale',
    user: 'postgres',
    password: 'postgres'
  });

  // EC2 database connection
  const ec2Client = new Client({
    host: process.env.EC2_DB_HOST || '43.209.22.250',
    port: parseInt(process.env.EC2_DB_PORT || '5432'),
    database: process.env.EC2_DB_NAME || 'sensor_data',
    user: process.env.EC2_DB_USER || 'postgres',
    password: process.env.EC2_DB_PASSWORD || 'postgres'
  });

  try {
    await localClient.connect();
    await ec2Client.connect();

    const localColumns = await getTableStructure(localClient, table);
    const ec2Columns = await getTableStructure(ec2Client, table);

    const differences: string[] = [];

    // Check if column counts match
    if (localColumns.length !== ec2Columns.length) {
      differences.push(`Column count mismatch: Local has ${localColumns.length}, EC2 has ${ec2Columns.length}`);
    }

    // Compare each column
    for (let i = 0; i < Math.max(localColumns.length, ec2Columns.length); i++) {
      const localCol = localColumns[i];
      const ec2Col = ec2Columns[i];

      if (!localCol && ec2Col) {
        differences.push(`Missing in local: ${ec2Col.column_name}`);
        continue;
      }
      if (localCol && !ec2Col) {
        differences.push(`Missing in EC2: ${localCol.column_name}`);
        continue;
      }

      if (localCol && ec2Col) {
        // Compare column properties
        if (localCol.column_name !== ec2Col.column_name) {
          differences.push(`Column name mismatch at position ${i + 1}: Local='${localCol.column_name}', EC2='${ec2Col.column_name}'`);
        }
        if (localCol.data_type !== ec2Col.data_type) {
          differences.push(`Data type mismatch for ${localCol.column_name}: Local='${localCol.data_type}', EC2='${ec2Col.data_type}'`);
        }
        if (localCol.is_nullable !== ec2Col.is_nullable) {
          differences.push(`Nullable mismatch for ${localCol.column_name}: Local='${localCol.is_nullable}', EC2='${ec2Col.is_nullable}'`);
        }
        if (localCol.numeric_precision !== ec2Col.numeric_precision || localCol.numeric_scale !== ec2Col.numeric_scale) {
          differences.push(`Numeric precision/scale mismatch for ${localCol.column_name}: Local=(${localCol.numeric_precision},${localCol.numeric_scale}), EC2=(${ec2Col.numeric_precision},${ec2Col.numeric_scale})`);
        }
      }
    }

    return {
      tableName: table,
      localColumns,
      ec2Columns,
      differences
    };
  } finally {
    await localClient.end();
    await ec2Client.end();
  }
}

async function checkHypertableConfiguration(table: string): Promise<string[]> {
  const differences: string[] = [];
  
  // Local database connection
  const localClient = new Client({
    host: 'localhost',
    port: 5433,
    database: 'munbon_timescale',
    user: 'postgres',
    password: 'postgres'
  });

  // EC2 database connection
  const ec2Client = new Client({
    host: process.env.EC2_DB_HOST || '43.209.22.250',
    port: parseInt(process.env.EC2_DB_PORT || '5432'),
    database: process.env.EC2_DB_NAME || 'sensor_data',
    user: process.env.EC2_DB_USER || 'postgres',
    password: process.env.EC2_DB_PASSWORD || 'postgres'
  });

  try {
    await localClient.connect();
    await ec2Client.connect();

    const hypertableQuery = `
      SELECT 
        h.table_name,
        h.num_dimensions,
        d.column_name,
        d.interval_length::text
      FROM _timescaledb_catalog.hypertable h
      JOIN _timescaledb_catalog.dimension d ON h.id = d.hypertable_id
      WHERE h.schema_name = 'public' AND h.table_name = $1;
    `;

    const localHypertable = await localClient.query(hypertableQuery, [table]);
    const ec2Hypertable = await ec2Client.query(hypertableQuery, [table]);

    if (localHypertable.rows.length === 0 && ec2Hypertable.rows.length === 0) {
      differences.push(`${table} is not a hypertable in either database`);
    } else if (localHypertable.rows.length === 0) {
      differences.push(`${table} is not a hypertable in local database`);
    } else if (ec2Hypertable.rows.length === 0) {
      differences.push(`${table} is not a hypertable in EC2 database`);
    } else {
      const local = localHypertable.rows[0];
      const ec2 = ec2Hypertable.rows[0];
      
      if (local.interval_length !== ec2.interval_length) {
        differences.push(`Hypertable chunk interval mismatch for ${table}: Local='${local.interval_length}', EC2='${ec2.interval_length}'`);
      }
    }

    return differences;
  } finally {
    await localClient.end();
    await ec2Client.end();
  }
}

async function main() {
  console.log('🔍 Verifying table structures between Local and EC2 databases...\n');

  const tables = ['water_level_readings', 'moisture_readings', 'sensor_registry'];
  let hasErrors = false;

  for (const table of tables) {
    console.log(`\n📊 Checking table: ${table}`);
    console.log('=' .repeat(50));
    
    try {
      const comparison = await compareTableStructures(table);
      
      if (comparison.differences.length === 0) {
        console.log('✅ Table structure matches perfectly!');
      } else {
        console.log('❌ Found differences:');
        comparison.differences.forEach(diff => console.log(`   - ${diff}`));
        hasErrors = true;
      }

      // Check hypertable configuration
      const hypertableDiffs = await checkHypertableConfiguration(table);
      if (hypertableDiffs.length > 0) {
        console.log('\n⚠️  Hypertable configuration issues:');
        hypertableDiffs.forEach(diff => console.log(`   - ${diff}`));
        hasErrors = true;
      }

      // Print column details for reference
      console.log('\n📋 Column Details:');
      console.log('Local columns:');
      comparison.localColumns.forEach(col => {
        console.log(`   - ${col.column_name}: ${col.data_type}${col.is_nullable === 'NO' ? ' NOT NULL' : ''}`);
      });

    } catch (error) {
      console.error(`❌ Error checking ${table}:`, error);
      hasErrors = true;
    }
  }

  console.log('\n' + '='.repeat(50));
  if (hasErrors) {
    console.log('❌ Schema verification failed! Please fix the differences before proceeding.');
    process.exit(1);
  } else {
    console.log('✅ All table structures match! Safe to proceed with dual-write implementation.');
  }
}

// Run the verification
main().catch(console.error);
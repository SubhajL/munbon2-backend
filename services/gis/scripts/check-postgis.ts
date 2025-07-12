#!/usr/bin/env ts-node

import { AppDataSource } from '../src/config/database';

async function checkPostGIS() {
  try {
    console.log('Connecting to database...');
    await AppDataSource.initialize();
    
    // Check if PostGIS extension exists
    const extensionCheck = await AppDataSource.query(`
      SELECT 
        extname,
        extversion
      FROM pg_extension 
      WHERE extname IN ('postgis', 'postgis_topology', 'postgis_raster')
    `);
    
    if (extensionCheck.length === 0) {
      console.log('\n❌ PostGIS is NOT installed');
      console.log('\nTo install PostGIS, run:');
      console.log('  CREATE EXTENSION postgis;');
      console.log('  CREATE EXTENSION postgis_topology;');
    } else {
      console.log('\n✅ PostGIS is installed:');
      extensionCheck.forEach((ext: any) => {
        console.log(`  - ${ext.extname} version ${ext.extversion}`);
      });
      
      // Get PostGIS full version info
      try {
        const versionInfo = await AppDataSource.query('SELECT PostGIS_Full_Version()');
        console.log('\nPostGIS Full Version Info:');
        console.log(versionInfo[0].postgis_full_version);
      } catch (error) {
        // Ignore if function doesn't exist
      }
    }
    
    // Check table status
    const schema = process.env.GIS_DATABASE_SCHEMA || 'gis';
    console.log(`\nChecking tables in schema '${schema}':`);
    
    const tables = await AppDataSource.query(`
      SELECT 
        table_name,
        EXISTS (
          SELECT 1 FROM information_schema.columns 
          WHERE table_schema = $1 
          AND table_name = t.table_name 
          AND udt_name = 'geometry'
        ) as has_geometry
      FROM information_schema.tables t
      WHERE table_schema = $1
      AND table_type = 'BASE TABLE'
      ORDER BY table_name
    `, [schema]);
    
    tables.forEach((table: any) => {
      const geoIcon = table.has_geometry ? '🌍' : '📄';
      console.log(`  ${geoIcon} ${table.table_name}${table.has_geometry ? ' (has geometry)' : ''}`);
    });
    
    // Check data counts
    console.log('\nData counts:');
    try {
      const simpleCount = await AppDataSource.query(`SELECT COUNT(*) as count FROM ${schema}.parcels_simple`);
      console.log(`  - parcels_simple: ${simpleCount[0]?.count || 0} records`);
    } catch (error) {
      console.log('  - parcels_simple: table not found');
    }
    
    try {
      const parcelCount = await AppDataSource.query(`SELECT COUNT(*) as count FROM ${schema}.parcels`);
      console.log(`  - parcels: ${parcelCount[0]?.count || 0} records`);
    } catch (error) {
      console.log('  - parcels: table not found');
    }
    
  } catch (error) {
    console.error('Error checking PostGIS:', error);
  } finally {
    await AppDataSource.destroy();
  }
}

// Run the check
checkPostGIS();
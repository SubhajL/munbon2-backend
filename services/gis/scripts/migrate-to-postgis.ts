#!/usr/bin/env ts-node

import { AppDataSource } from '../src/config/database';
import { logger } from '../src/utils/logger';

async function runMigration() {
  try {
    console.log('Initializing database connection...');
    await AppDataSource.initialize();
    
    console.log('Running migrations...');
    await AppDataSource.runMigrations();
    
    console.log('Migrations completed successfully');
    
    // Verify PostGIS is working
    const postgisVersion = await AppDataSource.query('SELECT PostGIS_Version()');
    console.log('PostGIS Version:', postgisVersion[0]?.postgis_version || 'Not installed');
    
    // Check parcel counts
    const schema = process.env.GIS_DATABASE_SCHEMA || 'gis';
    const parcelSimpleCount = await AppDataSource.query(`
      SELECT COUNT(*) as count FROM ${schema}.parcels_simple
    `);
    const parcelCount = await AppDataSource.query(`
      SELECT COUNT(*) as count FROM ${schema}.parcels
    `);
    
    console.log('Parcels in parcels_simple:', parcelSimpleCount[0]?.count || 0);
    console.log('Parcels in parcels (PostGIS):', parcelCount[0]?.count || 0);
    
  } catch (error) {
    console.error('Migration failed:', error);
    process.exit(1);
  } finally {
    await AppDataSource.destroy();
  }
}

// Run the migration
runMigration();
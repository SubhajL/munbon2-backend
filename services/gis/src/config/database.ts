import { DataSource } from 'typeorm';
import { config } from './index';
import { Zone } from '../models/zone.entity';
import { Parcel } from '../models/parcel.entity';
import { Canal } from '../models/canal.entity';
import { Gate } from '../models/gate.entity';
import { Pump } from '../models/pump.entity';
import { WaterSource } from '../models/water-source.entity';
import { IrrigationBlock } from '../models/irrigation-block.entity';
import { SpatialIndex } from '../models/spatial-index.entity';
import { ShapeFileUpload } from '../models/shape-file-upload.entity';
import { ParcelSimple } from '../models/parcel-simple.entity';

export const AppDataSource = new DataSource({
  type: 'postgres',
  url: config.database.url,
  ssl: config.database.ssl ? { rejectUnauthorized: false } : false,
  synchronize: false, // We'll handle this manually after creating schema
  logging: config.database.enableQueryLogging,
  entities: [
    // PostGIS entities - will be enabled after PostGIS is installed
    Zone,
    Parcel,
    Canal,
    Gate,
    Pump,
    WaterSource,
    IrrigationBlock,
    SpatialIndex,
    ShapeFileUpload,
    ParcelSimple, // Keep for migration purposes
  ],
  migrations: ['src/migrations/*.ts'],
  subscribers: ['src/subscribers/*.ts'],
  schema: config.database.gisSchema,
  poolSize: config.database.poolSize,
  extra: {
    max: config.database.poolSize,
    idleTimeoutMillis: config.database.poolIdleTimeout,
    connectionTimeoutMillis: 2000,
  },
});

export async function connectDatabase(): Promise<void> {
  try {
    console.log('Connecting to database with URL:', config.database.url?.replace(/:[^:]*@/, ':****@'));
    console.log('Database config:', {
      ssl: config.database.ssl,
      schema: config.database.gisSchema,
      poolSize: config.database.poolSize
    });
    
    await AppDataSource.initialize();
    console.log('Database connection initialized');
    
    // Create schema if it doesn't exist
    await AppDataSource.query(`CREATE SCHEMA IF NOT EXISTS ${config.database.gisSchema}`);
    console.log('Schema created/verified');
    
    // Enable PostGIS extension
    try {
      await AppDataSource.query('CREATE EXTENSION IF NOT EXISTS postgis');
      await AppDataSource.query('CREATE EXTENSION IF NOT EXISTS postgis_topology');
      console.log('PostGIS extensions enabled');
    } catch (error) {
      console.warn('PostGIS not available, continuing without spatial support');
      // Continue without PostGIS for now
    }
    
    // Set search path
    await AppDataSource.query(`SET search_path TO ${config.database.gisSchema}, public`);
    
    // Now synchronize the schema
    if (config.env === 'development') {
      console.log('Synchronizing database schema...');
      // Temporarily disable synchronization due to view conflicts
      // await AppDataSource.synchronize();
      console.log('Database schema synchronization skipped');
    }
    
    // Run any pending migrations in production
    if (config.env === 'production') {
      await AppDataSource.runMigrations();
    }
    
    // Create spatial indexes if PostGIS is available
    try {
      await createSpatialIndexes();
    } catch (error) {
      console.warn('Could not create spatial indexes:', error);
    }
    
  } catch (error) {
    console.error('Database connection error:', error);
    throw new Error(`Database connection failed: ${error}`);
  }
}

async function createSpatialIndexes(): Promise<void> {
  const queries = [
    // Zone spatial indexes
    `CREATE INDEX IF NOT EXISTS idx_zones_boundary ON ${config.database.gisSchema}.irrigation_zones USING GIST (boundary)`,
    
    // Agricultural plots spatial indexes
    `CREATE INDEX IF NOT EXISTS idx_plots_boundary ON ${config.database.gisSchema}.agricultural_plots USING GIST (boundary)`,
    
    // Canal spatial indexes
    `CREATE INDEX IF NOT EXISTS idx_canals_geometry ON ${config.database.gisSchema}.canal_network USING GIST (geometry)`,
    
    // Control structures spatial indexes (gates, pumps, etc.)
    `CREATE INDEX IF NOT EXISTS idx_control_structures_location ON ${config.database.gisSchema}.control_structures USING GIST (location)`,
  ];
  
  for (const query of queries) {
    try {
      await AppDataSource.query(query);
    } catch (error) {
      console.error(`Failed to create spatial index: ${error}`);
    }
  }
}
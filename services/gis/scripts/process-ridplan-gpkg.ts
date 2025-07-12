#!/usr/bin/env ts-node

import * as path from 'path';
import { config } from 'dotenv';
import { AppDataSource } from '../src/config/database';
import { Parcel } from '../src/models/parcel.entity';
import { logger } from '../src/utils/logger';
import Database from 'better-sqlite3';
import { v4 as uuidv4 } from 'uuid';

// Load environment variables
config({ path: path.join(__dirname, '../.env') });

interface RidPlanRow {
  fid: number;
  geom: Buffer;
  OBJECTID: number;
  PARCEL_SEQ: string;
  PARCELDESC: string;
  AMPHOE_T: string;
  TAM_NAM_T: string;
  file_name: string;
  lat: number;
  lon: number;
  area: number;
  member: string;
  sub_member: string;
  parcel_area_rai: number;
  data_date_process: number;
  start_int: number;
  wpet: number;
  age: number;
  stage_age: number;
  wprod: number;
  plant_id: string;
  yield_at_mc_kgpr: number;
  season_irri_m3_per_rai: number;
  auto_note: string;
}

async function processRidPlanGeoPackage(filePath: string) {
  try {
    // Initialize database connection
    if (!AppDataSource.isInitialized) {
      await AppDataSource.initialize();
      logger.info('Database connection established');
    }

    const parcelRepository = AppDataSource.getRepository(Parcel);
    
    // Open GeoPackage with better-sqlite3
    logger.info('Opening GeoPackage file', { filePath });
    const db = new Database(filePath, { readonly: true });
    
    // Get total count
    const countResult = db.prepare('SELECT COUNT(*) as count FROM ridplan_rice_20250702').get() as { count: number };
    const totalFeatures = countResult.count;
    logger.info(`Found ${totalFeatures} features to process`);
    
    // Process in batches
    const batchSize = 100;
    let processedCount = 0;
    let savedCount = 0;
    let errors: string[] = [];
    
    // Prepare statement for reading data
    const stmt = db.prepare(`
      SELECT 
        fid, OBJECTID, PARCEL_SEQ, PARCELDESC, 
        AMPHOE_T, TAM_NAM_T, file_name,
        lat, lon, area, member, sub_member,
        parcel_area_rai, data_date_process, start_int,
        wpet, age, stage_age, wprod, plant_id,
        yield_at_mc_kgpr, season_irri_m3_per_rai, auto_note,
        AsText(geom) as geom_wkt
      FROM ridplan_rice_20250702
      LIMIT ? OFFSET ?
    `);
    
    // Get default zone ID (Zone 1)
    let defaultZoneId: string;
    try {
      const zoneResult = await AppDataSource.query(`
        SELECT id FROM gis.irrigation_zones 
        WHERE zone_code = 'Z001' 
        LIMIT 1
      `);
      defaultZoneId = zoneResult[0]?.id;
      
      if (!defaultZoneId) {
        // Create default zone if it doesn't exist
        const newZone = await AppDataSource.query(`
          INSERT INTO gis.irrigation_zones (zone_code, zone_name, zone_type, boundary)
          VALUES ('Z001', 'Zone 1', 'irrigation', ST_GeomFromText('POLYGON((102 14, 103 14, 103 15, 102 15, 102 14))', 4326))
          RETURNING id
        `);
        defaultZoneId = newZone[0].id;
      }
    } catch (error) {
      logger.error('Error getting default zone', { error });
      throw error;
    }
    
    logger.info('Using default zone', { zoneId: defaultZoneId });
    
    // Process in batches
    for (let offset = 0; offset < totalFeatures; offset += batchSize) {
      const rows = stmt.all(batchSize, offset) as any[];
      const parcelsToSave: Partial<Parcel>[] = [];
      
      for (const row of rows) {
        try {
          // Create point geometry from lat/lon
          const pointWkt = `POINT(${row.lon} ${row.lat})`;
          
          // Convert area from sq meters to hectares
          const areaHectares = row.area / 10000;
          
          const parcel: Partial<Parcel> = {
            id: uuidv4(),
            plotCode: row.PARCEL_SEQ || `RID-${row.fid}`,
            farmerId: row.member || 'unknown',
            zoneId: defaultZoneId,
            areaHectares: areaHectares,
            boundary: pointWkt as any, // Will be converted by PostGIS
            currentCropType: row.plant_id || 'rice',
            soilType: 'unknown',
            properties: {
              uploadId: `ridplan-import-${Date.now()}`,
              ridAttributes: {
                parcelAreaRai: row.parcel_area_rai,
                dataDateProcess: new Date(row.data_date_process * 1000), // Convert from Unix timestamp
                startInt: new Date(row.start_int * 1000),
                wpet: row.wpet,
                age: row.age,
                wprod: row.wprod,
                plantId: row.plant_id,
                yieldAtMcKgpr: row.yield_at_mc_kgpr,
                seasonIrrM3PerRai: row.season_irri_m3_per_rai,
                autoNote: row.auto_note,
              },
              lastUpdated: new Date(),
            } as any
          };
          
          parcelsToSave.push(parcel);
        } catch (error) {
          errors.push(`Error processing feature ${row.fid}: ${error}`);
        }
      }
      
      // Save batch to database
      if (parcelsToSave.length > 0) {
        try {
          // Use raw query to insert with ST_GeomFromText
          for (const parcel of parcelsToSave) {
            await AppDataSource.query(`
              INSERT INTO gis.agricultural_plots (
                id, plot_code, farmer_id, zone_id, area_hectares, 
                boundary, current_crop_type, soil_type, properties
              ) VALUES (
                $1, $2, $3, $4, $5,
                ST_GeomFromText($6, 4326), $7, $8, $9
              )
              ON CONFLICT (plot_code) DO UPDATE SET
                area_hectares = EXCLUDED.area_hectares,
                boundary = EXCLUDED.boundary,
                properties = EXCLUDED.properties,
                updated_at = NOW()
            `, [
              parcel.id,
              parcel.plotCode,
              parcel.farmerId,
              parcel.zoneId,
              parcel.areaHectares,
              parcel.boundary,
              parcel.currentCropType,
              parcel.soilType,
              JSON.stringify(parcel.properties)
            ]);
            savedCount++;
          }
          
          logger.info(`Saved batch: ${parcelsToSave.length} parcels`);
        } catch (saveError) {
          logger.error('Error saving batch', { saveError });
          errors.push(`Error saving batch at offset ${offset}: ${saveError}`);
        }
      }
      
      processedCount += rows.length;
      
      // Log progress
      if (processedCount % 1000 === 0) {
        const progress = ((processedCount / totalFeatures) * 100).toFixed(1);
        logger.info(`Progress: ${processedCount}/${totalFeatures} (${progress}%)`);
      }
    }
    
    // Close SQLite database
    db.close();
    
    // Final summary
    console.log('\n=== Import Summary ===');
    console.log(`File: ${path.basename(filePath)}`);
    console.log(`Total features: ${totalFeatures}`);
    console.log(`Processed: ${processedCount}`);
    console.log(`Saved: ${savedCount}`);
    console.log(`Errors: ${errors.length}`);
    
    if (errors.length > 0) {
      console.log('\nFirst 10 errors:');
      errors.slice(0, 10).forEach(err => console.log(`  - ${err}`));
    }
    
  } catch (error) {
    logger.error('Failed to process GeoPackage', { error });
    console.error('\nError:', error);
    process.exit(1);
  } finally {
    // Close database connection
    if (AppDataSource.isInitialized) {
      await AppDataSource.destroy();
    }
  }
}

// Main execution
const args = process.argv.slice(2);
if (args.length === 0) {
  console.log('Usage: npm run process:ridplan <path-to-gpkg-file>');
  console.log('Example: npm run process:ridplan /path/to/ridplan_rice_20250702.gpkg');
  process.exit(1);
}

const filePath = args[0];
if (!filePath.endsWith('.gpkg')) {
  console.error('Error: File must be a GeoPackage (.gpkg) file');
  process.exit(1);
}

// Run the processing
processRidPlanGeoPackage(filePath).catch(console.error);
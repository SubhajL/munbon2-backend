#!/usr/bin/env ts-node

import * as path from 'path';
import * as fs from 'fs/promises';
import { config } from 'dotenv';
import { AppDataSource } from '../src/config/database';
import { logger } from '../src/utils/logger';
const initSqlJs = require('sql.js');
import { v4 as uuidv4 } from 'uuid';

// Load environment variables
config({ path: path.join(__dirname, '../.env') });

async function processRidPlanGeoPackage(filePath: string) {
  try {
    // Initialize database connection
    if (!AppDataSource.isInitialized) {
      await AppDataSource.initialize();
      logger.info('Database connection established');
    }

    // Read GeoPackage file
    const fileBuffer = await fs.readFile(filePath);
    
    // Initialize SQL.js
    const SQL = await initSqlJs({
      locateFile: (file: string) => `https://sql.js.org/dist/${file}`
    });
    
    // Open database
    const db = new SQL.Database(fileBuffer);
    
    logger.info('Opening GeoPackage file', { filePath });
    
    // Get total count
    const countResult = db.exec('SELECT COUNT(*) as count FROM ridplan_rice_20250702');
    const totalFeatures = countResult[0].values[0][0] as number;
    logger.info(`Found ${totalFeatures} features to process`);
    
    // Get default zone ID
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
          INSERT INTO gis.irrigation_zones (id, zone_code, zone_name, zone_type, boundary)
          VALUES ($1, 'Z001', 'Zone 1', 'irrigation', ST_GeomFromText('POLYGON((102 14, 103 14, 103 15, 102 15, 102 14))', 4326))
          RETURNING id
        `, [uuidv4()]);
        defaultZoneId = newZone[0].id;
      }
    } catch (error) {
      logger.error('Error getting default zone', { error });
      throw error;
    }
    
    logger.info('Using default zone', { zoneId: defaultZoneId });
    
    // Process in batches
    const batchSize = 100;
    let processedCount = 0;
    let savedCount = 0;
    let errors: string[] = [];
    
    const uploadId = `ridplan-import-${Date.now()}`;
    
    for (let offset = 0; offset < totalFeatures; offset += batchSize) {
      const result = db.exec(`
        SELECT 
          fid, PARCEL_SEQ, AMPHOE_T, TAM_NAM_T,
          lat, lon, area, parcel_area_rai,
          data_date_process, start_int, wpet, age,
          wprod, plant_id, yield_at_mc_kgpr,
          season_irri_m3_per_rai, auto_note
        FROM ridplan_rice_20250702
        LIMIT ${batchSize} OFFSET ${offset}
      `);
      
      if (result.length === 0) continue;
      
      const rows = result[0].values;
      
      for (const row of rows) {
        try {
          const parcelId = uuidv4();
          const plotCode = (row[1] as string) || `RID-${row[0]}`;
          const areaHectares = (row[6] as number) / 10000; // Convert from sq meters
          
          // Create properties JSON
          const properties = {
            uploadId,
            ridAttributes: {
              parcelAreaRai: row[7],
              dataDateProcess: row[8] ? new Date((row[8] as number) * 1000) : null,
              startInt: row[9] ? new Date((row[9] as number) * 1000) : null,
              wpet: row[10],
              age: row[11],
              wprod: row[12],
              plantId: row[13],
              yieldAtMcKgpr: row[14],
              seasonIrrM3PerRai: row[15],
              autoNote: row[16]
            },
            location: {
              amphoe: row[2],
              tambon: row[3],
              lat: row[4],
              lon: row[5]
            },
            lastUpdated: new Date()
          };
          
          // Insert into PostGIS
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
            parcelId,
            plotCode,
            'unknown', // farmer_id
            defaultZoneId,
            areaHectares,
            `POINT(${row[5]} ${row[4]})`, // lon, lat
            (row[13] as string) || 'rice', // crop type
            'unknown', // soil type
            JSON.stringify(properties)
          ]);
          
          savedCount++;
        } catch (error) {
          errors.push(`Error processing FID ${row[0]}: ${error}`);
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
  console.log('Usage: npm run process:ridplan:sqljs <path-to-gpkg-file>');
  console.log('Example: npm run process:ridplan:sqljs /path/to/ridplan_rice_20250702.gpkg');
  process.exit(1);
}

const filePath = args[0];
if (!filePath.endsWith('.gpkg')) {
  console.error('Error: File must be a GeoPackage (.gpkg) file');
  process.exit(1);
}

// Run the processing
processRidPlanGeoPackage(filePath).catch(console.error);
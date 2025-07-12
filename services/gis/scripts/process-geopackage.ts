#!/usr/bin/env ts-node

import * as path from 'path';
import { config } from 'dotenv';
import { AppDataSource } from '../src/config/database';
import { GeoPackageProcessor } from '../src/services/geopackage-processor';
import { logger } from '../src/utils/logger';

// Load environment variables
config({ path: path.join(__dirname, '../.env') });

async function processGeoPackageFile(filePath: string) {
  try {
    // Initialize database connection
    if (!AppDataSource.isInitialized) {
      await AppDataSource.initialize();
      logger.info('Database connection established');
    }

    // Create processor instance
    const processor = new GeoPackageProcessor();
    
    // Generate upload ID
    const uploadId = `manual-${Date.now()}`;
    
    logger.info('Starting GeoPackage processing', { filePath, uploadId });
    
    // Process the file
    const results = await processor.processGeoPackageFile(filePath, uploadId);
    
    // Log processing results
    logger.info('Processing complete', {
      tables: results.map(r => ({
        tableName: r.metadata.tableName,
        totalFeatures: r.metadata.totalFeatures,
        processedFeatures: r.metadata.processedFeatures,
        failedFeatures: r.metadata.failedFeatures,
        sourceSRS: r.metadata.sourceSRS
      }))
    });
    
    // Save to database
    logger.info('Saving results to database...');
    const saveResults = await processor.saveProcessingResults(results);
    
    logger.info('Database save complete', {
      totalParcels: saveResults.totalParcels,
      totalZones: saveResults.totalZones,
      errors: saveResults.errors
    });
    
    // Summary
    console.log('\n=== Processing Summary ===');
    console.log(`File: ${path.basename(filePath)}`);
    console.log(`Tables processed: ${results.length}`);
    console.log(`Total parcels saved: ${saveResults.totalParcels}`);
    console.log(`Total zones saved: ${saveResults.totalZones}`);
    
    if (saveResults.errors.length > 0) {
      console.log('\nErrors encountered:');
      saveResults.errors.forEach(err => console.log(`  - ${err}`));
    }
    
    console.log('\nDetailed results by table:');
    results.forEach(result => {
      console.log(`\nTable: ${result.metadata.tableName}`);
      console.log(`  Source SRS: ${result.metadata.sourceSRS || 'Unknown'}`);
      console.log(`  Total features: ${result.metadata.totalFeatures}`);
      console.log(`  Processed: ${result.metadata.processedFeatures}`);
      console.log(`  Failed: ${result.metadata.failedFeatures}`);
      console.log(`  Parcels: ${result.parcels.length}`);
      console.log(`  Zones: ${result.zones.length}`);
    });
    
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
  console.log('Usage: npm run process:geopackage <path-to-gpkg-file>');
  console.log('Example: npm run process:geopackage /path/to/ridplan_rice_20250702.gpkg');
  process.exit(1);
}

const filePath = args[0];
if (!filePath.endsWith('.gpkg')) {
  console.error('Error: File must be a GeoPackage (.gpkg) file');
  process.exit(1);
}

// Run the processing
processGeoPackageFile(filePath).catch(console.error);
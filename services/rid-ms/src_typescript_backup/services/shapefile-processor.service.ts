import * as fs from 'fs/promises';
import * as path from 'path';
import AdmZip from 'adm-zip';
import { open as openShapefile } from 'shapefile';
import { DBFFile } from 'dbffile';
import proj4 from 'proj4';
import * as turf from '@turf/turf';
import { Feature, FeatureCollection, Polygon, MultiPolygon } from 'geojson';
import { v4 as uuidv4 } from 'uuid';
import { logger } from '../utils/logger';
import { config } from '../config';
import { ShapeFileMetadata, ParcelData, ProcessingResult, ProcessingError } from '../types';
import { DatabaseService } from './database.service';
import { KafkaService } from './kafka.service';

export class ShapeFileProcessorService {
  private static instance: ShapeFileProcessorService;
  private databaseService: DatabaseService;
  private kafkaService: KafkaService;

  private constructor() {
    this.databaseService = DatabaseService.getInstance();
    this.kafkaService = KafkaService.getInstance();
  }

  public static getInstance(): ShapeFileProcessorService {
    if (!ShapeFileProcessorService.instance) {
      ShapeFileProcessorService.instance = new ShapeFileProcessorService();
    }
    return ShapeFileProcessorService.instance;
  }

  /**
   * Process uploaded shape file (zip or individual files)
   */
  public async processShapeFile(
    filePath: string,
    metadata: Partial<ShapeFileMetadata>
  ): Promise<ProcessingResult> {
    const startTime = Date.now();
    const shapeFileId = uuidv4();
    const errors: ProcessingError[] = [];
    let parcelsProcessed = 0;
    let parcelsWithErrors = 0;

    try {
      // Create processing directory
      const processingDir = path.join(config.fileProcessing.processedDir, shapeFileId);
      await fs.mkdir(processingDir, { recursive: true });

      // Extract files if zip
      let shapeFilePath: string;
      if (filePath.endsWith('.zip')) {
        shapeFilePath = await this.extractZipFile(filePath, processingDir);
      } else {
        shapeFilePath = filePath;
      }

      // Update metadata
      const fullMetadata: ShapeFileMetadata = {
        id: shapeFileId,
        originalFileName: metadata.originalFileName || path.basename(filePath),
        uploadDate: new Date(),
        status: 'processing',
        fileSize: (await fs.stat(filePath)).size,
        coordinateSystem: config.waterDemand.coordinateSystem,
        ...metadata,
      };

      // Save metadata to database
      await this.databaseService.saveShapeFileMetadata(fullMetadata);

      // Read and process shape file
      const geoJson = await this.readShapeFile(shapeFilePath);
      const parcels = await this.processParcels(geoJson, shapeFileId);

      // Save parcels to database in batches
      for (let i = 0; i < parcels.length; i += config.fileProcessing.batchSize) {
        const batch = parcels.slice(i, i + config.fileProcessing.batchSize);
        try {
          await this.databaseService.saveParcels(batch);
          parcelsProcessed += batch.length;
        } catch (error) {
          parcelsWithErrors += batch.length;
          errors.push({
            errorCode: 'BATCH_SAVE_ERROR',
            message: `Failed to save batch ${i / config.fileProcessing.batchSize + 1}`,
            details: error,
          });
        }
      }

      // Update metadata with success
      fullMetadata.status = 'processed';
      fullMetadata.processedDate = new Date();
      fullMetadata.featureCount = parcels.length;
      fullMetadata.boundingBox = this.calculateBoundingBox(geoJson);
      await this.databaseService.updateShapeFileMetadata(fullMetadata);

      // Publish success event
      await this.kafkaService.publishShapeFileProcessed({
        shapeFileId,
        parcelsCount: parcels.length,
        processedAt: new Date(),
      });

      // Archive original file
      await this.archiveFile(filePath, shapeFileId);

      return {
        shapeFileId,
        success: true,
        parcelsProcessed,
        parcelsWithErrors,
        processingTime: Date.now() - startTime,
        errors: errors.length > 0 ? errors : undefined,
      };

    } catch (error) {
      logger.error('Shape file processing failed:', error);
      
      // Update metadata with failure
      await this.databaseService.updateShapeFileMetadata({
        id: shapeFileId,
        status: 'failed',
        error: error instanceof Error ? error.message : 'Unknown error',
      });

      // Publish error event
      await this.kafkaService.publishProcessingError({
        shapeFileId,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date(),
      });

      return {
        shapeFileId,
        success: false,
        parcelsProcessed,
        parcelsWithErrors,
        processingTime: Date.now() - startTime,
        errors: [
          {
            errorCode: 'PROCESSING_FAILED',
            message: error instanceof Error ? error.message : 'Unknown error',
            details: error,
          },
        ],
      };
    }
  }

  /**
   * Extract zip file to processing directory
   */
  private async extractZipFile(zipPath: string, extractDir: string): Promise<string> {
    const zip = new AdmZip(zipPath);
    zip.extractAllTo(extractDir, true);

    // Find .shp file
    const files = await fs.readdir(extractDir);
    const shpFile = files.find(f => f.toLowerCase().endsWith('.shp'));
    
    if (!shpFile) {
      throw new Error('No .shp file found in zip archive');
    }

    return path.join(extractDir, shpFile);
  }

  /**
   * Read shape file and convert to GeoJSON
   */
  private async readShapeFile(shapeFilePath: string): Promise<FeatureCollection> {
    const features: Feature[] = [];
    const source = await openShapefile(shapeFilePath);
    
    let result = await source.read();
    while (!result.done) {
      if (result.value) {
        features.push(result.value as Feature);
      }
      result = await source.read();
    }

    return {
      type: 'FeatureCollection',
      features,
    };
  }

  /**
   * Process GeoJSON features into parcels
   */
  private async processParcels(
    geoJson: FeatureCollection,
    shapeFileId: string
  ): Promise<ParcelData[]> {
    const parcels: ParcelData[] = [];

    for (const feature of geoJson.features) {
      try {
        // Only process polygon features
        if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') {
          continue;
        }

        // Transform coordinates if needed
        const transformedGeometry = this.transformCoordinates(
          feature.geometry as Polygon | MultiPolygon
        );

        // Calculate area
        const area = turf.area(transformedGeometry);

        // Extract parcel data
        const parcel: ParcelData = {
          id: uuidv4(),
          parcelId: feature.properties?.PARCEL_ID || 
                    feature.properties?.parcel_id || 
                    feature.properties?.ID || 
                    uuidv4(),
          geometry: transformedGeometry,
          area,
          zone: feature.properties?.ZONE || feature.properties?.zone,
          subZone: feature.properties?.SUBZONE || feature.properties?.subzone,
          landUseType: feature.properties?.LAND_USE || feature.properties?.land_use,
          cropType: feature.properties?.CROP_TYPE || feature.properties?.crop_type,
          owner: feature.properties?.OWNER || feature.properties?.owner,
          waterDemandMethod: this.determineWaterDemandMethod(feature.properties),
          attributes: feature.properties || {},
        };

        // Parse dates if present
        if (feature.properties?.PLANTING_DATE) {
          parcel.plantingDate = new Date(feature.properties.PLANTING_DATE);
        }
        if (feature.properties?.HARVEST_DATE) {
          parcel.harvestDate = new Date(feature.properties.HARVEST_DATE);
        }

        parcels.push(parcel);
      } catch (error) {
        logger.error(`Error processing parcel: ${error}`);
      }
    }

    return parcels;
  }

  /**
   * Transform coordinates from source CRS to WGS84
   */
  private transformCoordinates(geometry: Polygon | MultiPolygon): Polygon | MultiPolygon {
    // Define projection transformation
    const sourceProj = config.waterDemand.coordinateSystem;
    const targetProj = 'EPSG:4326'; // WGS84

    if (sourceProj === targetProj) {
      return geometry;
    }

    // Transform coordinates
    const transform = proj4(sourceProj, targetProj);

    if (geometry.type === 'Polygon') {
      return {
        type: 'Polygon',
        coordinates: geometry.coordinates.map(ring =>
          ring.map(coord => transform.forward(coord))
        ),
      };
    } else {
      return {
        type: 'MultiPolygon',
        coordinates: geometry.coordinates.map(polygon =>
          polygon.map(ring =>
            ring.map(coord => transform.forward(coord))
          )
        ),
      };
    }
  }

  /**
   * Determine water demand calculation method
   */
  private determineWaterDemandMethod(properties: any): 'RID-MS' | 'ROS' | 'AWD' {
    if (properties?.WATER_DEMAND_METHOD) {
      const method = properties.WATER_DEMAND_METHOD.toUpperCase();
      if (['RID-MS', 'ROS', 'AWD'].includes(method)) {
        return method as 'RID-MS' | 'ROS' | 'AWD';
      }
    }
    return config.waterDemand.defaultMethod as 'RID-MS' | 'ROS' | 'AWD';
  }

  /**
   * Calculate bounding box of features
   */
  private calculateBoundingBox(geoJson: FeatureCollection) {
    const bbox = turf.bbox(geoJson);
    return {
      minX: bbox[0],
      minY: bbox[1],
      maxX: bbox[2],
      maxY: bbox[3],
    };
  }

  /**
   * Archive processed file
   */
  private async archiveFile(filePath: string, shapeFileId: string): Promise<void> {
    const archivePath = path.join(
      config.fileProcessing.archiveDir,
      `${shapeFileId}_${path.basename(filePath)}`
    );
    await fs.mkdir(path.dirname(archivePath), { recursive: true });
    await fs.rename(filePath, archivePath);
  }

  /**
   * Clean up old files based on retention policy
   */
  public async cleanupOldFiles(): Promise<void> {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - config.fileProcessing.retentionDays);

    // Clean archive directory
    const archiveFiles = await fs.readdir(config.fileProcessing.archiveDir);
    for (const file of archiveFiles) {
      const filePath = path.join(config.fileProcessing.archiveDir, file);
      const stats = await fs.stat(filePath);
      if (stats.mtime < cutoffDate) {
        await fs.unlink(filePath);
        logger.info(`Deleted old archive file: ${file}`);
      }
    }

    // Clean processed directory
    const processedDirs = await fs.readdir(config.fileProcessing.processedDir);
    for (const dir of processedDirs) {
      const dirPath = path.join(config.fileProcessing.processedDir, dir);
      const stats = await fs.stat(dirPath);
      if (stats.mtime < cutoffDate) {
        await fs.rm(dirPath, { recursive: true, force: true });
        logger.info(`Deleted old processed directory: ${dir}`);
      }
    }
  }
}
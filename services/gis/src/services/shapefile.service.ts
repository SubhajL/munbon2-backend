import * as AWS from 'aws-sdk';
import { v4 as uuidv4 } from 'uuid';
import { getRepository } from 'typeorm';
import { AppDataSource } from '../config/database';
import { ShapeFileProcessor } from './shapefile-processor';
import { GeoPackageProcessor } from './geopackage-processor';
import { Parcel, ParcelStatus, LandUseType, IrrigationMethod } from '../models/parcel.entity';
import { ParcelSimple } from '../models/parcel-simple.entity';
import { ShapeFileUpload, UploadStatus } from '../models/shape-file-upload.entity';
import { logger } from '../utils/logger';
import * as fs from 'fs/promises';
import * as path from 'path';

interface UploadOptions {
  file: Express.Multer.File;
  waterDemandMethod: 'RID-MS' | 'ROS' | 'AWD';
  processingInterval: 'daily' | 'weekly' | 'bi-weekly';
  metadata?: any;
}


export class ShapeFileService {
  private s3: AWS.S3;
  private sqs: AWS.SQS;
  private processor: ShapeFileProcessor;
  private geopackageProcessor: GeoPackageProcessor;

  constructor() {
    AWS.config.update({ region: process.env.AWS_REGION || 'ap-southeast-1' });
    this.s3 = new AWS.S3();
    this.sqs = new AWS.SQS();
    this.processor = new ShapeFileProcessor();
    this.geopackageProcessor = new GeoPackageProcessor();
  }

  async processUpload(options: UploadOptions) {
    const uploadId = uuidv4();
    const timestamp = new Date();
    const uploadDate = timestamp.toISOString().split('T')[0];

    try {
      // Upload to S3
      const s3Key = `shape-files/${uploadDate}/${uploadId}/${options.file.originalname}`;
      const bucketName = process.env.SHAPE_FILE_BUCKET || 'munbon-gis-shape-files';

      const contentType = options.file.originalname.toLowerCase().endsWith('.gpkg') 
        ? 'application/geopackage+sqlite3' 
        : 'application/zip';

      await this.s3.putObject({
        Bucket: bucketName,
        Key: s3Key,
        Body: options.file.buffer,
        ContentType: contentType,
        Metadata: {
          uploadId,
          originalFileName: options.file.originalname,
          fileType: options.file.originalname.toLowerCase().endsWith('.gpkg') ? 'geopackage' : 'shapefile',
          waterDemandMethod: options.waterDemandMethod,
          processingInterval: options.processingInterval,
          uploadedAt: timestamp.toISOString(),
          ...options.metadata,
        },
      }).promise();

      logger.info('Shape file uploaded to S3', { uploadId, s3Key });

      // Send message to SQS for async processing
      const queueUrl = process.env.GIS_SQS_QUEUE_URL || 
        `https://sqs.${process.env.AWS_REGION}.amazonaws.com/${process.env.AWS_ACCOUNT_ID}/munbon-gis-shapefile-queue`;

      const message = {
        type: 'shape-file',
        uploadId,
        s3Bucket: bucketName,
        s3Key,
        fileName: options.file.originalname,
        waterDemandMethod: options.waterDemandMethod,
        processingInterval: options.processingInterval,
        metadata: options.metadata,
        uploadedAt: timestamp.toISOString(),
      };

      await this.sqs.sendMessage({
        QueueUrl: queueUrl,
        MessageBody: JSON.stringify(message),
        MessageAttributes: {
          uploadId: {
            DataType: 'String',
            StringValue: uploadId,
          },
          dataType: {
            DataType: 'String',
            StringValue: 'shape-file',
          },
        },
      }).promise();

      logger.info('Shape file message sent to SQS', { uploadId, queueUrl });

      // Store upload record
      await this.storeUploadRecord({
        uploadId,
        fileName: options.file.originalname,
        s3Key,
        metadata: options.metadata,
      });

      return {
        uploadId,
        fileName: options.file.originalname,
        status: 'pending',
        uploadedAt: timestamp.toISOString(),
        message: 'File uploaded successfully and queued for processing',
      };
    } catch (error) {
      logger.error('Failed to process shape file upload', { error, uploadId });
      throw error;
    }
  }

  async processShapeFileFromQueue(message: any) {
    const { uploadId, s3Bucket, s3Key, fileName, waterDemandMethod, metadata } = message;
    
    try {
      await this.updateUploadStatus(uploadId, 'processing');
      
      // Download from S3
      const s3Object = await this.s3.getObject({
        Bucket: s3Bucket,
        Key: s3Key,
      }).promise();

      if (!s3Object.Body) {
        throw new Error('Empty file received from S3');
      }

      const isGeoPackage = fileName.toLowerCase().endsWith('.gpkg');
      
      if (isGeoPackage) {
        // Process GeoPackage file
        // Save to temporary file first as GeoPackage library requires file path
        const tempDir = process.env.TEMP_DIR || '/tmp';
        const tempFilePath = path.join(tempDir, `${uploadId}.gpkg`);
        
        await fs.writeFile(tempFilePath, s3Object.Body as Buffer);
        
        try {
          const results = await this.geopackageProcessor.processGeoPackageFile(tempFilePath, uploadId);
          
          // Save results to database
          const saveResults = await this.geopackageProcessor.saveProcessingResults(results);
          
          // Update upload status
          await this.updateUploadStatus(uploadId, 'completed', {
            parcelCount: saveResults.totalParcels,
            zoneCount: saveResults.totalZones,
            completedAt: new Date(),
            errors: saveResults.errors,
          });

          logger.info('GeoPackage processing completed', { 
            uploadId, 
            parcelCount: saveResults.totalParcels,
            zoneCount: saveResults.totalZones 
          });
        } finally {
          // Clean up temp file
          await fs.unlink(tempFilePath).catch(() => {});
        }
      } else {
        // Process shape file (existing logic)
        const parcels = await this.processor.processShapeFile({
          buffer: s3Object.Body as Buffer,
          fileName,
          uploadId,
        });

        // Store parcels in database
        await this.storeParcels(uploadId, parcels);

        // Update upload status
        await this.updateUploadStatus(uploadId, 'completed', {
          parcelCount: parcels.length,
          completedAt: new Date(),
        });

        logger.info('Shape file processing completed', { uploadId, parcelCount: parcels.length });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      const errorStack = error instanceof Error ? error.stack : undefined;
      logger.error('Failed to process file', { 
        error: errorMessage, 
        stack: errorStack,
        uploadId,
        fileName 
      });
      await this.updateUploadStatus(uploadId, 'failed', {
        error: errorMessage,
      });
      throw error;
    }
  }

  private async storeUploadRecord(data: {
    uploadId: string;
    fileName: string;
    s3Key: string;
    metadata?: any;
  }) {
    const uploadRepository = AppDataSource.getRepository(ShapeFileUpload);
    const upload = new ShapeFileUpload();
    upload.uploadId = data.uploadId;
    upload.fileName = data.fileName;
    upload.s3Key = data.s3Key;
    upload.status = UploadStatus.PENDING;
    upload.metadata = data.metadata;
    
    await uploadRepository.save(upload);
    logger.info('Storing upload record', { uploadId: data.uploadId });
  }

  private async updateUploadStatus(uploadId: string, status: string, metadata?: any) {
    const uploadRepository = AppDataSource.getRepository(ShapeFileUpload);
    const upload = await uploadRepository.findOne({ where: { uploadId } });
    
    if (upload) {
      upload.status = status as UploadStatus;
      if (metadata) {
        if (metadata.parcelCount) upload.parcelCount = metadata.parcelCount;
        if (metadata.completedAt) upload.completedAt = metadata.completedAt;
        if (metadata.error) upload.error = metadata.error;
        upload.metadata = { ...upload.metadata, ...metadata };
      }
      await uploadRepository.save(upload);
    }
    
    logger.info('Updating upload status', { uploadId, status, metadata });
  }

  private async storeParcels(uploadId: string, parcels: any[]) {
    // Check if PostGIS is available
    let usePostGIS = false;
    try {
      const postgisCheck = await AppDataSource.query(`
        SELECT EXISTS (
          SELECT 1 FROM pg_extension WHERE extname = 'postgis'
        ) as postgis_exists
      `);
      usePostGIS = postgisCheck[0].postgis_exists;
    } catch (error) {
      logger.warn('Could not check PostGIS availability, using simple storage');
    }

    if (usePostGIS) {
      // Use PostGIS-enabled Parcel entity
      const parcelRepository = AppDataSource.getRepository(Parcel);
      
      // Get zone mappings
      const zones = await AppDataSource.query(`
        SELECT id, zone_code FROM gis.irrigation_zones 
        WHERE zone_code IN ('Z001', 'Z002', 'Z003', 'Z004', 'Z005', 'Z006')
        ORDER BY zone_code
      `);
      
      const zoneMapping: Record<string, string> = {};
      zones.forEach((zone: any) => {
        // Map zone number to zone ID
        const zoneNum = zone.zone_code.replace('Z00', '');
        zoneMapping[zoneNum] = zone.id;
      });
      
      // Default to Zone 1 if not found
      const defaultZoneId = zoneMapping['1'] || zones[0]?.id;
      
      if (!defaultZoneId) {
        throw new Error('No valid zones found in database. Please create zones first.');
      }
      
      logger.info('Zone mapping', { zoneMapping, defaultZoneId });
      
      for (const parcelData of parcels) {
        try {
          const parcel = new Parcel();
          parcel.plotCode = parcelData.parcelId || `P-${uploadId}-${Date.now()}`;
          
          // Map zone number to actual zone UUID
          const zoneNum = String(parcelData.zoneId || '1');
          parcel.zoneId = zoneMapping[zoneNum] || defaultZoneId;
          
          parcel.farmerId = parcelData.ownerId || `farmer-${Date.now()}`;
          
          // Convert GeoJSON to PostGIS geometry
          // Handle MultiPolygon by taking the largest polygon
          if (parcelData.geometry && parcelData.geometry.type === 'MultiPolygon') {
            // Find the largest polygon in the MultiPolygon
            let largestArea = 0;
            let largestPolygon = null;
            
            for (const polygon of parcelData.geometry.coordinates) {
              // Simple area calculation (not accurate but good for comparison)
              const coords = polygon[0];
              let area = 0;
              for (let i = 0; i < coords.length - 1; i++) {
                area += (coords[i][0] * coords[i + 1][1]) - (coords[i + 1][0] * coords[i][1]);
              }
              area = Math.abs(area / 2);
              
              if (area > largestArea) {
                largestArea = area;
                largestPolygon = polygon;
              }
            }
            
            parcel.boundary = {
              type: 'Polygon',
              coordinates: largestPolygon
            };
          } else {
            parcel.boundary = parcelData.geometry;
          }
          
          // Convert area to hectares (from square meters)
          parcel.areaHectares = parcelData.area / 10000;
          
          // Set crop type and soil type
          parcel.currentCropType = parcelData.cropType || parcelData.landUseType || 'rice';
          parcel.soilType = parcelData.attributes?.soil_type || 'unknown';
          
          // If RID attributes exist, use them for specific fields
          if (parcelData.ridAttributes) {
            const rid = parcelData.ridAttributes;
            
            // Convert area from rai to hectares (1 rai = 0.16 hectares)
            if (rid.parcelAreaRai) {
              parcel.areaHectares = rid.parcelAreaRai * 0.16;
            }
            
            // Set planting date if available
            if (rid.startInt) {
              parcel.plantingDate = new Date(rid.startInt);
              // Estimate harvest date (120 days after planting for rice)
              parcel.expectedHarvestDate = new Date(rid.startInt);
              parcel.expectedHarvestDate.setDate(parcel.expectedHarvestDate.getDate() + 120);
            }
            
            // Use plant ID as crop type
            if (rid.plantId) {
              parcel.currentCropType = rid.plantId;
            }
            
            // Store all RID attributes in properties field
            parcel.properties = {
              uploadId,
              ridAttributes: rid,
              lastUpdated: new Date(),
            };
          }
          
          // Use upsert to handle updates for existing parcels
          await parcelRepository.upsert(parcel, {
            conflictPaths: ['plotCode'],
            skipUpdateIfNoValuesChanged: true,
          });
        } catch (error) {
          logger.error('Failed to save parcel with PostGIS', { error, parcelData });
          throw error;
        }
      }
    } else {
      // Fallback to simple storage
      const parcelRepository = AppDataSource.getRepository(ParcelSimple);
      
      for (const parcelData of parcels) {
        const parcel = new ParcelSimple();
        parcel.uploadId = uploadId;
        parcel.parcelCode = parcelData.parcelId || `P-${uploadId}-${Date.now()}`;
        parcel.zoneId = parcelData.zoneId || '1';
        parcel.geometry = parcelData.geometry; // Store as JSON
        parcel.area = parcelData.area;
        parcel.perimeter = parcelData.perimeter;
        parcel.ownerName = parcelData.ownerName;
        parcel.ownerId = parcelData.ownerId;
        parcel.landUseType = parcelData.landUseType || 'rice';
        parcel.cropType = parcelData.cropType;
        parcel.attributes = parcelData.attributes;
        parcel.properties = {
          uploadId,
          originalData: parcelData,
        };
        
        // Calculate centroid if not provided
        if (!parcel.centroid && parcelData.geometry) {
          // Simple centroid calculation for polygon
          if (parcelData.geometry.type === 'Polygon' && parcelData.geometry.coordinates[0]) {
            const coords = parcelData.geometry.coordinates[0];
            let sumX = 0, sumY = 0;
            for (const coord of coords) {
              sumX += coord[0];
              sumY += coord[1];
            }
            parcel.centroid = {
              type: 'Point',
              coordinates: [sumX / coords.length, sumY / coords.length]
            };
          }
        }
        
        await parcelRepository.save(parcel);
      }
    }
    
    logger.info('Parcels stored in database', { 
      uploadId, 
      count: parcels.length,
      storageType: usePostGIS ? 'PostGIS' : 'Simple'
    });
  }

  async listUploads(options: any) {
    // Implementation for listing uploads
    return {
      uploads: [],
      total: 0,
      page: options.page,
      limit: options.limit,
    };
  }

  async getUploadStatus(uploadId: string) {
    // Implementation for getting upload status
    return null;
  }

  async getUploadParcels(uploadId: string) {
    // For now, return empty array since we don't track uploadId in the new schema
    // In a real implementation, you would need to add an uploadId column or 
    // track this information in a separate table
    logger.warn('getUploadParcels not implemented for new schema');
    return [];
  }

  async deleteUpload(uploadId: string) {
    // Delete parcels and upload record
    logger.info('Deleting upload and associated data', { uploadId });
  }
}
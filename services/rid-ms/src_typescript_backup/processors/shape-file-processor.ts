import * as AWS from 'aws-sdk';
import { Pool } from 'pg';
import * as fs from 'fs-extra';
import * as path from 'path';
import AdmZip from 'adm-zip';
import { open as openShapefile } from 'shapefile';
import proj4 from 'proj4';
import * as turf from '@turf/turf';
import { Feature, Polygon, MultiPolygon } from 'geojson';
import pino from 'pino';

const logger = pino({ level: 'info' });

interface SQSMessage {
  type: string;
  uploadId: string;
  s3Bucket: string;
  s3Key: string;
  fileName: string;
  waterDemandMethod: 'RID-MS' | 'ROS' | 'AWD';
  processingInterval: 'daily' | 'weekly' | 'bi-weekly';
  metadata?: any;
  uploadedAt: string;
}

interface ParsedParcel {
  parcelId: string;
  geometry: any;
  area: number;
  zone: string;
  subZone?: string;
  ownerName?: string;
  ownerId?: string;
  cropType?: string;
  landUseType?: string;
  attributes: any;
}

export class ShapeFileProcessor {
  private sqs: AWS.SQS;
  private s3: AWS.S3;
  private db: Pool;
  private isRunning: boolean = false;
  private readonly tempDir = '/tmp/shape-files';

  constructor() {
    // Initialize AWS clients
    this.sqs = new AWS.SQS({ region: process.env.AWS_REGION || 'ap-southeast-1' });
    this.s3 = new AWS.S3({ region: process.env.AWS_REGION || 'ap-southeast-1' });
    
    // Initialize database connection
    this.db = new Pool({
      connectionString: process.env.DATABASE_URL,
      max: 10,
      idleTimeoutMillis: 30000,
    });

    // Ensure temp directory exists
    fs.ensureDirSync(this.tempDir);
  }

  async start(): Promise<void> {
    logger.info('Starting Shape File Processor...');
    this.isRunning = true;

    while (this.isRunning) {
      try {
        await this.processMessages();
        // Wait 10 seconds before next poll
        await this.sleep(10000);
      } catch (error) {
        logger.error({ error }, 'Error in processing loop');
        await this.sleep(30000); // Wait longer on error
      }
    }
  }

  async stop(): Promise<void> {
    logger.info('Stopping Shape File Processor...');
    this.isRunning = false;
    await this.db.end();
  }

  private async processMessages(): Promise<void> {
    const queueUrl = process.env.SQS_QUEUE_URL;
    if (!queueUrl) {
      throw new Error('SQS_QUEUE_URL not configured');
    }

    // Receive messages from SQS
    const result = await this.sqs.receiveMessage({
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 1,
      WaitTimeSeconds: 20, // Long polling
      VisibilityTimeout: 900, // 15 minutes to process
    }).promise();

    if (!result.Messages || result.Messages.length === 0) {
      return;
    }

    for (const message of result.Messages) {
      try {
        const body: SQSMessage = JSON.parse(message.Body || '{}');
        
        if (body.type !== 'shape-file') {
          logger.warn({ type: body.type }, 'Skipping non-shape-file message');
          continue;
        }

        logger.info({ uploadId: body.uploadId }, 'Processing shape file');
        
        // Process the shape file
        await this.processShapeFile(body);

        // Delete message from queue on success
        if (message.ReceiptHandle) {
          await this.sqs.deleteMessage({
            QueueUrl: queueUrl,
            ReceiptHandle: message.ReceiptHandle,
          }).promise();
        }

        logger.info({ uploadId: body.uploadId }, 'Successfully processed shape file');
      } catch (error) {
        logger.error({ error, message }, 'Failed to process message');
        // Message will become visible again after VisibilityTimeout
      }
    }
  }

  private async processShapeFile(message: SQSMessage): Promise<void> {
    const startTime = Date.now();
    const { uploadId, s3Bucket, s3Key, fileName, waterDemandMethod, metadata } = message;

    try {
      // Update status to processing
      await this.updateUploadStatus(uploadId, 'processing', {
        file_name: fileName,
        s3_bucket: s3Bucket,
        s3_key: s3Key,
        water_demand_method: waterDemandMethod,
        processing_interval: message.processingInterval,
        metadata,
      });

      // Download file from S3
      logger.info({ s3Bucket, s3Key }, 'Downloading file from S3');
      const s3Object = await this.s3.getObject({
        Bucket: s3Bucket,
        Key: s3Key,
      }).promise();

      if (!s3Object.Body) {
        throw new Error('Empty file received from S3');
      }

      const fileSize = s3Object.Body instanceof Buffer ? s3Object.Body.length : 0;

      // Extract and process shape files
      const uploadDir = path.join(this.tempDir, uploadId);
      fs.ensureDirSync(uploadDir);

      try {
        // Save zip file
        const zipPath = path.join(uploadDir, fileName);
        fs.writeFileSync(zipPath, s3Object.Body as Buffer);

        // Extract zip
        const zip = new AdmZip(zipPath);
        zip.extractAllTo(uploadDir, true);
        logger.info({ uploadDir }, 'Extracted zip file');

        // Parse shape files
        const parcels = await this.parseShapeFiles(uploadDir);
        logger.info({ count: parcels.length }, 'Parsed parcels from shape file');

        // Store parcels in database
        await this.storeParcels(uploadId, parcels, waterDemandMethod);

        // Update upload status
        const processingTime = Date.now() - startTime;
        await this.updateUploadStatus(uploadId, 'completed', {
          parcel_count: parcels.length,
          processing_time_ms: processingTime,
          file_size_bytes: fileSize,
        });

        // Calculate zone summaries
        await this.updateZoneSummaries(parcels);

      } finally {
        // Clean up temp files
        fs.removeSync(uploadDir);
      }

    } catch (error) {
      logger.error({ error, uploadId }, 'Failed to process shape file');
      
      await this.updateUploadStatus(uploadId, 'failed', {
        error_message: error instanceof Error ? error.message : 'Unknown error',
        processing_time_ms: Date.now() - startTime,
      });
      
      throw error;
    }
  }

  private async parseShapeFiles(directory: string): Promise<ParsedParcel[]> {
    const files = fs.readdirSync(directory);
    const shpFile = files.find(f => f.toLowerCase().endsWith('.shp'));
    const dbfFile = files.find(f => f.toLowerCase().endsWith('.dbf'));

    if (!shpFile) {
      throw new Error('No .shp file found in archive');
    }

    const shpPath = path.join(directory, shpFile);
    const dbfPath = dbfFile ? path.join(directory, dbfFile) : undefined;

    // Configure coordinate transformation
    const utm48n = '+proj=utm +zone=48 +datum=WGS84 +units=m +no_defs';
    const wgs84 = '+proj=longlat +datum=WGS84 +no_defs';
    const transform = proj4(utm48n, wgs84);

    const parcels: ParsedParcel[] = [];
    
    // Open shape file
    const source = await openShapefile(shpPath, dbfPath);
    let result = await source.read();

    while (!result.done && result.value) {
      const feature = result.value as Feature;
      
      if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') {
        result = await source.read();
        continue;
      }

      // Transform coordinates from UTM to WGS84
      const transformedGeometry = this.transformCoordinates(feature.geometry, transform);
      
      // Calculate area
      const area = turf.area(transformedGeometry);
      
      // Extract properties (case-insensitive)
      const props = feature.properties || {};
      const propsLower: any = {};
      Object.keys(props).forEach(key => {
        propsLower[key.toLowerCase()] = props[key];
      });

      const parcel: ParsedParcel = {
        parcelId: propsLower.parcel_id || propsLower.id || propsLower.objectid || `generated-${Date.now()}-${Math.random()}`,
        geometry: transformedGeometry,
        area,
        zone: propsLower.zone || propsLower.โซน || 'Unknown',
        subZone: propsLower.subzone || propsLower.sub_zone,
        ownerName: propsLower.owner || propsLower.owner_name || propsLower.ชื่อเจ้าของ,
        ownerId: propsLower.owner_id || propsLower.บัตรประชาชน,
        cropType: propsLower.crop_type || propsLower.crop || propsLower.ชนิดพืช,
        landUseType: propsLower.land_use || propsLower.การใช้ที่ดิน,
        attributes: props,
      };

      parcels.push(parcel);
      result = await source.read();
    }

    return parcels;
  }

  private transformCoordinates(geometry: Polygon | MultiPolygon, transform: proj4.Converter): any {
    if (geometry.type === 'Polygon') {
      return {
        type: 'Polygon',
        coordinates: geometry.coordinates.map(ring =>
          ring.map(coord => transform.forward(coord))
        ),
      };
    } else if (geometry.type === 'MultiPolygon') {
      return {
        type: 'MultiPolygon',
        coordinates: geometry.coordinates.map(polygon =>
          polygon.map(ring =>
            ring.map(coord => transform.forward(coord))
          )
        ),
      };
    }
    return geometry;
  }

  private async storeParcels(
    uploadId: string, 
    parcels: ParsedParcel[], 
    waterDemandMethod: string
  ): Promise<void> {
    const client = await this.db.connect();

    try {
      await client.query('BEGIN');

      // Get shape file ID
      const shapeFileResult = await client.query(
        'SELECT id FROM shape_file_uploads WHERE upload_id = $1',
        [uploadId]
      );

      if (shapeFileResult.rows.length === 0) {
        throw new Error(`Shape file upload not found: ${uploadId}`);
      }

      const shapeFileId = shapeFileResult.rows[0].id;

      // Mark previous parcels as historical (if doing full replacement)
      const zones = [...new Set(parcels.map(p => p.zone))];
      for (const zone of zones) {
        await client.query(`
          UPDATE parcels 
          SET valid_to = NOW() 
          WHERE zone = $1 AND valid_to IS NULL
        `, [zone]);
      }

      // Insert new parcels
      for (const parcel of parcels) {
        const centroid = turf.centroid(parcel.geometry);
        const areaRai = parcel.area / 1600; // Convert sqm to rai

        await client.query(`
          INSERT INTO parcels (
            parcel_id, shape_file_id, geometry, centroid,
            area_sqm, area_rai, zone, sub_zone,
            owner_name, owner_id, crop_type, land_use_type,
            water_demand_method, attributes
          ) VALUES (
            $1, $2, ST_GeomFromGeoJSON($3), ST_GeomFromGeoJSON($4),
            $5, $6, $7, $8,
            $9, $10, $11, $12,
            $13, $14
          )
        `, [
          parcel.parcelId,
          shapeFileId,
          JSON.stringify(parcel.geometry),
          JSON.stringify(centroid.geometry),
          parcel.area,
          areaRai,
          parcel.zone,
          parcel.subZone,
          parcel.ownerName,
          parcel.ownerId,
          parcel.cropType,
          parcel.landUseType,
          waterDemandMethod,
          JSON.stringify(parcel.attributes),
        ]);
      }

      await client.query('COMMIT');
      logger.info({ count: parcels.length }, 'Stored parcels in database');

    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  private async updateUploadStatus(
    uploadId: string, 
    status: string, 
    updates: any = {}
  ): Promise<void> {
    const client = await this.db.connect();

    try {
      // First, ensure the upload record exists
      const existing = await client.query(
        'SELECT id FROM shape_file_uploads WHERE upload_id = $1',
        [uploadId]
      );

      if (existing.rows.length === 0) {
        // Create the record if it doesn't exist
        await client.query(`
          INSERT INTO shape_file_uploads (
            upload_id, file_name, s3_bucket, s3_key, 
            status, water_demand_method, processing_interval, metadata
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        `, [
          uploadId,
          updates.file_name || 'unknown',
          updates.s3_bucket || 'unknown',
          updates.s3_key || 'unknown',
          status,
          updates.water_demand_method,
          updates.processing_interval,
          JSON.stringify(updates.metadata || {}),
        ]);
      } else {
        // Update existing record
        const setFields = ['status = $2'];
        const values = [uploadId, status];
        let paramCount = 2;

        if (status === 'processing') {
          setFields.push(`processing_started_at = NOW()`);
        } else if (status === 'completed' || status === 'failed') {
          setFields.push(`processing_completed_at = NOW()`);
        }

        Object.entries(updates).forEach(([key, value]) => {
          if (value !== undefined) {
            paramCount++;
            setFields.push(`${key} = $${paramCount}`);
            values.push(value);
          }
        });

        await client.query(`
          UPDATE shape_file_uploads 
          SET ${setFields.join(', ')}
          WHERE upload_id = $1
        `, values);
      }
    } finally {
      client.release();
    }
  }

  private async updateZoneSummaries(parcels: ParsedParcel[]): Promise<void> {
    const client = await this.db.connect();

    try {
      // Group parcels by zone
      const zoneGroups = parcels.reduce((acc, parcel) => {
        if (!acc[parcel.zone]) {
          acc[parcel.zone] = [];
        }
        acc[parcel.zone].push(parcel);
        return acc;
      }, {} as Record<string, ParsedParcel[]>);

      const summaryDate = new Date().toISOString().split('T')[0];

      for (const [zone, zoneParcels] of Object.entries(zoneGroups)) {
        const totalAreaSqm = zoneParcels.reduce((sum, p) => sum + p.area, 0);
        const totalAreaRai = totalAreaSqm / 1600;

        // Calculate crop distribution
        const cropDistribution = zoneParcels.reduce((acc, p) => {
          const crop = p.cropType || 'Unknown';
          acc[crop] = (acc[crop] || 0) + 1;
          return acc;
        }, {} as Record<string, number>);

        await client.query(`
          INSERT INTO zone_summaries (
            zone, summary_date, total_parcels, 
            total_area_sqm, total_area_rai, crop_distribution
          ) VALUES ($1, $2, $3, $4, $5, $6)
          ON CONFLICT (zone, summary_date) 
          DO UPDATE SET
            total_parcels = EXCLUDED.total_parcels,
            total_area_sqm = EXCLUDED.total_area_sqm,
            total_area_rai = EXCLUDED.total_area_rai,
            crop_distribution = EXCLUDED.crop_distribution,
            updated_at = NOW()
        `, [
          zone,
          summaryDate,
          zoneParcels.length,
          totalAreaSqm,
          totalAreaRai,
          JSON.stringify(cropDistribution),
        ]);
      }

      logger.info({ zones: Object.keys(zoneGroups) }, 'Updated zone summaries');
    } finally {
      client.release();
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
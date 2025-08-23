import { S3Event, Context, Callback } from 'aws-lambda';
import AWS from 'aws-sdk';
import { v4 as uuidv4 } from 'uuid';
import AdmZip from 'adm-zip';
import * as path from 'path';
import { open as openShapefile } from 'shapefile';
import proj4 from 'proj4';
import * as turf from '@turf/turf';
import { Feature, FeatureCollection, Polygon, MultiPolygon } from 'geojson';

const s3 = new AWS.S3();
const sqs = new AWS.SQS();
const dynamodb = new AWS.DynamoDB.DocumentClient();

const SHAPE_FILE_TABLE = process.env.SHAPE_FILE_TABLE || 'rid-ms-shapefiles';
const PARCEL_TABLE = process.env.PARCEL_TABLE || 'rid-ms-parcels';
const PROCESSING_QUEUE_URL = process.env.PROCESSING_QUEUE_URL || '';
const PROCESSED_BUCKET = process.env.PROCESSED_BUCKET || 'rid-ms-processed';
const TMP_DIR = '/tmp';

interface ShapeFileRecord {
  id: string;
  originalKey: string;
  bucket: string;
  uploadTime: string;
  status: 'pending' | 'processing' | 'processed' | 'failed';
  fileSize: number;
  waterDemandMethod?: 'RID-MS' | 'ROS' | 'AWD';
  processingInterval?: 'daily' | 'weekly' | 'bi-weekly';
  featureCount?: number;
  boundingBox?: any;
  error?: string;
  processedTime?: string;
}

interface ParcelRecord {
  id: string;
  shapeFileId: string;
  parcelId: string;
  geometry: any;
  area: number;
  zone?: string;
  subZone?: string;
  landUseType?: string;
  cropType?: string;
  plantingDate?: string;
  harvestDate?: string;
  owner?: string;
  waterDemandMethod: 'RID-MS' | 'ROS' | 'AWD';
  attributes: any;
  createdAt: string;
}

/**
 * Lambda handler for S3 trigger when shape files are uploaded
 */
export const handler = async (event: S3Event, context: Context, callback: Callback) => {
  console.log('Shape file ingestion triggered:', JSON.stringify(event, null, 2));

  for (const record of event.Records) {
    const bucket = record.s3.bucket.name;
    const key = decodeURIComponent(record.s3.object.key.replace(/\+/g, ' '));
    const shapeFileId = uuidv4();

    try {
      // Create shape file record
      const shapeFileRecord: ShapeFileRecord = {
        id: shapeFileId,
        originalKey: key,
        bucket,
        uploadTime: new Date().toISOString(),
        status: 'processing',
        fileSize: record.s3.object.size,
        waterDemandMethod: extractMetadataFromKey(key, 'method') as any || 'RID-MS',
        processingInterval: extractMetadataFromKey(key, 'interval') as any || 'weekly',
      };

      // Save initial record to DynamoDB
      await dynamodb.put({
        TableName: SHAPE_FILE_TABLE,
        Item: shapeFileRecord,
      }).promise();

      // Download file from S3
      const s3Object = await s3.getObject({ Bucket: bucket, Key: key }).promise();
      const buffer = s3Object.Body as Buffer;

      // Process based on file type
      let processedData: FeatureCollection;
      if (key.toLowerCase().endsWith('.zip')) {
        processedData = await processZipFile(buffer, shapeFileId);
      } else if (key.toLowerCase().endsWith('.shp')) {
        // For direct .shp upload, we'd need accompanying files
        throw new Error('Direct .shp upload requires accompanying .dbf, .shx files. Please upload as zip.');
      } else {
        throw new Error(`Unsupported file type: ${path.extname(key)}`);
      }

      // Extract parcels from GeoJSON
      const parcels = await extractParcels(processedData, shapeFileId, shapeFileRecord.waterDemandMethod);

      // Save parcels to DynamoDB in batches
      const BATCH_SIZE = 25; // DynamoDB batch write limit
      for (let i = 0; i < parcels.length; i += BATCH_SIZE) {
        const batch = parcels.slice(i, i + BATCH_SIZE);
        const putRequests = batch.map(parcel => ({
          PutRequest: { Item: parcel }
        }));

        await dynamodb.batchWrite({
          RequestItems: {
            [PARCEL_TABLE]: putRequests
          }
        }).promise();
      }

      // Calculate bounding box
      const boundingBox = turf.bbox(processedData);

      // Update shape file record with success
      await dynamodb.update({
        TableName: SHAPE_FILE_TABLE,
        Key: { id: shapeFileId },
        UpdateExpression: 'SET #status = :status, featureCount = :count, boundingBox = :bbox, processedTime = :time',
        ExpressionAttributeNames: {
          '#status': 'status'
        },
        ExpressionAttributeValues: {
          ':status': 'processed',
          ':count': parcels.length,
          ':bbox': boundingBox,
          ':time': new Date().toISOString()
        }
      }).promise();

      // Save processed GeoJSON to S3
      const processedKey = `processed/${shapeFileId}/parcels.geojson`;
      await s3.putObject({
        Bucket: PROCESSED_BUCKET,
        Key: processedKey,
        Body: JSON.stringify(processedData),
        ContentType: 'application/geo+json',
        Metadata: {
          shapeFileId,
          originalKey: key,
          featureCount: parcels.length.toString(),
        }
      }).promise();

      // Send message to SQS for water demand calculation
      await sqs.sendMessage({
        QueueUrl: PROCESSING_QUEUE_URL,
        MessageBody: JSON.stringify({
          type: 'CALCULATE_WATER_DEMAND',
          shapeFileId,
          parcelCount: parcels.length,
          waterDemandMethod: shapeFileRecord.waterDemandMethod,
          timestamp: new Date().toISOString(),
        }),
      }).promise();

      console.log(`Successfully processed shape file ${key}: ${parcels.length} parcels extracted`);

    } catch (error) {
      console.error(`Error processing shape file ${key}:`, error);

      // Update record with error
      await dynamodb.update({
        TableName: SHAPE_FILE_TABLE,
        Key: { id: shapeFileId },
        UpdateExpression: 'SET #status = :status, #error = :error',
        ExpressionAttributeNames: {
          '#status': 'status',
          '#error': 'error'
        },
        ExpressionAttributeValues: {
          ':status': 'failed',
          ':error': error.message || 'Unknown error'
        }
      }).promise();

      // Send error to DLQ
      await sqs.sendMessage({
        QueueUrl: process.env.DLQ_URL || '',
        MessageBody: JSON.stringify({
          type: 'SHAPE_FILE_PROCESSING_ERROR',
          shapeFileId,
          key,
          error: error.message,
          timestamp: new Date().toISOString(),
        }),
      }).promise();
    }
  }
};

/**
 * Process zip file containing shape files
 */
async function processZipFile(buffer: Buffer, shapeFileId: string): Promise<FeatureCollection> {
  const zip = new AdmZip(buffer);
  const tmpDir = path.join(TMP_DIR, shapeFileId);
  
  // Extract to temp directory
  zip.extractAllTo(tmpDir, true);

  // Find .shp file
  const entries = zip.getEntries();
  const shpEntry = entries.find(entry => entry.entryName.toLowerCase().endsWith('.shp'));
  
  if (!shpEntry) {
    throw new Error('No .shp file found in zip archive');
  }

  const shpPath = path.join(tmpDir, shpEntry.entryName);
  
  // Read shape file
  const features: Feature[] = [];
  const source = await openShapefile(shpPath);
  
  let result = await source.read();
  while (!result.done) {
    if (result.value) {
      // Transform coordinates from UTM Zone 48N to WGS84
      const transformedFeature = transformFeature(result.value as Feature);
      features.push(transformedFeature);
    }
    result = await source.read();
  }

  return {
    type: 'FeatureCollection',
    features,
  };
}

/**
 * Transform feature coordinates from UTM to WGS84
 */
function transformFeature(feature: Feature): Feature {
  const sourceProj = 'EPSG:32648'; // UTM Zone 48N
  const targetProj = 'EPSG:4326'; // WGS84
  const transform = proj4(sourceProj, targetProj);

  if (feature.geometry.type === 'Polygon') {
    const polygon = feature.geometry as Polygon;
    return {
      ...feature,
      geometry: {
        type: 'Polygon',
        coordinates: polygon.coordinates.map(ring =>
          ring.map(coord => transform.forward(coord))
        ),
      },
    };
  } else if (feature.geometry.type === 'MultiPolygon') {
    const multiPolygon = feature.geometry as MultiPolygon;
    return {
      ...feature,
      geometry: {
        type: 'MultiPolygon',
        coordinates: multiPolygon.coordinates.map(polygon =>
          polygon.map(ring =>
            ring.map(coord => transform.forward(coord))
          )
        ),
      },
    };
  }

  return feature;
}

/**
 * Extract parcels from GeoJSON features
 */
async function extractParcels(
  geoJson: FeatureCollection,
  shapeFileId: string,
  defaultMethod: 'RID-MS' | 'ROS' | 'AWD'
): Promise<ParcelRecord[]> {
  const parcels: ParcelRecord[] = [];

  for (const feature of geoJson.features) {
    if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') {
      continue;
    }

    const area = turf.area(feature.geometry);
    const parcelId = feature.properties?.PARCEL_ID || 
                    feature.properties?.parcel_id || 
                    feature.properties?.ID || 
                    uuidv4();

    const parcel: ParcelRecord = {
      id: uuidv4(),
      shapeFileId,
      parcelId,
      geometry: feature.geometry,
      area,
      zone: feature.properties?.ZONE || feature.properties?.zone,
      subZone: feature.properties?.SUBZONE || feature.properties?.subzone,
      landUseType: feature.properties?.LAND_USE || feature.properties?.land_use,
      cropType: feature.properties?.CROP_TYPE || feature.properties?.crop_type,
      owner: feature.properties?.OWNER || feature.properties?.owner,
      waterDemandMethod: determineWaterDemandMethod(feature.properties, defaultMethod),
      attributes: feature.properties || {},
      createdAt: new Date().toISOString(),
    };

    // Parse dates if present
    if (feature.properties?.PLANTING_DATE) {
      parcel.plantingDate = feature.properties.PLANTING_DATE;
    }
    if (feature.properties?.HARVEST_DATE) {
      parcel.harvestDate = feature.properties.HARVEST_DATE;
    }

    parcels.push(parcel);
  }

  return parcels;
}

/**
 * Determine water demand calculation method
 */
function determineWaterDemandMethod(
  properties: any,
  defaultMethod: 'RID-MS' | 'ROS' | 'AWD'
): 'RID-MS' | 'ROS' | 'AWD' {
  if (properties?.WATER_DEMAND_METHOD) {
    const method = properties.WATER_DEMAND_METHOD.toUpperCase();
    if (['RID-MS', 'ROS', 'AWD'].includes(method)) {
      return method as 'RID-MS' | 'ROS' | 'AWD';
    }
  }
  return defaultMethod;
}

/**
 * Extract metadata from S3 key
 */
function extractMetadataFromKey(key: string, field: string): string | undefined {
  // Example key format: rid-ms/uploads/2024-01-15/method-AWD/interval-weekly/parcels.zip
  const parts = key.split('/');
  for (const part of parts) {
    if (part.startsWith(`${field}-`)) {
      return part.substring(field.length + 1);
    }
  }
  return undefined;
}
import { SQSEvent, Context } from 'aws-lambda';
import AWS from 'aws-sdk';
import AdmZip from 'adm-zip';
import * as path from 'path';
import { open as openShapefile } from 'shapefile';
import proj4 from 'proj4';
import * as turf from '@turf/turf';
import { Feature, FeatureCollection, Polygon, MultiPolygon } from 'geojson';
import { v4 as uuidv4 } from 'uuid';

const s3 = new AWS.S3();
const dynamodb = new AWS.DynamoDB.DocumentClient();
const sqs = new AWS.SQS();

const SHAPE_FILE_TABLE = process.env.SHAPE_FILE_TABLE || 'rid-ms-shapefiles';
const PARCEL_TABLE = process.env.PARCEL_TABLE || 'rid-ms-parcels';
const WATER_DEMAND_QUEUE_URL = process.env.WATER_DEMAND_QUEUE_URL || '';
const PROCESSED_BUCKET = process.env.PROCESSED_BUCKET || 'rid-ms-processed';
const TMP_DIR = '/tmp';

interface SQSMessage {
  uploadId: string;
  s3Bucket: string;
  s3Key: string;
  fileName: string;
  waterDemandMethod: 'RID-MS' | 'ROS' | 'AWD';
  processingInterval: 'daily' | 'weekly' | 'bi-weekly';
  metadata?: any;
  uploadedAt: string;
  source: string;
}

/**
 * SQS Consumer Lambda handler for processing shape files
 */
export const handler = async (event: SQSEvent, context: Context) => {
  console.log('SQS Consumer triggered:', JSON.stringify(event, null, 2));

  for (const record of event.Records) {
    const message: SQSMessage = JSON.parse(record.body);
    const shapeFileId = message.uploadId;

    try {
      console.log(`Processing shape file: ${message.fileName} (${shapeFileId})`);

      // Create shape file record
      const shapeFileRecord = {
        id: shapeFileId,
        originalKey: message.s3Key,
        bucket: message.s3Bucket,
        fileName: message.fileName,
        uploadTime: message.uploadedAt,
        status: 'processing',
        waterDemandMethod: message.waterDemandMethod,
        processingInterval: message.processingInterval,
        metadata: message.metadata,
      };

      // Save initial record to DynamoDB
      await dynamodb.put({
        TableName: SHAPE_FILE_TABLE,
        Item: shapeFileRecord,
      }).promise();

      // Download file from S3
      console.log(`Downloading from S3: ${message.s3Bucket}/${message.s3Key}`);
      const s3Object = await s3.getObject({
        Bucket: message.s3Bucket,
        Key: message.s3Key,
      }).promise();

      if (!s3Object.Body) {
        throw new Error('Empty file received from S3');
      }

      const buffer = s3Object.Body as Buffer;

      // Process zip file
      const processedData = await processZipFile(buffer, shapeFileId);
      console.log(`Extracted ${processedData.features.length} features from shape file`);

      // Extract parcels
      const parcels = await extractParcels(
        processedData,
        shapeFileId,
        message.waterDemandMethod
      );
      console.log(`Processed ${parcels.length} parcels`);

      // Save parcels to DynamoDB in batches
      const BATCH_SIZE = 25; // DynamoDB batch write limit
      let savedCount = 0;

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

        savedCount += batch.length;
        console.log(`Saved ${savedCount}/${parcels.length} parcels`);
      }

      // Calculate bounding box
      const boundingBox = turf.bbox(processedData);

      // Update shape file record with success
      await dynamodb.update({
        TableName: SHAPE_FILE_TABLE,
        Key: { id: shapeFileId },
        UpdateExpression: 'SET #status = :status, featureCount = :count, boundingBox = :bbox, processedTime = :time, fileSize = :size',
        ExpressionAttributeNames: {
          '#status': 'status'
        },
        ExpressionAttributeValues: {
          ':status': 'processed',
          ':count': parcels.length,
          ':bbox': boundingBox,
          ':time': new Date().toISOString(),
          ':size': buffer.length,
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
          originalFileName: message.fileName,
          featureCount: parcels.length.toString(),
          processedAt: new Date().toISOString(),
        }
      }).promise();

      console.log(`Saved processed GeoJSON to S3: ${processedKey}`);

      // Send message to water demand calculation queue
      await sqs.sendMessage({
        QueueUrl: WATER_DEMAND_QUEUE_URL,
        MessageBody: JSON.stringify({
          type: 'CALCULATE_WATER_DEMAND',
          shapeFileId,
          parcelCount: parcels.length,
          waterDemandMethod: message.waterDemandMethod,
          timestamp: new Date().toISOString(),
        }),
      }).promise();

      console.log(`Shape file processing completed: ${shapeFileId}`);

    } catch (error) {
      console.error(`Error processing shape file ${shapeFileId}:`, error);

      // Update record with error
      await dynamodb.update({
        TableName: SHAPE_FILE_TABLE,
        Key: { id: shapeFileId },
        UpdateExpression: 'SET #status = :status, #error = :error, processedTime = :time',
        ExpressionAttributeNames: {
          '#status': 'status',
          '#error': 'error'
        },
        ExpressionAttributeValues: {
          ':status': 'failed',
          ':error': error.message || 'Unknown error',
          ':time': new Date().toISOString(),
        }
      }).promise();

      // Re-throw to let SQS handle retry
      throw error;
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
  console.log(`Extracted zip to: ${tmpDir}`);

  // Find .shp file
  const entries = zip.getEntries();
  const shpEntry = entries.find(entry => entry.entryName.toLowerCase().endsWith('.shp'));
  
  if (!shpEntry) {
    throw new Error('No .shp file found in zip archive');
  }

  const shpPath = path.join(tmpDir, shpEntry.entryName);
  console.log(`Processing shape file: ${shpPath}`);
  
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

  console.log(`Read ${features.length} features from shape file`);

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
): Promise<any[]> {
  const parcels = [];

  for (const feature of geoJson.features) {
    if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') {
      continue;
    }

    const area = turf.area(feature.geometry);
    const parcelId = feature.properties?.PARCEL_ID || 
                    feature.properties?.parcel_id || 
                    feature.properties?.ID || 
                    uuidv4();

    const parcel = {
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
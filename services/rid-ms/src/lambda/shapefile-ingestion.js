"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.handler = void 0;
const aws_sdk_1 = __importDefault(require("aws-sdk"));
const uuid_1 = require("uuid");
const adm_zip_1 = __importDefault(require("adm-zip"));
const path = __importStar(require("path"));
const shapefile_1 = require("shapefile");
const proj4_1 = __importDefault(require("proj4"));
const turf = __importStar(require("@turf/turf"));
const s3 = new aws_sdk_1.default.S3();
const sqs = new aws_sdk_1.default.SQS();
const dynamodb = new aws_sdk_1.default.DynamoDB.DocumentClient();
const SHAPE_FILE_TABLE = process.env.SHAPE_FILE_TABLE || 'rid-ms-shapefiles';
const PARCEL_TABLE = process.env.PARCEL_TABLE || 'rid-ms-parcels';
const PROCESSING_QUEUE_URL = process.env.PROCESSING_QUEUE_URL || '';
const PROCESSED_BUCKET = process.env.PROCESSED_BUCKET || 'rid-ms-processed';
const TMP_DIR = '/tmp';
const handler = async (event, context, callback) => {
    console.log('Shape file ingestion triggered:', JSON.stringify(event, null, 2));
    for (const record of event.Records) {
        const bucket = record.s3.bucket.name;
        const key = decodeURIComponent(record.s3.object.key.replace(/\+/g, ' '));
        const shapeFileId = (0, uuid_1.v4)();
        try {
            const shapeFileRecord = {
                id: shapeFileId,
                originalKey: key,
                bucket,
                uploadTime: new Date().toISOString(),
                status: 'processing',
                fileSize: record.s3.object.size,
                waterDemandMethod: extractMetadataFromKey(key, 'method') || 'RID-MS',
                processingInterval: extractMetadataFromKey(key, 'interval') || 'weekly',
            };
            await dynamodb.put({
                TableName: SHAPE_FILE_TABLE,
                Item: shapeFileRecord,
            }).promise();
            const s3Object = await s3.getObject({ Bucket: bucket, Key: key }).promise();
            const buffer = s3Object.Body;
            let processedData;
            if (key.toLowerCase().endsWith('.zip')) {
                processedData = await processZipFile(buffer, shapeFileId);
            }
            else if (key.toLowerCase().endsWith('.shp')) {
                throw new Error('Direct .shp upload requires accompanying .dbf, .shx files. Please upload as zip.');
            }
            else {
                throw new Error(`Unsupported file type: ${path.extname(key)}`);
            }
            const parcels = await extractParcels(processedData, shapeFileId, shapeFileRecord.waterDemandMethod);
            const BATCH_SIZE = 25;
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
            const boundingBox = turf.bbox(processedData);
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
        }
        catch (error) {
            console.error(`Error processing shape file ${key}:`, error);
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
exports.handler = handler;
async function processZipFile(buffer, shapeFileId) {
    const zip = new adm_zip_1.default(buffer);
    const tmpDir = path.join(TMP_DIR, shapeFileId);
    zip.extractAllTo(tmpDir, true);
    const entries = zip.getEntries();
    const shpEntry = entries.find(entry => entry.entryName.toLowerCase().endsWith('.shp'));
    if (!shpEntry) {
        throw new Error('No .shp file found in zip archive');
    }
    const shpPath = path.join(tmpDir, shpEntry.entryName);
    const features = [];
    const source = await (0, shapefile_1.open)(shpPath);
    let result = await source.read();
    while (!result.done) {
        if (result.value) {
            const transformedFeature = transformFeature(result.value);
            features.push(transformedFeature);
        }
        result = await source.read();
    }
    return {
        type: 'FeatureCollection',
        features,
    };
}
function transformFeature(feature) {
    const sourceProj = 'EPSG:32648';
    const targetProj = 'EPSG:4326';
    const transform = (0, proj4_1.default)(sourceProj, targetProj);
    if (feature.geometry.type === 'Polygon') {
        const polygon = feature.geometry;
        return {
            ...feature,
            geometry: {
                type: 'Polygon',
                coordinates: polygon.coordinates.map(ring => ring.map(coord => transform.forward(coord))),
            },
        };
    }
    else if (feature.geometry.type === 'MultiPolygon') {
        const multiPolygon = feature.geometry;
        return {
            ...feature,
            geometry: {
                type: 'MultiPolygon',
                coordinates: multiPolygon.coordinates.map(polygon => polygon.map(ring => ring.map(coord => transform.forward(coord)))),
            },
        };
    }
    return feature;
}
async function extractParcels(geoJson, shapeFileId, defaultMethod) {
    const parcels = [];
    for (const feature of geoJson.features) {
        if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') {
            continue;
        }
        const area = turf.area(feature.geometry);
        const parcelId = feature.properties?.PARCEL_ID ||
            feature.properties?.parcel_id ||
            feature.properties?.ID ||
            (0, uuid_1.v4)();
        const parcel = {
            id: (0, uuid_1.v4)(),
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
function determineWaterDemandMethod(properties, defaultMethod) {
    if (properties?.WATER_DEMAND_METHOD) {
        const method = properties.WATER_DEMAND_METHOD.toUpperCase();
        if (['RID-MS', 'ROS', 'AWD'].includes(method)) {
            return method;
        }
    }
    return defaultMethod;
}
function extractMetadataFromKey(key, field) {
    const parts = key.split('/');
    for (const part of parts) {
        if (part.startsWith(`${field}-`)) {
            return part.substring(field.length + 1);
        }
    }
    return undefined;
}
//# sourceMappingURL=shapefile-ingestion.js.map
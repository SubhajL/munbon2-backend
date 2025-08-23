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
exports.ShapeFileProcessor = void 0;
const AWS = __importStar(require("aws-sdk"));
const pg_1 = require("pg");
const fs = __importStar(require("fs-extra"));
const path = __importStar(require("path"));
const adm_zip_1 = __importDefault(require("adm-zip"));
const shapefile_1 = require("shapefile");
const proj4_1 = __importDefault(require("proj4"));
const turf = __importStar(require("@turf/turf"));
const pino_1 = __importDefault(require("pino"));
const logger = (0, pino_1.default)({ level: 'info' });
class ShapeFileProcessor {
    sqs;
    s3;
    db;
    isRunning = false;
    tempDir = '/tmp/shape-files';
    constructor() {
        this.sqs = new AWS.SQS({ region: process.env.AWS_REGION || 'ap-southeast-1' });
        this.s3 = new AWS.S3({ region: process.env.AWS_REGION || 'ap-southeast-1' });
        this.db = new pg_1.Pool({
            connectionString: process.env.DATABASE_URL,
            max: 10,
            idleTimeoutMillis: 30000,
        });
        fs.ensureDirSync(this.tempDir);
    }
    async start() {
        logger.info('Starting Shape File Processor...');
        this.isRunning = true;
        while (this.isRunning) {
            try {
                await this.processMessages();
                await this.sleep(10000);
            }
            catch (error) {
                logger.error({ error }, 'Error in processing loop');
                await this.sleep(30000);
            }
        }
    }
    async stop() {
        logger.info('Stopping Shape File Processor...');
        this.isRunning = false;
        await this.db.end();
    }
    async processMessages() {
        const queueUrl = process.env.SQS_QUEUE_URL;
        if (!queueUrl) {
            throw new Error('SQS_QUEUE_URL not configured');
        }
        const result = await this.sqs.receiveMessage({
            QueueUrl: queueUrl,
            MaxNumberOfMessages: 1,
            WaitTimeSeconds: 20,
            VisibilityTimeout: 900,
        }).promise();
        if (!result.Messages || result.Messages.length === 0) {
            return;
        }
        for (const message of result.Messages) {
            try {
                const body = JSON.parse(message.Body || '{}');
                if (body.type !== 'shape-file') {
                    logger.warn({ type: body.type }, 'Skipping non-shape-file message');
                    continue;
                }
                logger.info({ uploadId: body.uploadId }, 'Processing shape file');
                await this.processShapeFile(body);
                if (message.ReceiptHandle) {
                    await this.sqs.deleteMessage({
                        QueueUrl: queueUrl,
                        ReceiptHandle: message.ReceiptHandle,
                    }).promise();
                }
                logger.info({ uploadId: body.uploadId }, 'Successfully processed shape file');
            }
            catch (error) {
                logger.error({ error, message }, 'Failed to process message');
            }
        }
    }
    async processShapeFile(message) {
        const startTime = Date.now();
        const { uploadId, s3Bucket, s3Key, fileName, waterDemandMethod, metadata } = message;
        try {
            await this.updateUploadStatus(uploadId, 'processing', {
                file_name: fileName,
                s3_bucket: s3Bucket,
                s3_key: s3Key,
                water_demand_method: waterDemandMethod,
                processing_interval: message.processingInterval,
                metadata,
            });
            logger.info({ s3Bucket, s3Key }, 'Downloading file from S3');
            const s3Object = await this.s3.getObject({
                Bucket: s3Bucket,
                Key: s3Key,
            }).promise();
            if (!s3Object.Body) {
                throw new Error('Empty file received from S3');
            }
            const fileSize = s3Object.Body instanceof Buffer ? s3Object.Body.length : 0;
            const uploadDir = path.join(this.tempDir, uploadId);
            fs.ensureDirSync(uploadDir);
            try {
                const zipPath = path.join(uploadDir, fileName);
                fs.writeFileSync(zipPath, s3Object.Body);
                const zip = new adm_zip_1.default(zipPath);
                zip.extractAllTo(uploadDir, true);
                logger.info({ uploadDir }, 'Extracted zip file');
                const parcels = await this.parseShapeFiles(uploadDir);
                logger.info({ count: parcels.length }, 'Parsed parcels from shape file');
                await this.storeParcels(uploadId, parcels, waterDemandMethod);
                const processingTime = Date.now() - startTime;
                await this.updateUploadStatus(uploadId, 'completed', {
                    parcel_count: parcels.length,
                    processing_time_ms: processingTime,
                    file_size_bytes: fileSize,
                });
                await this.updateZoneSummaries(parcels);
            }
            finally {
                fs.removeSync(uploadDir);
            }
        }
        catch (error) {
            logger.error({ error, uploadId }, 'Failed to process shape file');
            await this.updateUploadStatus(uploadId, 'failed', {
                error_message: error instanceof Error ? error.message : 'Unknown error',
                processing_time_ms: Date.now() - startTime,
            });
            throw error;
        }
    }
    async parseShapeFiles(directory) {
        const files = fs.readdirSync(directory);
        const shpFile = files.find(f => f.toLowerCase().endsWith('.shp'));
        const dbfFile = files.find(f => f.toLowerCase().endsWith('.dbf'));
        if (!shpFile) {
            throw new Error('No .shp file found in archive');
        }
        const shpPath = path.join(directory, shpFile);
        const dbfPath = dbfFile ? path.join(directory, dbfFile) : undefined;
        const utm48n = '+proj=utm +zone=48 +datum=WGS84 +units=m +no_defs';
        const wgs84 = '+proj=longlat +datum=WGS84 +no_defs';
        const transform = (0, proj4_1.default)(utm48n, wgs84);
        const parcels = [];
        const source = await (0, shapefile_1.open)(shpPath, dbfPath);
        let result = await source.read();
        while (!result.done && result.value) {
            const feature = result.value;
            if (feature.geometry.type !== 'Polygon' && feature.geometry.type !== 'MultiPolygon') {
                result = await source.read();
                continue;
            }
            const transformedGeometry = this.transformCoordinates(feature.geometry, transform);
            const area = turf.area(transformedGeometry);
            const props = feature.properties || {};
            const propsLower = {};
            Object.keys(props).forEach(key => {
                propsLower[key.toLowerCase()] = props[key];
            });
            const parcel = {
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
    transformCoordinates(geometry, transform) {
        if (geometry.type === 'Polygon') {
            return {
                type: 'Polygon',
                coordinates: geometry.coordinates.map(ring => ring.map(coord => transform.forward(coord))),
            };
        }
        else if (geometry.type === 'MultiPolygon') {
            return {
                type: 'MultiPolygon',
                coordinates: geometry.coordinates.map(polygon => polygon.map(ring => ring.map(coord => transform.forward(coord)))),
            };
        }
        return geometry;
    }
    async storeParcels(uploadId, parcels, waterDemandMethod) {
        const client = await this.db.connect();
        try {
            await client.query('BEGIN');
            const shapeFileResult = await client.query('SELECT id FROM shape_file_uploads WHERE upload_id = $1', [uploadId]);
            if (shapeFileResult.rows.length === 0) {
                throw new Error(`Shape file upload not found: ${uploadId}`);
            }
            const shapeFileId = shapeFileResult.rows[0].id;
            const zones = [...new Set(parcels.map(p => p.zone))];
            for (const zone of zones) {
                await client.query(`
          UPDATE parcels 
          SET valid_to = NOW() 
          WHERE zone = $1 AND valid_to IS NULL
        `, [zone]);
            }
            for (const parcel of parcels) {
                const centroid = turf.centroid(parcel.geometry);
                const areaRai = parcel.area / 1600;
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
        }
        catch (error) {
            await client.query('ROLLBACK');
            throw error;
        }
        finally {
            client.release();
        }
    }
    async updateUploadStatus(uploadId, status, updates = {}) {
        const client = await this.db.connect();
        try {
            const existing = await client.query('SELECT id FROM shape_file_uploads WHERE upload_id = $1', [uploadId]);
            if (existing.rows.length === 0) {
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
            }
            else {
                const setFields = ['status = $2'];
                const values = [uploadId, status];
                let paramCount = 2;
                if (status === 'processing') {
                    setFields.push(`processing_started_at = NOW()`);
                }
                else if (status === 'completed' || status === 'failed') {
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
        }
        finally {
            client.release();
        }
    }
    async updateZoneSummaries(parcels) {
        const client = await this.db.connect();
        try {
            const zoneGroups = parcels.reduce((acc, parcel) => {
                if (!acc[parcel.zone]) {
                    acc[parcel.zone] = [];
                }
                acc[parcel.zone].push(parcel);
                return acc;
            }, {});
            const summaryDate = new Date().toISOString().split('T')[0];
            for (const [zone, zoneParcels] of Object.entries(zoneGroups)) {
                const totalAreaSqm = zoneParcels.reduce((sum, p) => sum + p.area, 0);
                const totalAreaRai = totalAreaSqm / 1600;
                const cropDistribution = zoneParcels.reduce((acc, p) => {
                    const crop = p.cropType || 'Unknown';
                    acc[crop] = (acc[crop] || 0) + 1;
                    return acc;
                }, {});
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
        }
        finally {
            client.release();
        }
    }
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}
exports.ShapeFileProcessor = ShapeFileProcessor;
//# sourceMappingURL=shape-file-processor.js.map
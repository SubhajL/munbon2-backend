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
Object.defineProperty(exports, "__esModule", { value: true });
exports.ShapeFileService = void 0;
const AWS = __importStar(require("aws-sdk"));
const uuid_1 = require("uuid");
const database_1 = require("../config/database");
const shapefile_processor_1 = require("./shapefile-processor");
const geopackage_processor_1 = require("./geopackage-processor");
const parcel_entity_1 = require("../models/parcel.entity");
const parcel_simple_entity_1 = require("../models/parcel-simple.entity");
const shape_file_upload_entity_1 = require("../models/shape-file-upload.entity");
const logger_1 = require("../utils/logger");
const fs = __importStar(require("fs/promises"));
const path = __importStar(require("path"));
class ShapeFileService {
    s3;
    sqs;
    processor;
    geopackageProcessor;
    constructor() {
        AWS.config.update({ region: process.env.AWS_REGION || 'ap-southeast-1' });
        this.s3 = new AWS.S3();
        this.sqs = new AWS.SQS();
        this.processor = new shapefile_processor_1.ShapeFileProcessor();
        this.geopackageProcessor = new geopackage_processor_1.GeoPackageProcessor();
    }
    async processUpload(options) {
        const uploadId = (0, uuid_1.v4)();
        const timestamp = new Date();
        const uploadDate = timestamp.toISOString().split('T')[0];
        try {
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
            logger_1.logger.info('Shape file uploaded to S3', { uploadId, s3Key });
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
            logger_1.logger.info('Shape file message sent to SQS', { uploadId, queueUrl });
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
        }
        catch (error) {
            logger_1.logger.error('Failed to process shape file upload', { error, uploadId });
            throw error;
        }
    }
    async processShapeFileFromQueue(message) {
        const { uploadId, s3Bucket, s3Key, fileName, waterDemandMethod, metadata } = message;
        try {
            await this.updateUploadStatus(uploadId, 'processing');
            const s3Object = await this.s3.getObject({
                Bucket: s3Bucket,
                Key: s3Key,
            }).promise();
            if (!s3Object.Body) {
                throw new Error('Empty file received from S3');
            }
            const isGeoPackage = fileName.toLowerCase().endsWith('.gpkg');
            if (isGeoPackage) {
                const tempDir = process.env.TEMP_DIR || '/tmp';
                const tempFilePath = path.join(tempDir, `${uploadId}.gpkg`);
                await fs.writeFile(tempFilePath, s3Object.Body);
                try {
                    const results = await this.geopackageProcessor.processGeoPackageFile(tempFilePath, uploadId);
                    const saveResults = await this.geopackageProcessor.saveProcessingResults(results);
                    await this.updateUploadStatus(uploadId, 'completed', {
                        parcelCount: saveResults.totalParcels,
                        zoneCount: saveResults.totalZones,
                        completedAt: new Date(),
                        errors: saveResults.errors,
                    });
                    logger_1.logger.info('GeoPackage processing completed', {
                        uploadId,
                        parcelCount: saveResults.totalParcels,
                        zoneCount: saveResults.totalZones
                    });
                }
                finally {
                    await fs.unlink(tempFilePath).catch(() => { });
                }
            }
            else {
                const parcels = await this.processor.processShapeFile({
                    buffer: s3Object.Body,
                    fileName,
                    uploadId,
                });
                await this.storeParcels(uploadId, parcels);
                await this.updateUploadStatus(uploadId, 'completed', {
                    parcelCount: parcels.length,
                    completedAt: new Date(),
                });
                logger_1.logger.info('Shape file processing completed', { uploadId, parcelCount: parcels.length });
            }
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            const errorStack = error instanceof Error ? error.stack : undefined;
            logger_1.logger.error('Failed to process file', {
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
    async storeUploadRecord(data) {
        const uploadRepository = database_1.AppDataSource.getRepository(shape_file_upload_entity_1.ShapeFileUpload);
        const upload = new shape_file_upload_entity_1.ShapeFileUpload();
        upload.uploadId = data.uploadId;
        upload.fileName = data.fileName;
        upload.s3Key = data.s3Key;
        upload.status = shape_file_upload_entity_1.UploadStatus.PENDING;
        upload.metadata = data.metadata;
        await uploadRepository.save(upload);
        logger_1.logger.info('Storing upload record', { uploadId: data.uploadId });
    }
    async updateUploadStatus(uploadId, status, metadata) {
        const uploadRepository = database_1.AppDataSource.getRepository(shape_file_upload_entity_1.ShapeFileUpload);
        const upload = await uploadRepository.findOne({ where: { uploadId } });
        if (upload) {
            upload.status = status;
            if (metadata) {
                if (metadata.parcelCount)
                    upload.parcelCount = metadata.parcelCount;
                if (metadata.completedAt)
                    upload.completedAt = metadata.completedAt;
                if (metadata.error)
                    upload.error = metadata.error;
                upload.metadata = { ...upload.metadata, ...metadata };
            }
            await uploadRepository.save(upload);
        }
        logger_1.logger.info('Updating upload status', { uploadId, status, metadata });
    }
    async storeParcels(uploadId, parcels) {
        let usePostGIS = false;
        try {
            const postgisCheck = await database_1.AppDataSource.query(`
        SELECT EXISTS (
          SELECT 1 FROM pg_extension WHERE extname = 'postgis'
        ) as postgis_exists
      `);
            usePostGIS = postgisCheck[0].postgis_exists;
        }
        catch (error) {
            logger_1.logger.warn('Could not check PostGIS availability, using simple storage');
        }
        if (usePostGIS) {
            const parcelRepository = database_1.AppDataSource.getRepository(parcel_entity_1.Parcel);
            const zones = await database_1.AppDataSource.query(`
        SELECT id, zone_code FROM gis.irrigation_zones 
        WHERE zone_code IN ('Z001', 'Z002', 'Z003', 'Z004', 'Z005', 'Z006')
        ORDER BY zone_code
      `);
            const zoneMapping = {};
            zones.forEach((zone) => {
                const zoneNum = zone.zone_code.replace('Z00', '');
                zoneMapping[zoneNum] = zone.id;
            });
            const defaultZoneId = zoneMapping['1'] || zones[0]?.id;
            if (!defaultZoneId) {
                throw new Error('No valid zones found in database. Please create zones first.');
            }
            logger_1.logger.info('Zone mapping', { zoneMapping, defaultZoneId });
            for (const parcelData of parcels) {
                try {
                    const parcel = new parcel_entity_1.Parcel();
                    parcel.plotCode = parcelData.parcelId || `P-${uploadId}-${Date.now()}`;
                    const zoneNum = String(parcelData.zoneId || '1');
                    parcel.zoneId = zoneMapping[zoneNum] || defaultZoneId;
                    parcel.farmerId = parcelData.ownerId || `farmer-${Date.now()}`;
                    if (parcelData.geometry && parcelData.geometry.type === 'MultiPolygon') {
                        let largestArea = 0;
                        let largestPolygon = null;
                        for (const polygon of parcelData.geometry.coordinates) {
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
                    }
                    else {
                        parcel.boundary = parcelData.geometry;
                    }
                    parcel.areaHectares = parcelData.area / 10000;
                    parcel.currentCropType = parcelData.cropType || parcelData.landUseType || 'rice';
                    parcel.soilType = parcelData.attributes?.soil_type || 'unknown';
                    if (parcelData.ridAttributes) {
                        const rid = parcelData.ridAttributes;
                        if (rid.parcelAreaRai) {
                            parcel.areaHectares = rid.parcelAreaRai * 0.16;
                        }
                        if (rid.startInt) {
                            parcel.plantingDate = new Date(rid.startInt);
                            parcel.expectedHarvestDate = new Date(rid.startInt);
                            parcel.expectedHarvestDate.setDate(parcel.expectedHarvestDate.getDate() + 120);
                        }
                        if (rid.plantId) {
                            parcel.currentCropType = rid.plantId;
                        }
                        parcel.properties = {
                            uploadId,
                            ridAttributes: rid,
                            lastUpdated: new Date(),
                        };
                    }
                    await parcelRepository.upsert(parcel, {
                        conflictPaths: ['plotCode'],
                        skipUpdateIfNoValuesChanged: true,
                    });
                }
                catch (error) {
                    logger_1.logger.error('Failed to save parcel with PostGIS', { error, parcelData });
                    throw error;
                }
            }
        }
        else {
            const parcelRepository = database_1.AppDataSource.getRepository(parcel_simple_entity_1.ParcelSimple);
            for (const parcelData of parcels) {
                const parcel = new parcel_simple_entity_1.ParcelSimple();
                parcel.uploadId = uploadId;
                parcel.parcelCode = parcelData.parcelId || `P-${uploadId}-${Date.now()}`;
                parcel.zoneId = parcelData.zoneId || '1';
                parcel.geometry = parcelData.geometry;
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
                if (!parcel.centroid && parcelData.geometry) {
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
        logger_1.logger.info('Parcels stored in database', {
            uploadId,
            count: parcels.length,
            storageType: usePostGIS ? 'PostGIS' : 'Simple'
        });
    }
    async listUploads(options) {
        return {
            uploads: [],
            total: 0,
            page: options.page,
            limit: options.limit,
        };
    }
    async getUploadStatus(uploadId) {
        return null;
    }
    async getUploadParcels(uploadId) {
        logger_1.logger.warn('getUploadParcels not implemented for new schema');
        return [];
    }
    async deleteUpload(uploadId) {
        logger_1.logger.info('Deleting upload and associated data', { uploadId });
    }
}
exports.ShapeFileService = ShapeFileService;
//# sourceMappingURL=shapefile.service.js.map